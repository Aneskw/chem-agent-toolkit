"""Small explicit JSON contract and deterministic provenance checks."""
import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit

def obj(properties, required=None):
    return {'type':'object','properties':properties,'required':required or list(properties),'additionalProperties':False}

TEXT={'type':'string','minLength':1,'maxLength':3000}
CITATION=obj({'source_id':TEXT,'start':{'type':'integer','minimum':1},'end':{'type':'integer','minimum':1},
              'quote':{'type':'string','minLength':8,'maxLength':240}})
CLAIM=obj({'text':TEXT,'citations':{'type':'array','minItems':1,'maxItems':5,'items':CITATION}})
CLAIMS={'type':'array','minItems':1,'maxItems':15,'items':CLAIM}
CANDIDATE=obj({'name':{'type':'string','pattern':'^[a-z0-9]+(?:-[a-z0-9]+)*$','maxLength':63},
    'description':TEXT,'kind':{'type':'string','enum':['tool_usage','method_procedure']},
    'operation':TEXT,'inputs':CLAIMS,'outputs':CLAIMS,'steps':CLAIMS,
    'requirements':{'type':'array','maxItems':30,'items':obj({'path':TEXT,'kind':{'type':'string','enum':['repo_file','external_asset']},'reason':CLAIM})},
    'unknowns':{'type':'array','maxItems':20,'items':TEXT}})
SCHEMA=obj({'schema_version':{'type':'integer','enum':[1]},'paper_id':TEXT,
    'candidates':{'type':'array','maxItems':4,'items':CANDIDATE},
    'no_skill_reason':{'type':'string','maxLength':3000}})

# Version 1 remains replayable. Version 2 makes the behavior change explicit;
# a citation match is still not a semantic review or an agent-utility result.
DECISION=obj({
    'when':TEXT, 'requires':TEXT, 'choose':TEXT, 'avoid':TEXT,
    'because':TEXT, 'check':TEXT, 'stop_or_fallback':TEXT, 'scope':TEXT,
    'support':{'type':'string','enum':['direct','inferred']},
    'citations':{'type':'array','minItems':1,'maxItems':8,'items':CITATION}})
RESOURCE_MANIFEST_ITEM=obj({
    'path':TEXT,
    'kind':{'type':'string','enum':['source_code','preprocessing','dataset','checkpoint','endpoint','dependency']},
    'source_url':{'type':'string','maxLength':3000},
    'source_revision':{'type':'string','maxLength':3000},
    'sha256':{'type':'string','pattern':'^(?:[0-9a-fA-F]{64})?$'},
    'restore_command':{'type':'string','maxLength':3000},
    'status':{'type':'string','enum':['present','download_required','user_supplied','blocked_resources','unverified']},
    'citations':{'type':'array','minItems':1,'maxItems':5,'items':CITATION}
}, required=['path','kind','source_url','source_revision','sha256','restore_command','status','citations'])
CANDIDATE_V2=obj({**CANDIDATE['properties'],
    'decisions':{'type':'array','maxItems':8,'items':DECISION},
    'resource_manifest':{'type':'array','maxItems':30,'items':RESOURCE_MANIFEST_ITEM}
}, required=list(CANDIDATE['properties'])+['decisions','resource_manifest'])
SCHEMA_V2=obj({**SCHEMA['properties'],
    'schema_version':{'type':'integer','enum':[2]},
    'candidates':{'type':'array','maxItems':4,'items':CANDIDATE_V2}})

def schema_for(version):
    if version == 1:return SCHEMA
    if version == 2:return SCHEMA_V2
    raise ValueError('Unsupported extraction schema version')

