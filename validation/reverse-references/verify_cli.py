"""Public read-only CLI over real libraries; mutations are isolated fixture copies."""
import copy
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from creation_pipeline.management import API_VERSION
from creation_pipeline.records import read_json,write_json,redact,file_digest,now
from creation_pipeline.artifacts.package import manifest


def main():
    root=Path(sys.argv[1]).resolve();root.mkdir(exist_ok=False)
    original=Path(sys.argv[2]).resolve();managed=Path(sys.argv[3]).resolve()
    libraries=[original/x/'library' for x in ('a','b')]+[managed/x/'library' for x in ('a','b')]+[managed/'missing-image-library']
    tool_root=original/'shared-tools';env_root=original/'shared-environments'
    subjects=[*libraries,tool_root,env_root]
    before={str(p):manifest(p) for p in subjects}
    timestamps={str(p):p.stat().st_mtime_ns for subject in subjects for p in subject.rglob('*') if p.is_file()}
    write_json(root/'inputs-before.json',before)
    write_json(root/'implementation.json',{p.as_posix():file_digest(p) for p in sorted((REPO/'creation_pipeline').rglob('*.py'))})
    artifact=read_json(next(tool_root.glob('*.json')))
    tool=dict(kind='tool',**{k:artifact[k] for k in ('request_key','artifact_id')})
    environment=dict(kind='environment',**{k:artifact['environment'][k] for k in ('recipe_key','image_id','daemon_id')})
    params={'libraries':list(map(str,libraries)),'tool_registries':[str(tool_root)],'environment_registries':[str(env_root)],'target':tool}
    guard=root/'guard';guard.mkdir()
    compiled=subprocess.run(['C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe','/nologo','/out:'+str(guard/'docker.exe'),str(REPO/'validation/v3-delivery/CliGuard.cs')],capture_output=True,text=True)
    assert compiled.returncode==0,redact(compiled.stderr)
    shutil.copyfile(guard/'docker.exe',guard/'codex.exe')
    env=os.environ.copy();env['PATH']=str(guard)+os.pathsep+env['PATH'];env['CHEM_PROBE_REAL_DOCKER']=shutil.which('docker') or ''
    operations=[]
    def run(label,settings):
        dest=root/'operations'/label;dest.mkdir(parents=True)
        write_json(dest/'request.json',{'api_version':API_VERSION,'request_id':label,'operation':'references.query','params':settings})
        roots=[Path(p) for field in ('libraries','tool_registries','environment_registries') for p in settings[field] if Path(p).is_dir()]
        snapshots={str(p):manifest(p) for p in roots}
        e=env.copy();e['CHEM_PROBE_COUNTER']=str(dest/'counter.txt')
        command=[sys.executable,'-m','creation_pipeline','manage',str(dest/'request.json')]
        start=time.monotonic();process=subprocess.run(command,cwd=REPO,env=e,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (dest/'stdout.json').write_text(redact(process.stdout),encoding='utf-8');(dest/'stderr.log').write_text(redact(process.stderr),encoding='utf-8')
        result=read_json(dest/'stdout.json');marks=(dest/'counter.txt').read_text() if (dest/'counter.txt').exists() else ''
        receipt={'command':command,'seconds':time.monotonic()-start,'exit_code':process.returncode,
                 'models':marks.count('M'),'builds':marks.count('B'),'docker':marks.count('D'),
                 'bindings':len(result.get('data',{}).get('matches',{}).get('bindings',[])),
                 'tools':len(result.get('data',{}).get('matches',{}).get('tools',[])),
                 'attempts':len(result.get('data',{}).get('matches',{}).get('attempts',[])),
                 'issues':result.get('data',{}).get('issues',[])}
        write_json(dest/'result.json',receipt);operations.append({'label':label,**receipt})
        assert process.returncode==0 and result['ok'] and not marks,(label,receipt)
        assert all(manifest(p)==snapshots[str(p)] for p in roots),(label,'query changed inputs')
        assert result['data']['qualification'] is None and result['data']['availability'] is None
        assert not result['data']['scope']['global_complete']
        assert not any(v for k,v in result['side_effects'].items() if k!='filesystem_reads')
        return result['data']
    all_tool=run('tool-real-libraries',params)
    assert all_tool['scope']['complete_within_declared_layouts'],[(i['code'],i['field'],i['path']) for i in all_tool['issues']]
    assert len(all_tool['matches']['bindings'])==5
    assert any(a['recorded_execution_status']=='runtime_blocked' for a in all_tool['matches']['attempts'])
    all_env=run('environment-real-libraries',dict(params,target=environment))
    assert len(all_env['matches']['tools'])==1 and len(all_env['matches']['bindings'])==5
    repeated=run('rebuilt-index',params)
    assert all_tool['matches']==repeated['matches'] and all_tool['index']==repeated['index']
    subset=dict(params,libraries=[str(libraries[0])],tool_registries=[],environment_registries=[])
    observed=run('only-explicit-one-library',subset)
    assert len(observed['matches']['bindings'])==1 and observed['target_registration']['status']=='not_scanned'
    registry_only=run('libraries-unscanned',dict(params,libraries=[]))
    assert registry_only['matches']['bindings']==[] and 'libraries' in registry_only['scope']['unscanned_categories']
    absent=run('other-concrete-tool',dict(params,target=dict(tool,artifact_id='0'*64)))
    assert absent['matches']=={'tools':[],'bindings':[],'attempts':[]}
    absent_env=run('other-concrete-environment',dict(params,target=dict(environment,image_id='sha256:'+'0'*64)))
    assert absent_env['matches']=={'tools':[],'bindings':[],'attempts':[]}
    missing=root/'missing-library'
    partial=run('missing-library',dict(params,libraries=[*params['libraries'],str(missing)]))
    assert len(partial['matches']['bindings'])==5 and not partial['scope']['complete_within_declared_layouts'] and not missing.exists()
    broken=root/'broken-library';broken.mkdir();(broken/'catalog.json').write_text('{broken')
    partial=run('corrupt-catalog',dict(params,libraries=[str(broken)]))
    assert any('JSONDecodeError' in i['reason'] for i in partial['issues'])
    bad_tools=root/'bad-tools';bad_tools.mkdir();bad=copy.deepcopy(artifact);bad['image_id']='sha256:'+'0'*64
    write_json(bad_tools/next(tool_root.glob('*.json')).name,bad)
    partial=run('corrupt-tool-record',dict(params,tool_registries=[str(bad_tools)]))
    assert len(partial['matches']['bindings'])==5 and partial['target_registration']['status']=='not_found_in_scanned_roots'
    empty_env=root/'empty-environments';empty_env.mkdir()
    partial=run('environment-record-not-in-scope',dict(params,target=environment,environment_registries=[str(empty_env)]))
    assert len(partial['matches']['bindings'])==5 and any(i['code']=='environment_record_not_found_in_scope' for i in partial['issues'])
    pending=root/'pending-library';shutil.copytree(libraries[0],pending)
    (pending/'.catalog.lock').write_text('foreign-owner');(pending/'.transaction.json').write_text('{pending')
    partial=run('foreign-lock-and-journal',dict(params,libraries=[str(pending)]))
    assert len(partial['matches']['bindings'])==1 and any(i['code']=='catalog_pending' for i in partial['issues'])
    transient=root/'transient-tools';transient.mkdir();(transient/'request.lock').write_text('foreign-owner');(transient/'request.json.tmp').write_text('{partial')
    partial=run('unfinished-publication',dict(params,tool_registries=[str(transient)]))
    assert any(i['code']=='publication_pending' for i in partial['issues']) and partial['target_registration']['status']=='not_found_in_scanned_roots'
    drift=root/'drift-library';shutil.copytree(libraries[0],drift)
    entry=read_json(drift/'catalog.json')['skills'][0]
    resource=next(f['path'] for f in artifact['request']['files'] if f['path'].startswith('package/') and f['path'].endswith('.json'))
    (drift/entry['evidence']/'runtime/context'/resource).write_text('{changed-resource}')
    partial=run('frozen-resource-drift',dict(params,libraries=[str(drift)]))
    assert not partial['matches']['bindings'] and partial['unresolved_bindings'] and any(i['field']=='freeze.files' for i in partial['issues'])
    assert all(manifest(p)==before[str(p)] for p in subjects)
    assert all(Path(p).stat().st_mtime_ns==stamp for p,stamp in timestamps.items())
    write_json(root/'results.json',{'at':now(),'passed':True,'models':0,'builds':0,'docker':0,'business_executions':0,
        'scanned_libraries':list(map(str,libraries)),'tool_target':tool,'environment_target':environment,
        'confirmed_bindings':len(all_tool['matches']['bindings']),'attempts':len(all_tool['matches']['attempts']),
        'original_bytes_and_file_mtimes_unchanged':True,'each_query_input_bytes_unchanged':True,'operations':operations})
    print({'passed':True,'operations':len(operations),'bindings':len(all_tool['matches']['bindings']),'attempts':len(all_tool['matches']['attempts']),'models':0,'docker':0})


if __name__=='__main__':main()
