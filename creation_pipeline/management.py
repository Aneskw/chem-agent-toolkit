"""Versioned local DTO facade over the existing tool/store/execution chain.

Paths are trusted local operator inputs, not tenant or HTTP resource locators.
request_id is correlation only: execution is intentionally not deduplicated.
"""
import copy
import json
from pathlib import Path
import re

from creation_pipeline.artifacts import store
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import fingerprint
from creation_pipeline.records import read_json, file_digest, safe_relative, has_link, now, sanitized
from creation_pipeline.runtime import shared_tool as tools, request_contracts, planner
from creation_pipeline.runtime.local import LocalExecutor, process
from creation_pipeline.runtime.preparation import bind
from creation_pipeline.runtime.service import resume_build

API_VERSION = 'chem-local-management/v1'
DESCRIPTOR_REQUIRED = {'context', 'entry', 'declaration'}
DESCRIPTOR_OPTIONAL = {'requirements', 'constraints', 'runtime_limits', 'tool_compatibility', 'caller_constraints'}
OPERATIONS = {
    'tool.describe': (DESCRIPTOR_REQUIRED, DESCRIPTOR_OPTIONAL),
    'tool.resolve': ({'descriptor', 'request_key'}, {'registry'}),
    'tool.select': ({'descriptor', 'request_key', 'reference'}, {'registry'}),
    'tool.availability': ({'reference'}, {'registry', 'offline'}),
    'skill.execute': ({'library', 'name', 'expected_revision', 'expected_freeze_sha256'}, set()),
    'skill.qualification': ({'library', 'name'}, {'offline'}),
    'references.query': ({'libraries','tool_registries','environment_registries','target'}, set()),
}


class ManagementError(ValueError):
    def __init__(self, code, reason, *, object=None, field=None, expected=None, actual=None, raw=None, source_refs=None):
        super().__init__(reason)
        self.code, self.object, self.field = code, object, field
        self.expected, self.actual, self.raw = expected, actual, raw
        self.source_refs = source_refs or []


def _fields(value, required, optional, field):
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - optional:
        raise ManagementError('request_invalid', 'Missing or unsupported fields', field=field,
                              expected={'required': sorted(required), 'optional': sorted(optional)}, actual=value)


def _path(value, field, *, directory=False):
    if not isinstance(value, str) or not value or not Path(value).is_absolute() or has_link(value):
        raise ManagementError('request_invalid', 'Expected absolute unlinked local path', field=field, expected='absolute unlinked local path', actual=value)
    result = Path(value)
    if directory and not result.is_dir():
        raise ManagementError('not_found', 'Local directory not found', object=value, field=field, expected='existing directory', actual='missing')
    return result


def _sha(value, field, prefix=''):
    if not isinstance(value, str) or not re.fullmatch(re.escape(prefix) + '[0-9a-f]{64}', value):
        raise ManagementError('request_invalid', 'Invalid identity', field=field, expected=prefix+'<64 lowercase hex>', actual=value)


def _effects(operation, offline):
    catalog = operation.startswith('skill.') and not offline
    execute = operation == 'skill.execute'
    docker = operation in {'tool.resolve', 'tool.select', 'skill.execute'} or operation in {'tool.availability', 'skill.qualification'} and not offline
    return {'filesystem_reads': True, 'docker_observation': docker, 'ephemeral_probe_containers_possible': docker,
            'catalog_lock_recovery_or_reconciliation_possible': catalog, 'writes_attempt_evidence': execute,
            'executes_locked_business_cases': execute, 'builds': False, 'model_calls': False,
            'request_id_deduplicates_execution': False}


def _ref(path, kind):
    path = Path(path)
    try: sha = file_digest(path) if not has_link(path) and path.is_file() else None
    except OSError: sha = None
    return {'path': str(path), 'kind': kind, 'sha256': sha}


