"""Reuse partner's independent content reviewer for source-backed contract corrections."""
import copy
from pathlib import Path
from creation_pipeline.records import write_json, read_json, file_digest
from creation_pipeline.models import load_config
from creation_pipeline.resources.intake import Sources
from creation_pipeline.agent.backend import NativeSession
from creation_pipeline.generation.author import review
from creation_pipeline.artifacts.package import manifest


def review_snapshot(record, package, sources, work, *, proposed_plan=None, correction=None, proposed_binding=None, model=None,
                    timeout=600, total_seconds=None, call_guard=None, transport='default', reasoning_effort=None,
                    service_tier=None, backend='codex_cli', api_model=None):
    work = Path(work); work.mkdir(parents=True, exist_ok=False)
    raw = {'sources': [{'id': s['id'], 'path': s['path']} for s in sources], 'network': False,
           'prompt': 'Independently review the exact delivered files and source-bound execution scope. Do not run host business checks.',
           'checks': [], 'model': {'backend': backend},
           'limits': {'model_timeout': timeout, 'total_seconds': total_seconds}}
    if model:
        raw['model']['name'] = model
    if api_model:
        raw['model']['api_model'] = api_model
    # The review turn is a model stage like any other: keep the batch's transport
    # and effort settings instead of silently falling back to the user's config.
    raw['model']['transport'] = transport
    if reasoning_effort is not None:
        raw['model']['reasoning_effort'] = reasoning_effort
    if service_tier is not None:
        raw['model']['service_tier'] = service_tier
    write_json(work / 'config.json', raw)
    config = load_config(work / 'config.json')
    material = Sources(config, work / 'cache')
    for source in sources:
        for key in ('upstream', 'carrier_repository', 'snapshot_id'):
            if key in source:
                material.entries[source['id']][key] = copy.deepcopy(source[key])
    config['_binding_review'] = proposed_binding
    config['_oracle_changes'] = [] if correction is None else [{'previous': record['delivery']['inputs']['acceptance'],
        'proposed': proposed_plan, 'source_backed_reason': correction,
        'rule': 'Confirm only a source-supported error in the old expected result; never fit observed outputs or weaken a failing contract. '
                'Check source numeric types and output protocol, every proposed difference, unchanged negative tests/inputs/scope, '
                'no extra accepted outputs or tolerance, and no real source/call defect hidden by this proposal. '
                'Reject ambiguity or changes beyond the source-supported approved scope.'}]
    session = NativeSession(config, material, config['limits'], work / 'agent')
    if call_guard:
        stage = session.stage
        def guarded_stage(*args, **kwargs):
            from .accounting import admit, observe
            ticket = admit(call_guard, 'independent_runtime_review', backend,
                           api_model if backend == 'deepseek_api' else model)
            before = len(session.receipts)
            try:
                return stage(*args, **kwargs)
            finally:
                if len(session.receipts) > before:
                    observe(ticket, session.receipts[-1])
        session.stage = guarded_stage
    plan = copy.deepcopy(record['plan'])
    plan['evidence'] = [{'id': e['id'], 'claim': 'Inspect the original source for this delivered capability'} for e in material.evidence]
    artifact = {'files': [{'path': f['path'], 'content': (Path(package) / f['path']).read_text(encoding='utf-8', errors='replace'),
                           'purpose': 'Exact delivered file'} for f in manifest(package)],
                'tests': [t for origin in ('configured', 'generated', 'reviewed') for t in record.get('test_definitions', {}).get(origin, [])], 'issues': [], 'notes': [],
                'runtime_requirement': record['delivery']['inputs']['requirement'], 'runtime_plan': proposed_plan,
                'entry_binding': proposed_binding}
    before = manifest(package)
    result = review(session, plan, artifact, [], config)
    material.verify()
    if manifest(package) != before:
        raise ValueError('Independent review changed delivered files')
    write_json(work / 'review.json', result)
    return {'review': result, 'receipts': session.receipts, 'files': before,
            'source_files': {s['id']: s['inventory'] for s in sources}, 'oracle_changes': config['_oracle_changes']}