def check(value,schema,path='$'):
    kind=schema['type'];expected={'object':dict,'array':list,'string':str,'integer':int}[kind]
    if type(value) is not expected: raise ValueError(f'{path}: expected {kind}')
    if 'enum' in schema and value not in schema['enum']: raise ValueError(f'{path}: unsupported value')
    if kind=='object':
        missing=set(schema['required'])-set(value)
        extra=set(value)-set(schema['properties'])
        if missing or extra: raise ValueError(f'{path}: missing={sorted(missing)}, extra={sorted(extra)}')
        for key,child in value.items(): check(child,schema['properties'][key],path+'.'+key)
    elif kind=='array':
        if not schema.get('minItems',0)<=len(value)<=schema.get('maxItems',10000): raise ValueError(path+': invalid item count')
        for i,child in enumerate(value): check(child,schema['items'],f'{path}[{i}]')
    elif kind=='string':
        if not schema.get('minLength',0)<=len(value.strip())<=schema.get('maxLength',100000): raise ValueError(path+': invalid string length')
        if 'pattern' in schema and not re.fullmatch(schema['pattern'],value): raise ValueError(path+': invalid name')
    elif kind=='integer' and value<schema.get('minimum',value): raise ValueError(path+': integer below minimum')

def reconcile_resources(response,bundle):
    """Replace model guesses with the pinned inventory's observed availability."""
    catalog={item['path']:item for item in bundle.get('resource_catalog',[])}
    changes=[]
    for candidate in response.get('candidates',[]):
        for resource in candidate.get('resource_manifest',[]):
            item=catalog.get(resource['path'])
            if item:
                old=(resource['status'],resource['source_url'],resource['sha256'])
                resource['source_url']=item['source_url']
                resource['source_revision']=bundle['commit']
                resource['sha256']=item['local_sha256']
                resource['status']=('present' if item['local_present'] else
                                    'download_required' if item['source_url'] else 'blocked_resources')
                resource['restore_command']=(f'included at {resource["path"]}' if item['local_present'] else
                    f'curl -L {item["source_url"]} -o {resource["path"]}' if item['source_url'] else '')
                if old!=(resource['status'],resource['source_url'],resource['sha256']):
                    changes.append({'candidate':candidate['name'],'path':resource['path'],
                                    'availability':resource['status']})
            elif resource['status']=='present':
                resource['status']='unverified'
                resource['sha256']=''
                note='Resource not confirmed in local intake: '+resource['path']
                if note not in candidate['unknowns']:candidate['unknowns'].append(note)
                changes.append({'candidate':candidate['name'],'path':resource['path'],
                                'availability':'unverified'})
    return response,changes

DATA_SUFFIXES={'.csv','.tsv','.json','.jsonl','.parquet','.arrow','.sqlite',
               '.sqlite3','.db','.sdf','.smi','.smiles','.mol','.mol2','.pkl',
               '.pickle','.h5','.hdf5','.npz','.npy','.zip','.gz','.tar',
               '.tgz','.7z','.xz','.bz2'}

def direct_dataset(item,catalog):
    if item['status']=='present':
        pinned=catalog.get(item['path'])
        return bool(pinned and pinned['local_present'])
    if item['status']!='download_required' or not item['restore_command']:
        return False
    url=item['source_url']
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or url not in item['restore_command']:
        return False
    path=parsed.path.lower()
    return (any(path.endswith(suffix) for suffix in DATA_SUFFIXES) or
            path.endswith('/download') or '/ndownloader/files/' in path or
            '/api/files/' in path)