def _entry_refs(root, name, snapshot=None):
    refs = [_ref(root/'catalog.json', 'catalog_snapshot')]
    try: entry = snapshot if snapshot is not None else next((e for e in store.catalog(root)['skills'] if e['name'] == name), None)
    except (ValueError,OSError,KeyError,TypeError): return refs
    if entry:
        for file in ('freeze.json', 'record.json'):
            refs.append(_ref(safe_relative(root, entry['evidence'])/file, 'frozen_input'))
        for key in ('runtime', 'pending_runtime'):
            if entry.get(key):
                attempt = safe_relative(root, entry[key]['path'])
                for file in ('attempt-start.json', 'receipt.json', 'build-log.json', 'execution/report.json'):
                    path = safe_relative(attempt, file)
                    if path.is_file(): refs.append(_ref(path, key+'_evidence'))
    return refs


def _describe(params):
    _fields(params, DESCRIPTOR_REQUIRED, DESCRIPTOR_OPTIONAL, 'descriptor')
    root = _path(params['context'], 'context', directory=True)
    entry = params['entry']
    if not isinstance(entry,str): raise ManagementError('request_invalid','entry must be a relative script path',field='entry',actual=entry)
    safe_relative(root/'package', entry)
    sources_root = safe_relative(root, 'sources')
    sources = []
    if not sources_root.is_dir(): raise ValueError('Descriptor sources directory is missing: '+str(sources_root))
    for source in sorted(sources_root.iterdir()):
        if has_link(source) or not source.is_dir(): raise ValueError('Descriptor requires unlinked source-id directories: '+str(source))
        sources.append({'id':source.name,'path':str(source),'inventory':manifest(source)})
    binding = bind(root/'package', sources, entry=entry)
    limits = params.get('runtime_limits', {})
    _fields(limits, set(), {'memory','cpus','pids'}, 'runtime_limits')
    limits = planner.options(limits)
    opaque = {k:params.get(k, []) for k in ('requirements','constraints')}
    for key,value in opaque.items(): request_contracts.strings(value, key)
    compatibility = None
    if 'tool_compatibility' in params:
        compatibility = request_contracts.tool_payload({**opaque,'tool_compatibility':params['tool_compatibility']},
                                                      {'constraints':params.get('caller_constraints', {})})
    elif params.get('caller_constraints'):
        raise ValueError('caller_constraints requires explicit tool_compatibility; legacy requirements cannot be silently reclassified')
    request = tools.describe(root, binding, params['declaration'], opaque['requirements'], opaque['constraints'], limits,
                             tool_compatibility=compatibility)
    return {'request_key':fingerprint(request), 'request':request, 'binding_observation':binding,
            'binding_persisted':False}, [_ref(root/f['path'], 'implementation_input') for f in request['files']]


def _registry(params):
    return _path(params['registry'], 'registry') if 'registry' in params else tools.registry_root()


def _host(refs=None):
    host = LocalExecutor().host()
    if host.get('status') != 'available':
        raise ManagementError('host_unavailable', 'Current Docker host unavailable', object='local-docker', raw=host, source_refs=refs)
    return host


def _observer():
    observations = []
    def observed(command, timeout):
        result = process(command, timeout)
        observations.append({'command':command,'result':result})
        return result
    return observed, observations


def _artifact(root, reference):
    _reference(reference)
    path = safe_relative(root, reference['request_key']+'-'+reference['artifact_id']+'.json')
    try:
        record = tools.read_record(path)
        if any(record[k] != reference[k] for k in reference): raise ValueError('Selected record identity differs from filename/reference')
    except (ValueError,OSError,KeyError,TypeError) as exc:
        raise ManagementError('not_found' if isinstance(exc,FileNotFoundError) else 'artifact_invalid',str(exc),object=str(path),
            raw={'exception':type(exc).__name__,'reason':str(exc)},source_refs=[_ref(path,'selected_record_observation')]) from exc
    return record, _ref(path, 'tool_artifact_record')


def _reference(value):
    try: tools.validate_reference(value)
    except ValueError as exc:
        raise ManagementError('request_invalid',str(exc),field='reference',actual=value) from exc


def _library(params):
    root = _path(params['library'], 'library', directory=True)
    name = params['name']
    if not isinstance(name,str) or not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',name):
        raise ManagementError('request_invalid','Invalid candidate name',field='name',actual=name)
    if not safe_relative(root,'catalog.json').is_file():
        raise ManagementError('not_found','Library catalog not found',object=str(root/'catalog.json'))
    return root, name


