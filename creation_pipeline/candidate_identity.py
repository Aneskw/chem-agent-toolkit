"""Stable source-cited candidate identity and explicit caller-owned tool selection."""
from pathlib import Path
from runtime_common import digest, read, write


def cited_sources(value):
    result=set()
    if isinstance(value,dict):
        if 'source_id' in value:result.add(value['source_id'])
        for item in value.values():result.update(cited_sources(item))
    elif isinstance(value,list):
        for item in value:result.update(cited_sources(item))
    return result


def identity(candidate,bundle,job_id):
    # Directory/name is presentation; identity survives a deterministic rename.
    content={k:v for k,v in candidate.items() if k!='name'}
    source_ids=sorted(cited_sources(candidate))
    basis={'job_id':job_id,'candidate':content,'sources':{s['id']:s['sha256'] for s in bundle['sources'] if s['id'] in source_ids}}
    return {'schema_version':1,'candidate_id':'candidate-'+digest(basis)[:24],'job_id':job_id,
            'kind':candidate['kind'],'source_ids':source_ids,'identity_basis':basis}


def load(candidate):
    path=Path(candidate)/'candidate.json'
    if not path.exists():return None
    value=read(path)
    if value['candidate_id']!='candidate-'+digest(value['identity_basis'])[:24]:raise ValueError('Candidate identity checksum mismatch')
    basis=value['identity_basis']
    if value['job_id']!=basis['job_id'] or value['kind']!=basis['candidate']['kind'] or value['source_ids']!=sorted(cited_sources(basis['candidate'])):
        raise ValueError('Candidate identity metadata differs from its cited basis')
    return value


def resolve(settings,candidate,job_id):
    if not isinstance(settings.get('bindings'),list) or any(not isinstance(b,dict) for b in settings['bindings']):raise ValueError('bindings must be a list of explicit rule objects')
    exact=[b for b in settings['bindings'] if b.get('job_id')==job_id and b.get('candidate')==Path(candidate).name]
    if exact:
        matches=exact;method='exact_candidate'
    else:
        value=load(candidate);matches=[];method='cited_source_selector'
        if value and value['job_id']!=job_id:raise ValueError('Candidate identity belongs to another job')
        for rule in settings['bindings']:
            selector=rule.get('selector')
            if selector is None:continue
            if not isinstance(selector,dict):raise ValueError('selector must be an object')
            if set(selector)-{'job_id','source_ids','source_ids_any','candidate_id','kind'} or not selector.get('job_id') or not (selector.get('source_ids') or selector.get('source_ids_any') or selector.get('candidate_id')):
                raise ValueError('Selectors require job_id plus cited source_ids or candidate_id; job-wide wildcard binding is disallowed')
            ids=selector.get('source_ids',[])
            if not isinstance(ids,list) or not all(isinstance(x,str) for x in ids):raise ValueError('Selector source_ids must be a string list')
            any_ids=selector.get('source_ids_any',[])
            if not isinstance(any_ids,list) or not all(isinstance(x,str) for x in any_ids):raise ValueError('Selector source_ids_any must be a string list')
            if not value or selector['job_id']!=job_id:continue
            if selector.get('candidate_id',value['candidate_id'])!=value['candidate_id']:continue
            if selector.get('kind',value['kind'])!=value['kind']:continue
            if not set(ids)<=set(value['source_ids']):continue
            if any_ids and not set(any_ids)&set(value['source_ids']):continue
            matches.append(rule)
    if len(matches)!=1:raise ValueError('Tool association '+('ambiguous' if matches else 'unresolved')+': expected one explicit binding, found '+str(len(matches)))
    binding=matches[0]
    if method!='exact_candidate' and any(key not in settings['tools'] for key in binding.get('tools',[])):raise ValueError('Binding references an undeclared tool')
    return binding,{'method':method,'binding':binding,'candidate_id':(load(candidate) or {}).get('candidate_id')}
