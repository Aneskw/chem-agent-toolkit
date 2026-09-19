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

def validate(response,bundle):
    check(response,SCHEMA)
    if response['paper_id']!=bundle['paper_id']: raise ValueError('paper_id does not match source bundle')
    if not response['candidates'] and not response['no_skill_reason'].strip(): raise ValueError('No candidates requires a reason')
    names=[c['name'] for c in response['candidates']]
    if len(names)!=len(set(names)): raise ValueError('Duplicate candidate names')
    sources={s['id']:s for s in bundle['sources']}
    results=[]
    for candidate in response['candidates']:
        claims=candidate['inputs']+candidate['outputs']+candidate['steps']+[r['reason'] for r in candidate['requirements']]
        paper_cited=False
        for claim in claims:
            for citation in claim['citations']:
                source=sources.get(citation['source_id'])
                if source is None: raise ValueError('Unknown source_id: '+citation['source_id'])
                start,end=citation['start'],citation['end']
                if not 1<=start<=end<=len(source['lines']): raise ValueError('Citation line range outside source')
                if end-start>25: raise ValueError('Citation range too broad; use at most 26 lines')
                excerpt='\n'.join(source['lines'][start-1:end])
                if citation['quote'] not in excerpt: raise ValueError('Citation quote not found in referenced lines')
                if source['role']=='paper' and claim in candidate['steps']:paper_cited=True
        if candidate['kind']=='method_procedure' and not paper_cited:
            raise ValueError('method_procedure needs a citation to supplied paper text, not metadata or README alone')
        missing=[];external=[]
        for requirement in candidate['requirements']:
            raw_path=requirement['path']
            if requirement['kind']=='external_asset' and raw_path.startswith('https://'):
                parsed=urlsplit(raw_path)
                if not parsed.hostname or parsed.username or parsed.password or '..' in PurePosixPath(parsed.path).parts:
                    raise ValueError('Unsafe external resource URL')
                external.append(raw_path)
                continue
            path=PurePosixPath(raw_path)
            if path.is_absolute() or '..' in path.parts or '\\' in str(path) or ':' in str(path): raise ValueError('Unsafe resource path')
            if requirement['kind']=='repo_file' and str(path) not in bundle['repo_files']:
                missing.append(str(path))
            if requirement['kind']=='external_asset':external.append(str(path))
        results.append({'name':candidate['name'],'state':'blocked_resources' if missing else 'draft_unexecuted',
            'missing_repo_files':missing,'external_assets_unverified':external,
            'checks':'Schema and citation text/location checked; semantic completeness and execution NOT verified.'})
    return results