def _perform(operation, params):
    if operation == 'references.query':
        from creation_pipeline.references import query
        return query(params)
    if operation == 'tool.describe': return _describe(params)
    if operation in {'tool.resolve', 'tool.select'}:
        _sha(params['request_key'],'request_key')
        if operation == 'tool.select': _reference(params['reference'])
        described, refs = _describe(params['descriptor'])
        if described['request_key'] != params['request_key']:
            raise ManagementError('request_changed','Current implementation/requirements differ from described request',
                object=params['descriptor']['context'],field='request_key',expected=params['request_key'],actual=described['request_key'])
        root = _registry(params); host = _host(refs)
        observed, observations = _observer()
        if operation == 'tool.select':
            record, observation = tools.select(described['request'],params['reference'],host,observed,root)
        else: record, observation = tools.resolve(described['request'],host,observed,root)
        data = {'observation':observation,'artifact':record,'binding_persisted':False,
                'available':record is not None,'passed':None,'accepted':None,'host':host,'observations':observations}
        if record: refs.append(_ref(root/(record['request_key']+'-'+record['artifact_id']+'.json'),'tool_artifact_record'))
        if operation == 'tool.select' and not record:
            first = next(iter(observation.get('mismatches',[])),{})
            if observation.get('path'): refs.append(_ref(observation['path'],'selected_record_observation'))
            raise ManagementError('selection_failed','Concrete version cannot satisfy the current request; no fallback',
                object=params['reference'],field=first.get('field'),expected=first.get('expected'),actual=first.get('actual'),raw=data,source_refs=refs)
        return data, refs
    if operation == 'tool.availability':
        record, ref = _artifact(_registry(params),params['reference'])
        offline = params.get('offline',False)
        observed, observations = _observer(); host = None if offline else _host([ref])
        reason = 'historical_unverified' if offline else tools.available(record,host,observed)
        return {'reference':params['reference'],'record_verified':True,'availability':reason,
                'available':None if offline else reason=='available','passed':None,'accepted':None,
                'host':host,'observations':observations,
                'scope':'record plus current metadata (v2 includes external closure probes); not execution qualification'}, [ref]
    root, name = _library(params)
    if operation == 'skill.qualification':
        if params.get('offline',False):
            entry = next((e for e in store.catalog(root)['skills'] if e['name']==name),None)
            if entry is None: raise ManagementError('not_found','Candidate not found',object=name)
            store.check(root,entry)
            return {'name':name,'revision_id':entry['revision_id'],'qualification':{'accepted':None,'reason':'offline_current_unverified'},
                    'historical':entry,'scope':'historical input/evidence integrity only; no current acceptance'}, _entry_refs(root,name,entry)
        entry = store.get(root,name,include_candidates=True)
        return {'name':name,'revision_id':entry['revision_id'],'qualification':entry['current_qualification'],
                'native':entry,'scope':'current qualification via existing store/qualify; catalog reconciliation is possible'}, _entry_refs(root,name,entry)
    _sha(params['expected_revision'],'expected_revision','rev-'); _sha(params['expected_freeze_sha256'],'expected_freeze_sha256')
    result = resume_build(root,name,reuse_image=True,allow_diagnosis=False,
                          expected_revision=params['expected_revision'],expected_freeze=params['expected_freeze_sha256'],include_evidence=True)
    refs = _entry_refs(root,name,result.get('evidence_snapshot'))
    if result.get('status') != 'execution_passed':
        raise ManagementError('execution_blocked' if result.get('status')=='runtime_blocked' else 'execution_failed',
                              'Independent locked execution did not pass',object=name,raw=result,source_refs=refs)
    return {'native':result,'passed':True,'accepted':bool(result.get('accepted')),
            'scope':'new attempt using bound completed image and current locked contract; no build/diagnosis'}, refs


