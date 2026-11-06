"""Zero-inference prerequisite observations, never construction or qualification."""
import ast
import os
import sys
from importlib.util import find_spec
from pathlib import Path
from creation_pipeline.records import file_digest,has_link,sanitized,redact
from creation_pipeline.resources.intake import exclusion
from creation_pipeline.runtime import shared_tool as st,bundled_data as bd
from creation_pipeline.models import exceeded, runtime_spec


def check(config,mode='build',snapshots=None,offline=False):
    if config.get('workflow') == 'shared-environments':
        from creation_pipeline.shared.readiness import check as shared_check
        return shared_check(config, mode, offline)
    checks=[];roots=[];inventories={}
    specs=[('runtime_defaults',runtime_spec(config))]
    specs += [('runtime.'+name,runtime_spec(config,name)) for name in config.get('runtime',{})]
    executable=any(s.get('shared_tool') or s.get('plan') for _,s in specs)
    executable=executable or any(r.get('status')=='required' for r in config.get('runtime_requirements',{}).values() if isinstance(r,dict))
    runtime_required=mode=='build' and not config.get('draft_only',False) and executable and not offline
    def add(obj,path,expected,actual,code=None,blocking=True,reason=''):
        checks.append({'object':obj,'path':str(path),'expected':expected,'actual':actual,
                       'status':'blocked' if code and blocking else 'deferred' if code else 'passed',
                       'code':code,'reason':reason})
    total_bytes=0
    sources=snapshots if snapshots is not None else config['sources']
    for source in sources:
        sid=source['id'];location=source.get('path')
        if not location:
            if 'table' in source:location=source['table']
            else:
                add('source:'+sid,source.get('url') or source.get('repo') or source.get('paper'),
                    'acquired local snapshot','remote acquisition pending','source_acquisition_pending',False);continue
        root=Path(location)
        if not root.exists() or has_link(root):
            add('source:'+sid,root,'existing unlinked readable source',{'exists':root.exists(),'linked':has_link(root)},'source_unavailable');continue
        try:
            files=[]
            if root.is_file():files=[root] if exclusion(Path(root.name)) is None else []
            else:
                for directory,names,leaves in os.walk(root,followlinks=False):
                    names[:]=[n for n in names if not exclusion(Path(directory,n).relative_to(root)) and not has_link(Path(directory,n))]
                    for name in leaves:
                        p=Path(directory,name)
                        if not exclusion(p.relative_to(root)) and not has_link(p):files.append(p)
            if not files:
                add('source:'+sid,root,'at least one retained readable file',0,'source_empty');continue
            inventory=[]
            if exceeded(len(files),config['limits']['source_files']):
                add('source:'+sid,root,'retained file count <= source_files',len(files),'source_budget_exceeded');continue
            for file in sorted(files):
                size=file.stat().st_size;total_bytes+=size
                if exceeded(size,config['limits']['source_bytes']) or exceeded(total_bytes,config['limits']['source_total_bytes']):
                    raise ValueError('source byte budget: path='+str(file)+'; expected source_bytes='+str(config['limits']['source_bytes'])+
                                     ', source_total_bytes='+str(config['limits']['source_total_bytes'])+'; actual file='+str(size)+', total='+str(total_bytes))
                relative=file.name if root.is_file() else file.relative_to(root).as_posix()
                inventory.append({'path':'sources/'+sid+'/'+relative,'sha256':file_digest(file),'bytes':file.stat().st_size,'mode':file.stat().st_mode&0o777})
            if source.get('sha256') and root.is_file() and file_digest(root)!=source['sha256']:
                add('source:'+sid,root,source['sha256'],file_digest(root),'source_digest_mismatch');continue
            inventories[sid]=inventory;roots.append((sid,root,files))
            add('source:'+sid,root,'retained readable files',{'files':len(files)})
            if snapshots is None and 'table' in source:
                add('source:'+sid,root,'expanded source snapshots','table expansion pending','source_acquisition_pending',False)
        except (OSError,ValueError) as exc:add('source:'+sid,root,'readable source within configured budgets',redact(str(exc)),'source_unreadable')
    if snapshots is not None and not roots:add('sources','snapshots','at least one readable snapshot',0,'source_unavailable')
    # No login/entitlement inference or auth-file inspection. Executability is a
    # prerequisite only; provider access remains explicitly unverified.
    backends={config.get('model',{}).get('backend','codex_cli')}
    api_native = config.get('model',{}).get('backend','codex_cli') == 'deepseek_api'
    if executable or api_native:
        present = find_spec('jsonschema') is not None
        add('host.python.jsonschema',sys.executable,'jsonschema available in the current interpreter',
            'available' if present else 'missing',None if present else 'host_dependency_missing',
            runtime_required or api_native,'No dependency is installed or repaired by readiness')
    if runtime_required:backends|={s.get('options',{}).get('backend','codex_cli') for _,s in specs}
    if 'codex_cli' in backends:
        from creation_pipeline.agent.command import codex_command
        try:add('model.backend','codex','resolvable executable',codex_command())
        except (ValueError,OSError) as exc:add('model.backend','codex','resolvable executable',redact(str(exc)),'model_client_unavailable')
    if 'deepseek_api' in backends:
        from creation_pipeline.runtime.deepseek_api import resolve
        try:
            resolve(timeout=1)
            add('model.backend','DEEPSEEK_API_KEY','valid local provider settings (credential value never emitted)',True)
        except ValueError as exc:
            add('model.backend','DEEPSEEK_API_KEY','valid local provider settings (credential value never emitted)',redact(str(exc)),'model_configuration_invalid')
    host=None
    if not offline:
        from creation_pipeline.runtime.local import LocalExecutor
        host=LocalExecutor().host()
        add('Docker','local-docker','available daemon',host,None if host.get('status')=='available' else 'docker_unavailable',runtime_required,
            'Required only for explicitly executable build; discovery/draft remain usable offline')
    else:add('Docker','local-docker','not probed in offline mode','not_checked','runtime_deferred',False)
    for scope,spec in specs:
        declaration=spec.get('shared_tool')
        if not declaration:continue
        try:
            st.validate_declaration(declaration)
            entry_paths=[a[len('/opt/skill/package/'):] for a in declaration['interface']['entrypoint'] if a.startswith('/opt/skill/package/') and a.endswith('.py')]
            if len(entry_paths)!=1:raise ValueError('interface.entrypoint: expected one concrete package Python script; actual='+repr(entry_paths))
            entry=entry_paths[0]
            matches=[(sid,r) for sid,r,_ in roots if r.is_dir() and (r/entry).is_file()]
            if not matches:
                if any(c['code']=='source_acquisition_pending' for c in checks):
                    add(scope,entry,'resolved source entry','acquisition pending','source_mapping_pending',False);continue
                raise ValueError('source entry mapping: expected exactly one source-relative '+entry+'; actual=missing')
            if len(matches)!=1:raise ValueError('source entry mapping: expected one source-relative '+entry+'; actual='+repr([s for s,_ in matches]))
            sid,root=matches[0]
            modules={p.stem for _,_,files in roots for p in files if p.suffix=='.py'}
            modules|={p.parent.name for _,_,files in roots for p in files if p.name=='__init__.py'}
            if declaration['policy'] in bd.PROFILES:bd.verify(root,declaration['bundled_data'])
            named={entry}|{i['module'] for i in declaration.get('bundled_data',[])};visited=set()
            while named-visited:
                name=sorted(named-visited)[0];visited.add(name)
                tree=ast.parse((root/name).read_text(encoding='utf-8-sig'),filename=str(root/name))
                st.validate_python(tree,name,declaration,modules,entry)
                # Follow only statically resolvable local imports. Full delivered
                # closure is still checked after authoring, before planning.
                for node in ast.walk(tree):
                    imports=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                    for imported in imports:
                        relative=Path(*imported.split('.'))
                        base=(root/name).parent if isinstance(node,ast.ImportFrom) and node.level else root
                        for candidate in (base/relative.with_suffix('.py'),base/relative/'__init__.py',(root/entry).parent/relative.with_suffix('.py')):
                            if candidate.is_file() and candidate.is_relative_to(root):named.add(candidate.relative_to(root).as_posix())
            add(scope+'.shared_tool',root/entry,'supported declared source structure',declaration['policy'])
        except (ValueError,OSError,SyntaxError,KeyError) as exc:
            add(scope+'.shared_tool',scope,'supported explicit source closure',redact(str(exc)),'tool_support_unresolved',runtime_required)
        reference=spec.get('tool_artifact')
        if reference:
            try:
                st.validate_reference(reference)
                path=st.registry_root()/(reference['request_key']+'-'+reference['artifact_id']+'.json')
                record=st.read_record(path)
                if record['request_key']!=reference['request_key'] or record['artifact_id']!=reference['artifact_id']:
                    raise ValueError('record reference identity differs')
                add(scope+'.tool_artifact',path,'verified concrete version',reference)
                if 'tool_compatibility' in spec:
                    from creation_pipeline.runtime.request_contracts import tool_payload, caller_context, REQUEST_PROTOCOL
                    known={'declaration':declaration,'request_protocol':REQUEST_PROTOCOL,'tool_compatibility':tool_payload(spec,caller_context(config))}
                else:
                    known={'declaration':declaration,'requirements':spec.get('requirements',[config.get('prompt','')]+list(config.get('constraints') or [])),
                           'constraints':spec.get('constraints',[])}
                for field,value in known.items():
                    if record['request'].get(field)!=value:
                        add(scope+'.tool_artifact.'+field,path,record['request'].get(field),value,'tool_request_mismatch',runtime_required)
                if snapshots is not None or not any(c['code']=='source_acquisition_pending' for c in checks):
                    old={i['path']:i for i in record['request']['files'] if i['path'].startswith('sources/')}
                    actual={i['path']:i for items in inventories.values() for i in items}
                    for name in sorted(set(old)|set(actual)):
                        if old.get(name)!=actual.get(name):add('ToolArtifact source',name,old.get(name),actual.get(name),'tool_source_mismatch',runtime_required)
                if host and host.get('status')=='available':
                    from creation_pipeline.runtime.local import process
                    state=st.available(record,host,process,verify_external=False)
                    add(scope+'.tool_artifact.image',record['image_id'],'available on '+record['daemon_id'],state,
                        None if state=='available' else 'external_identity_deferred' if state=='external_identity_not_observed' else 'tool_artifact_unavailable',
                        runtime_required and state!='external_identity_not_observed')
                else:add(scope+'.tool_artifact.image',record['image_id'],'current availability','not_checked','artifact_availability_deferred',False)
            except (ValueError,OSError,KeyError,TypeError) as exc:
                add(scope+'.tool_artifact',reference,'valid present concrete version',redact(str(exc)),'tool_artifact_unavailable',runtime_required)
    blocked=[c for c in checks if c['status']=='blocked']
    deferred=[c for c in checks if c['status']=='deferred']
    return sanitized({'version':1,'status':'blocked' if blocked else 'deferred' if deferred else 'ready',
        'mode':mode,'scope':'observed prerequisites only; source/delivery closure and provider entitlement remain subject to later gates',
        'runtime_required':runtime_required,'checks':checks,'gaps':blocked,'model_calls':0,'build_calls':0,
        'qualification':'not_granted','source_acquisition_pending':any(c['code']=='source_acquisition_pending' for c in checks)})


def configuration_error(path,mode,exc):
    return sanitized({'version':1,'status':'blocked','mode':mode,'model_calls':0,'build_calls':0,'qualification':'not_granted',
        'gaps':[{'object':'configuration','path':str(path),'expected':'valid readable configuration','actual':redact(str(exc)),
                 'code':'configuration_invalid','status':'blocked'}]})


def from_config(path,mode='build',offline=False):
    from creation_pipeline.models import load_config
    try:return check(load_config(path),mode,offline=offline)
    except (ValueError,OSError,KeyError) as exc:
        return configuration_error(path,mode,exc)
