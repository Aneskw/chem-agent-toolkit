"""Adapt old inspect_run/relocate_runtime decisions to the existing service/store.

No authoring, discovery, planner, parallel catalog or legacy bindings protocol.
"""
from pathlib import Path
from creation_pipeline.records import read_json, file_digest, safe_relative, now
from creation_pipeline.contracts import runtime_request
from .local import binding_identity, LocalExecutor


def import_candidate(source, library, name):
    """Transfer a frozen native output or installed runtime envelope into the one catalog.

    Imported execution is historical only. Even an unchanged image must be
    explicitly revalidated; incomplete attempts are retained as recovery input.
    """
    import copy
    import shutil
    import uuid
    from creation_pipeline.artifacts import store
    from creation_pipeline.artifacts.evidence import verify
    from creation_pipeline.artifacts.package import manifest
    source = Path(source).resolve()
    outer = {}
    record_path = safe_relative(source, 'records/' + name + '.json')
    if record_path.exists():
        outer = read_json(record_path)
        ref = outer['durable_evidence']
        frozen = safe_relative(source, ref['path'])
        record = verify(frozen, ref['freeze_sha256'])
        if outer['delivery'] != record['delivery']:
            raise ValueError('Output record does not match frozen inputs')
        attempt_ref = outer.get('pending_runtime') or outer.get('runtime')
        attempt = safe_relative(source, attempt_ref['path']) if attempt_ref else None
    else:
        frozen = safe_relative(source, 'frozen')
        attempt = safe_relative(source, 'attempt')
        receipt = read_json(attempt/'receipt.json')
        ref = {'path':'frozen','freeze_sha256':receipt['request']['freeze_sha256']}
        record = verify(frozen,ref['freeze_sha256'])
    if record['name'] != name:
        raise ValueError('Candidate name differs from frozen delivery')
    revoked = outer.get('content_status') == 'failed' or outer.get('runtime', {}).get('content_revoked', False)
    if outer.get('runtime') and not outer.get('pending_runtime'):
        from .service import verify_attempt
        verify_attempt(source,outer['runtime'],record['delivery'],ref['freeze_sha256'])
    if attempt is not None and (attempt/'execution/report.json').exists():
        report=read_json(attempt/'execution/report.json')
        request=runtime_request(record['delivery'],frozen,ref['freeze_sha256'],attempt)
        if report.get('request') != binding_identity(request):
            raise ValueError('Imported execution report does not bind this delivery')
        revoked=revoked or report.get('repair_lane')=='content'
    record = copy.deepcopy(record)
    record.pop('runtime',None);record.pop('runtime_history_records',None)
    record['durable_evidence'] = ref
    result = store.adopt(source,[record],{'new_only':True,'revision_parents':{},'batch':{'label':'imported-delivery','tags':[]}},library)
    if result[0]['status'] not in {'candidate_saved','adopted'}:
        raise ValueError('Destination already has this candidate; use explicit recovery/revision instead')
    with store.locked(library) as root:
        value=store.catalog(root);entry=next(e for e in value['skills'] if e['name']==name)
        packages={}
        if revoked:
            entry['current_content']={'status':'failed'}
            entry['current_qualification']={'accepted':False,'reason':'Imported evidence revoked content approval; independent repair/review required'}
            if entry['zone']=='accepted':
                previous=entry['path'];entry.update(zone='candidates',path='candidates/' + name)
                packages[entry['path']]=root/previous;packages[previous]=None
        if attempt is not None and attempt.exists():
            expected=manifest(attempt)
            relative='runtime/' + entry['candidate_id'] + '/' + uuid.uuid4().hex
            destination=safe_relative(root,relative)
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copytree(attempt,destination)
            if manifest(destination)!=expected:
                raise ValueError('Imported attempt changed during copy')
            entry['pending_runtime']={'path':relative,'revision_id':entry['revision_id'],
                                      'started_at':now(),'imported_files':expected,'reason':'Explicit import requires revalidation'}
        entry.setdefault('imports',[]).append({'at':now(),'source':str(source),'freeze_sha256':ref['freeze_sha256'],
                                               'execution_acceptance_inherited':False})
        store.commit(root,value,packages)
    return {'status':'ready' if entry['zone']=='accepted' else 'not_run','name':name,'revision_id':record['delivery']['revision_id'],
            'adoption':result,'next':'runtime-resume'}


def choose_build(root, entry, executor, mode):
    """False: explicit rebuild; True: validate only; None: reuse verified build or rebuild.

    Adapt lifecycle.validate(reuse_build): current inputs/image must match, and
    execution observations are never reused. A completed build from an interrupted
    attempt can be recovered, but an incomplete build receipt cannot.
    """
    if mode is False:
        return None, {'action': 'build', 'reason': 'Explicit rebuild requested'}
    refs = ([entry['pending_runtime']] if entry.get('pending_runtime') else [])
    refs += [entry['runtime']] if entry.get('runtime') else []
    refs += list(reversed(entry.get('runtime_history', [])))
    for ref in refs:
        directory = safe_relative(root, ref['path'])
        try:
            build = read_json(directory / 'receipt.json')
            request = runtime_request(entry['delivery'], root / entry['evidence'], entry['freeze_sha256'], directory)
            if build.get('status') != 'built' or build.get('request') != binding_identity(request):
                continue
            if file_digest(directory / 'build-log.json') != build['log_sha256']:
                raise ValueError('Build log changed')
            if 'execution_status' in ref:
                from .service import verify_attempt
                verify_attempt(root, ref, entry['delivery'], entry['freeze_sha256'])
            current = executor.verify_current(request, build)
            if mode is True or current['status'] == 'available' or current.get('preflight', {}).get('gaps'):
                return directory, {'action': 'validate', 'reason': 'Bound completed build; execute all locked cases afresh',
                                   'reused_attempt': ref['path'], 'image_observation': current}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if ref is entry.get('pending_runtime'):
                # Incomplete write is diagnostic, not permission to reuse the image.
                continue
            raise ValueError('Stored build evidence cannot be reused: ' + str(exc)) from exc
    if mode is True:
        raise ValueError('No bound completed build to validate; use runtime-resume or runtime-build')
    return None, {'action': 'build', 'reason': 'No completed build with a currently verified image'}