def dispatch(request):
    """One versioned request -> one redacted response; no alternate execution chain."""
    operation = request.get('operation') if isinstance(request,dict) else None
    request_id = request.get('request_id') if isinstance(request,dict) else None
    params = request.get('params',{}) if isinstance(request,dict) else {}
    response = {'api_version':API_VERSION,'request_id':request_id,'operation':operation,'ok':False,
                'observed_at':None,'data':None,'error':None,'evidence':[], 'side_effects':{}}
    try:
        _fields(request,{'api_version','request_id','operation','params'},set(),'request')
        if request['api_version'] != API_VERSION:
            raise ManagementError('request_invalid','Unsupported management API version',field='api_version',expected=API_VERSION,actual=request['api_version'])
        if not isinstance(request_id,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._:-]{0,127}',request_id):
            raise ManagementError('request_invalid','Invalid correlation request_id',field='request_id',actual=request_id)
        if not isinstance(operation,str) or operation not in OPERATIONS:
            raise ManagementError('request_invalid','Unsupported management operation',field='operation',expected=sorted(OPERATIONS),actual=operation)
        _fields(params,*OPERATIONS[operation],'params')
        if 'offline' in params and type(params['offline']) is not bool:
            raise ManagementError('request_invalid','offline must be boolean',field='offline',actual=params['offline'])
        response['side_effects'] = _effects(operation,params.get('offline',False))
        response['data'], response['evidence'] = _perform(operation,params)
        response['ok'] = True
    except (ValueError,OSError,KeyError,TypeError,KeyboardInterrupt) as exc:
        code = getattr(exc,'code',None) or ('cancelled' if isinstance(exc,KeyboardInterrupt) else 'not_found' if isinstance(exc,FileNotFoundError) else 'lock_conflict' if isinstance(exc,FileExistsError) else 'descriptor_invalid' if operation=='tool.describe' else 'operation_failed')
        response['evidence'] = copy.deepcopy(getattr(exc,'source_refs',[]))
        response['error'] = {'code':code,'object':getattr(exc,'object',getattr(exc,'filename',None)),'field':getattr(exc,'field',None),
            'expected':getattr(exc,'expected',None),'actual':getattr(exc,'actual',None),'reason':str(exc),
            'source_refs':[], 'raw':getattr(exc,'raw',None) or {'exception':type(exc).__name__,'code':getattr(exc,'code',None),'reason':str(exc)}}
        if isinstance(params,dict) and isinstance(operation,str) and operation in {'skill.execute','skill.qualification'}:
            try: response['evidence'] = _entry_refs(*_library(params),snapshot=getattr(exc,'evidence_snapshot',None))
            except (ValueError,OSError,KeyError,TypeError): pass
        response['error']['source_refs'] = copy.deepcopy(response['evidence'])
    response['observed_at'] = now()
    return sanitized(response)


def from_file(path):
    try: return dispatch(read_json(path))
    except (ValueError,OSError) as exc:
        response = dispatch(None)
        response['error'].update(object=str(path),reason=str(exc),raw={'exception':type(exc).__name__,'reason':str(exc)})
        return sanitized(response)


def exit_code(response):
    return 0 if response['ok'] else 2 if response['error']['code']=='request_invalid' else 1


def contract():
    """Offline, serializable local contract inventory; no state observations."""
    return {'api_version':API_VERSION,
        'request_fields':['api_version','request_id','operation','params'],
        'response_fields':['api_version','request_id','operation','ok','observed_at','data','error','evidence','side_effects'],
        'error_fields':['code','object','field','expected','actual','reason','source_refs','raw'],
        'evidence_fields':['path','kind','sha256'],
        'operations':{k:{'required':sorted(required),'optional':sorted(optional)} for k,(required,optional) in OPERATIONS.items()},
        'descriptor':{'required':sorted(DESCRIPTOR_REQUIRED),'optional':sorted(DESCRIPTOR_OPTIONAL)},
        'execution_policy':{'reuse_bound_image':True,'allow_diagnosis':False,'allow_build':False,'allow_models':False,
                            'expected_revision_and_freeze_required':True,'request_id_is_idempotency_key':False,
                            'evidence_snapshot_from_writer_lock':True},
        'offline_operations':['tool.describe','tool.availability','skill.qualification','references.query']}