def validate(response,bundle):
    check(response,schema_for(response.get('schema_version')))
    if response['paper_id']!=bundle['paper_id']: raise ValueError('paper_id does not match source bundle')
    if not response['candidates'] and not response['no_skill_reason'].strip(): raise ValueError('No candidates requires a reason')
    names=[c['name'] for c in response['candidates']]
    if len(names)!=len(set(names)): raise ValueError('Duplicate candidate names')
    sources={s['id']:s for s in bundle['sources']}
    catalog={item['path']:item for item in bundle.get('resource_catalog',[])}
    local_files=set(bundle.get('local_repo_files',[]))
    results=[]
    for candidate in response['candidates']:
        decisions=candidate.get('decisions',[])
        if response['schema_version']==2:
            if candidate['kind']=='method_procedure' and not decisions:
                raise ValueError('A method procedure must change at least one decision')
            if candidate['kind']=='tool_usage' and decisions:
                raise ValueError('Atomic tool operations must not claim method decision rules')
        manifest=candidate.get('resource_manifest',[])
        resource_claims=[{'text':item['path'],'citations':item['citations']} for item in manifest]
        claims=candidate['inputs']+candidate['outputs']+candidate['steps']+[r['reason'] for r in candidate['requirements']]+decisions+resource_claims
        authoritative_cited=False
        primary_role=bundle.get('primary_role','paper')
        # The source document and code pinned by the intake are both primary
        # evidence for an executable method. Repository prose alone is not:
        # it may explain intent, but it cannot establish implementation.
        authoritative_roles={primary_role,'repo_code'}
        for claim in claims:
            for citation in claim['citations']:
                source=sources.get(citation['source_id'])
                if source is None: raise ValueError('Unknown source_id: '+citation['source_id'])
                start,end=citation['start'],citation['end']
                if not 1<=start<=end<=len(source['lines']): raise ValueError('Citation line range outside source')
                if end-start>25: raise ValueError('Citation range too broad; use at most 26 lines')
                excerpt='\n'.join(source['lines'][start-1:end])
                if citation['quote'] not in excerpt: raise ValueError('Citation quote not found in referenced lines')
                if source['role'] in authoritative_roles and claim in candidate['steps']:
                    authoritative_cited=True
        for rule in decisions:
            if not any(sources[c['source_id']]['role'] in authoritative_roles for c in rule['citations']):
                raise ValueError('Each decision rule needs source-document or pinned-code evidence, not a README-only rationale')
        if candidate['kind']=='method_procedure' and not authoritative_cited:
            raise ValueError(f'method_procedure needs a step citation to supplied {primary_role} or pinned code, not metadata or README alone')
        missing=[];external=[]
        for requirement in candidate['requirements']:
            raw_path=requirement['path']
            if (requirement['kind']=='external_asset' and bundle.get('source_type')=='database'
                    and raw_path.startswith('/') and not raw_path.startswith('//')):
                # API route templates such as /molecule/:id are identifiers in
                # database documentation, never local files to open/execute.
                if '..' in PurePosixPath(urlsplit(raw_path).path).parts or '\\' in raw_path:
                    raise ValueError('Unsafe API route template')
                external.append(raw_path)
                continue
            if requirement['kind']=='external_asset' and raw_path.startswith('https://'):
                parsed=urlsplit(raw_path)
                if not parsed.hostname or parsed.username or parsed.password or '..' in PurePosixPath(parsed.path).parts:
                    raise ValueError('Unsafe external resource URL')
                external.append(raw_path)
                continue
            if requirement['kind']=='external_asset' and ': ' in raw_path:
                # A cited publication/resource label is descriptive metadata,
                # not a filesystem path. Preserve it without dereferencing it.
                if raw_path.startswith(('/', '\\')) or re.match(r'^[A-Za-z]:',raw_path) or '://' in raw_path:
                    raise ValueError('Unsafe external resource identifier')
                external.append(raw_path)
                continue
            path=PurePosixPath(raw_path)
            if path.is_absolute() or '..' in path.parts or '\\' in str(path) or ':' in str(path): raise ValueError('Unsafe resource path')
            if requirement['kind']=='repo_file' and str(path) not in bundle['repo_files']:
                missing.append(str(path))
            if requirement['kind']=='external_asset':external.append(str(path))
        # A generated Skill must carry an actionable recovery record for every
        # external asset. Older candidates without external assets remain
        # replayable; new resource-dependent candidates cannot silently omit
        # source, version, hash, and restore information.
        if external and not manifest:
            raise ValueError('External resources require resource_manifest with source, revision, hash, and restore command')
        for resource in manifest:
            pinned=catalog.get(resource['path'])
            path=PurePosixPath(resource['path'])
            if resource['kind']=='endpoint' and resource['path'].startswith('https://'):
                parsed=urlsplit(resource['path'])
                if not parsed.hostname or parsed.username or parsed.password or '..' in PurePosixPath(parsed.path).parts:
                    raise ValueError('Unsafe resource manifest URL: '+resource['path'])
            elif path.is_absolute() or '..' in path.parts or '\\' in resource['path'] or '://' in resource['path']:
                raise ValueError('Unsafe resource manifest path: '+resource['path'])
            if resource['status']=='present' and not resource['sha256']:
                raise ValueError('Present resources require a SHA-256 hash')
            if resource['status']=='present' and not (pinned and pinned['local_present']):
                raise ValueError('Present resource is not verified in local intake: '+resource['path'])
            if resource['status']=='present' and resource['path'] in bundle.get('repo_files',[]) and resource['path'] not in local_files:
                raise ValueError('Remote repository inventory is not a present local resource: '+resource['path'])
            if pinned and resource['status']=='present' and resource['sha256']!=pinned['local_sha256']:
                raise ValueError('Present repository resource hash differs from local file: '+resource['path'])
            if resource['status'] in {'download_required','user_supplied'} and not resource['source_url']:
                raise ValueError('Unresolved resources require a source_url or explicit acquisition record')
            if pinned and resource['status']=='download_required' and resource['source_url']!=pinned['source_url']:
                raise ValueError('Repository download URL must target the pinned commit: '+resource['path'])
        def available(item):
            return (item['status'] in {'present','download_required'} and
                    bool(item['source_url']) and
                    (item['kind']=='endpoint' or bool(item['restore_command'])))
        source_type=bundle.get('source_type','paper')
        missing_category=[]
        required_kinds={'database':{'dataset','endpoint'},
                        'tool':{'source_code','endpoint','dependency'}}.get(source_type)
        if required_kinds and not any(item['kind'] in required_kinds and available(item)
                                      for item in manifest):
            missing_category.append('dataset_or_endpoint' if source_type=='database' else 'tool_code_or_acquisition')
        needs_dataset=(bundle.get('data_capability')=='downloadable_dataset' or
                       (source_type=='database' and
                        any(item['kind']=='dataset' for item in manifest)))
        if needs_dataset and not any(item['kind']=='dataset' and direct_dataset(item,catalog)
                                     for item in manifest):
            missing_category.append('downloadable_dataset')
        inference_text=' '.join(candidate[key] for key in ('name','description','operation')).lower()
        model_inference=(candidate['kind']=='method_procedure' and
                         (bundle.get('model_capability')=='single_step_inference' or
                          (bundle.get('source_type')=='model' and
                           (any(item['kind']=='checkpoint' for item in manifest) or
                            any(word in inference_text for word in
                                ('predict','infer','retrosynth','reactant','precursor'))))))
        absent=[]
        if model_inference:
            for kind in ('source_code','preprocessing','checkpoint'):
                entries=[item for item in manifest if item['kind']==kind]
                if not entries or not any(item['status'] in {'present','download_required'} and
                                           item['source_url'] and item['restore_command'] for item in entries):
                    absent.append(kind)
        blocked=bool(missing or absent or missing_category or
                     any(item['status'] in {'blocked_resources','unverified','user_supplied'}
                                            for item in manifest))
        results.append({'name':candidate['name'],'state':'blocked_resources' if blocked else 'draft_unexecuted',
            'missing_repo_files':missing,'external_assets_unverified':external,
            'missing_model_resources':absent,
            'missing_category_resources':missing_category,
            'resource_manifest_entries':len(manifest),
            'checks':'Schema and citation text/location checked; semantic completeness and execution NOT verified.'})
    return results