def inspect_candidate(library, name):
    from creation_pipeline.artifacts import store
    entry = store.get(library, name, include_candidates=True)
    root = Path(library).resolve()
    result = {'name': name, 'revision_id': entry['revision_id'], 'zone': entry['zone'],
              'historical_execution': entry.get('current_execution', {'status': 'not_run'}),
              'qualification': entry.get('current_qualification'), 'pending': entry.get('pending_runtime'),
              'diagnosis': entry.get('runtime_diagnosis', {}).get('outcome'),
              'content': entry.get('current_content', entry['delivery']['content'])}
    if entry.get('invalidated') or result['content']['status'] == 'failed':
        return dict(result, action='review_required', reason=entry.get('invalidated') or
                    'Content approval revoked pending independent diagnosis; this is not proof of defective source. '
                    'runtime-resume can diagnose the source; verified contract errors reuse runtime-prepare --oracle-correction internally; '
                    'content/call defects require author review')
    if entry.get('runtime', {}).get('repair_lane') in {'unknown', 'contract'}:
        return dict(result, action='review_required',
                    reason='Execution observations require source diagnosis, not automatic source rewriting; use runtime-resume')
    if entry['delivery']['mode'] == 'draft':
        return dict(result, action='review_required', reason='Draft needs a normally reviewed revision')
    if entry['delivery']['inputs']['requirement']['status'] == 'not_required':
        return dict(result, action='none', reason='Reviewed source-supported no-execution delivery')
    env = entry['delivery']['inputs']['environment']['payload']
    if not env or not env.get('plan'):
        return dict(result, action='prepare_required', reason='No validated environment plan')
    request = runtime_request(entry['delivery'],root/entry['evidence'],entry['freeze_sha256'],root/'runtime/inspection')
    executor = LocalExecutor(); preflight = executor.preflight(request)
    if preflight['gaps']:
        return dict(result, action='blocked', host=preflight['host'], gaps=preflight['gaps'])
    _, decision = choose_build(root, entry, executor, None)
    return dict(result, action=decision['action'], decision=decision, host=preflight['host'])


def relocate(library, name, *, revalidate=False, recover_lock=False):
    """Migrate old relocate: verify before mutation, archive facts, withdraw, revalidate.

    Pure paths never enter input fingerprints. Frozen sources/contexts are already
    portable; no fingerprint rewriting, timestamp repair or legacy ZIP import.
    """
    from creation_pipeline.artifacts import store
    if recover_lock:
        store.release_dead_lock(library)
    with store.locked(library) as root:
        value = store.catalog(root)
        entry = next((e for e in value['skills'] if e['name'] == name), None)
        if entry is None or entry.get('invalidated'):
            raise ValueError('Explicit intact candidate selection required')
        store.check(root, entry)  # Drift fails before any mutation.
        entry.setdefault('relocation_history', []).append({'at': now(),
            'previous_location': entry.get('execution_location'), 'new_location': str(root.resolve()),
            'previous_qualification': entry.get('current_qualification'), 'acceptance_retained': False,
            'revision_id': entry['revision_id'], 'freeze_sha256': entry['freeze_sha256']})
        packages = {}
        if entry['zone'] == 'accepted':
            previous = entry['path']; entry.update(zone='candidates', path='candidates/' + name)
            packages[entry['path']] = root / previous; packages[previous] = None
        entry['execution_location'] = None
        entry['current_host'] = {'status':'not_checked', 'observed_at':now()}
        entry['current_qualification'] = {'accepted':False,'reason':'Explicit relocation requires fresh execution'}
        if entry['delivery']['inputs']['requirement']['status'] == 'not_required':
            # Same qualification gate; reading-only deliveries have no Docker stage.
            accepted, reason = store.qualification(root, entry)
            entry['current_qualification'] = {'accepted':accepted,'reason':reason}
            entry['current_host'] = {'status':'not_applicable','observed_at':now()}
            if accepted:
                previous = entry['path']
                entry.update(zone='accepted',path='accepted/' + name)
                packages = {entry['path']:root/entry['evidence']/'package'}
                if previous != entry['path'] and (root/previous).exists():packages[previous]=None
            store.commit(root,value,packages)
            return {'status':'ready' if accepted else 'not_run','name':name,'accepted':accepted,'execution':'not_applicable'}
        store.commit(root, value, packages)
    if revalidate:
        from .service import resume_build
        return resume_build(library,name,reuse_image=None)
    return {'status':'not_run','name':name,'accepted':False,'next':'runtime-resume'}
