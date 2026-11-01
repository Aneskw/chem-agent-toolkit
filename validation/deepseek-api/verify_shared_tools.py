"""Fresh real-Docker infrastructure trial; no generation or model calls.

The deterministic content gates here are fixtures, not claims of a new native
Agent content review. Current tests are supplied independently of the registry.
"""
import argparse
import copy
import os
from pathlib import Path
import shutil
import sys
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo))
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.artifacts.evidence import seal
from creation_pipeline.contracts import finalize, qualify
from creation_pipeline.records import write_json, read_json, sanitized, file_digest
from creation_pipeline.runtime import shared_tool, local
from creation_pipeline.runtime.preparation import prepare
from creation_pipeline.runtime.service import execute_prepared
from tests.pipeline.test_runtime_build import plan, TEXT, QUOTE
from tests.pipeline.test_shared_tool import declaration


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    root = args.evidence.resolve()
    root.mkdir(parents=True, exist_ok=False)
    os.environ['CHEM_AGENT_SHARED_TOOLS'] = str(root / 'tools')
    os.environ['CHEM_AGENT_SHARED_ENVIRONMENTS'] = str(root / 'environments')
    write_json(root / 'scope.json', {'scope': 'no-model infrastructure fixtures; not an independent generated chemistry batch',
                                   'models': 0, 'cache': 'existing Docker/BuildKit caches retained; fresh registry, not cold Docker'})
    executor = local.LocalExecutor()
    host = executor.host()
    write_json(root / 'host.json', sanitized(host))
    if host['status'] != 'available':
        raise ValueError('Docker unavailable: ' + str(host['gaps']))
    pin = executor._local_base_image('python:3.11-slim-bookworm', 30)
    if not pin:
        raise ValueError('Required previously cached python:3.11-slim-bookworm RepoDigest missing')
    executor.resolve_base_image = lambda reference, timeout=120: dict(pin, resolved_from='local_cache')
    write_json(root / 'storage-before.json', sanitized(local.process(['docker', 'system', 'df', '-v'], 60)))
    results = []
    records = {}
    observation_lock = threading.Lock()
    def trial(name, different=False, failing=False, build_failure=False):
        start = time.monotonic()
        base = root / name; package = base / 'package'; source = base / 'source'
        package.mkdir(parents=True); source.mkdir()
        text = TEXT + ('\n# Different implementation: ' + str(different) + ', identical dependencies.\n' if different else '')
        for path in (package / 'main.py', source / 'main.py'):
            path.write_text(text, encoding='utf-8')
        (package / 'SKILL.md').write_text('# ' + name + '\nIndependent fixture prose.\n', encoding='utf-8')
        sources = [{'id': 'tool', 'path': str(source), 'inventory': manifest(source), 'resolved_ref': 'fixed-test-fixture'}]
        record = {'name': name, 'kind': 'skill', 'status': 'ready', 'files': manifest(package), 'plan': {'name': name},
                  'checks': [{'name': 'content_review', 'status': 'pass', 'requirement_assessment': 'confirmed',
                              'scope': 'deterministic infrastructure fixture, not native Agent review'}]}
        if failing:
            record['test_definitions'] = {'configured': [{'name': 'deliberate-business-failure',
                'argv': ['{python}', '{package}/main.py'], 'stdout_contains': ['deliberately impossible output']}]}
        finalize(record, sources, {'status': 'required', 'reason': 'Executable fixture',
                                  'citations': [{'source_id': 'tool', 'path': 'main.py', 'quote': QUOTE}]})
        p = plan(); p['base_image'] = pin['reference']
        p['steps'] = [{'command': 'python -c "import sys; assert sys.version_info.major == 3"',
                       'purpose': 'Verify common dependency interpreter', 'evidence': 'Python standard library source'}]
        p['build_layout'] = {'dependency_files': [], 'prefix_steps': 1, 'reason': 'Source-independent interpreter check'}
        if build_failure:
            p['steps'][0]['command'] = 'python -c "raise SystemExit(17)"'
        # Fresh source-derived current cases, never loaded from a ToolArtifact.
        for case in p['tests']:
            case['name'] = name + '-' + case['name']
        spec = {'plan': p, 'options': {'pin_base_image': True}, 'shared_tool': declaration(p),
                'acceptance_plan': {k: p[k] for k in shared_tool.ACCEPTANCE}}
        materials = prepare(record, package, sources, base / 'work', spec, executor)
        prepared = time.monotonic()
        write_json(base / 'preparation.json', sanitized(record['runtime_preparation']))
        if record['runtime_preparation']['status'] != 'prepared':
            raise ValueError(str(record['runtime_preparation']))
        freeze = seal(base / 'evidence/frozen', package, record, sources, materials)
        record['durable_evidence'] = {'path': 'evidence/frozen', 'freeze_sha256': freeze}
        receipt = execute_prepared(base, record, executor)
        finished = time.monotonic()
        accepted, reason = qualify(record['delivery'], runtime_root=base, runtime_ref=record['runtime'],
                                   frozen_directory=base / 'evidence/frozen', freeze_sha256=freeze, executor=executor)
        write_json(base / 'record.json', sanitized(record))
        result = {'name': name, 'accepted': accepted, 'reason': reason, 'status': receipt['status'],
                  'shared_tool': receipt.get('shared_tool'), 'environment': receipt.get('shared_environment'),
                  'build_calls': receipt.get('build_calls'), 'preparation_seconds': prepared-start,
                  'build_execution_seconds': finished-prepared, 'model_calls': record['runtime_preparation']['model_calls'],
                  'environment_planner_calls': record['runtime_preparation']['environment_planning_calls'],
                  'acceptance_source': 'fresh caller-supplied fixture plan',
                  'cases': len(receipt.get('execution', {}).get('cases', [])), 'attempt': record['runtime']['path']}
        raw_build = read_json(base/record['runtime']['path']/'receipt.json')
        result['build_or_bind_seconds'] = (datetime.fromisoformat(raw_build['finished_at']) - datetime.fromisoformat(raw_build['started_at'])).total_seconds()
        execution = receipt.get('execution', {})
        result['validation_seconds'] = ((datetime.fromisoformat(execution['finished_at']) - datetime.fromisoformat(execution['started_at'])).total_seconds()
                                        if execution.get('started_at') else None)
        result['business_case_wall_seconds'] = sum(execution.get('case_wall_seconds', {}).get(c['name'], 0)
                                                   for c in execution.get('cases', []) if c.get('layer') != 'environment')
        with observation_lock:
            results.append(result); records[name] = (base, record)
            write_json(root / 'observations.json', sanitized(results))
        assert accepted is not (failing or build_failure), result
        return result
    with patch('creation_pipeline.runtime.model_call.call', side_effect=AssertionError('No model calls allowed')), \
         patch('creation_pipeline.agent.backend.NativeSession.stage', side_effect=AssertionError('No native model calls allowed')):
        a = trial('skill-a')
        b = trial('skill-b')
        c = trial('different-tool', different=True)
        failed = trial('skill-fails', failing=True)
        assert a['build_calls'] == {'environment': 1, 'tool': 1}, a
        assert b['build_calls'] == {'environment': 0, 'tool': 0}, b
        assert b['shared_tool']['artifact_id'] == a['shared_tool']['artifact_id']
        assert c['build_calls'] == {'environment': 0, 'tool': 1}, c
        assert c['environment']['status'] == 'hit'
        assert failed['shared_tool']['artifact_id'] == a['shared_tool']['artifact_id']
        base, old = records['skill-a']
        assert qualify(old['delivery'], runtime_root=base, runtime_ref=old['runtime'], frozen_directory=base/'evidence/frozen',
                       freeze_sha256=old['durable_evidence']['freeze_sha256'], executor=executor)[0]
        barrier = threading.Barrier(2)
        original_build = executor.build
        def simultaneous(request):
            barrier.wait(timeout=60)
            return original_build(request)
        with patch.object(executor, 'build', side_effect=simultaneous), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(trial, name, 'concurrent') for name in ('concurrent-a', 'concurrent-b')]
            concurrent = [f.result() for f in futures]
        assert sum(x['build_calls']['tool'] for x in concurrent) == 1, concurrent
        assert concurrent[0]['shared_tool']['artifact_id'] == concurrent[1]['shared_tool']['artifact_id']
        old_versions = {p.name: file_digest(p) for p in (root/'tools').glob('*.json')}
        broken = trial('build-fails', different='broken', build_failure=True)
        assert broken['status'] == 'build_failed', broken
        assert {p.name: file_digest(p) for p in (root/'tools').glob('*.json')} == old_versions
        # Isolated malformed observations; never remove real user images or
        # mutate published versions to manufacture failure.
        original_artifact = next(shared_tool.read_record(p) for p in (root/'tools').glob('*.json')
                                 if shared_tool.read_record(p)['artifact_id'] == a['shared_tool']['artifact_id'])
        faults = []
        for scenario in ('missing-image', 'different-daemon', 'corrupt-record'):
            isolated = root/'faults'/scenario
            item = copy.deepcopy(original_artifact)
            if scenario == 'missing-image':
                item['image_id'] = 'sha256:' + '0'*64
            elif scenario == 'different-daemon':
                item['daemon_id'] = 'different-daemon'
            item['artifact_id'] = shared_tool.fingerprint({k: v for k,v in item.items() if k != 'artifact_id'})
            path = isolated/(item['request_key']+'-'+item['artifact_id']+'.json')
            write_json(path, item if scenario != 'corrupt-record' else {'broken': True})
            found, observation = shared_tool.resolve(item['request'], host, local.process, isolated)
            assert found is None
            faults.append({'scenario': scenario, 'observation': observation})
        write_json(root/'faults.json', sanitized(faults))
        # Delivery uses the existing envelope/import/relocate path, which always
        # withdraws execution qualification before revalidating the new location.
        from creation_pipeline.runtime.installation import install_envelope
        from creation_pipeline.runtime.recovery import import_candidate, inspect_candidate, relocate
        from creation_pipeline.runtime.service import resume_build
        install_envelope(base, old['durable_evidence']['path'], old['runtime']['path'], root/'installed')
        imported = root/'imported-library'
        import_candidate(root/'installed', imported, 'skill-a')
        before = inspect_candidate(imported, 'skill-a')
        assert not before['qualification']['accepted']
        resume_build(imported, 'skill-a', reuse_image=True)
        assert inspect_candidate(imported, 'skill-a')['qualification']['accepted']
        moved = root/'moved-library'
        shutil.copytree(imported, moved)
        assert not inspect_candidate(moved, 'skill-a')['qualification']['accepted']
        relocate(moved, 'skill-a', revalidate=False)
        resume_build(moved, 'skill-a', reuse_image=True)
        assert inspect_candidate(moved, 'skill-a')['qualification']['accepted']
        # Explicit rebuild of a concrete shared binding validates and reuses the
        # same immutable tool; it does not silently upgrade a pinned version.
        resume_build(moved, 'skill-a', reuse_image=False)
        assert inspect_candidate(moved, 'skill-a')['qualification']['accepted']
        write_json(root/'delivery.json', {'passed': True, 'import_inherited_qualification': False,
                   'move_inherited_qualification': False, 'paths': ['install-envelope', 'import', 'relocate', 'resume', 'explicit-rebuild'],
                   'remote_OCI_distribution': 'unsupported; local daemon identity required'})
        write_json(root / 'storage-after.json', sanitized(local.process(['docker', 'system', 'df', '-v'], 60)))
        write_json(root / 'result.json', sanitized({'passed': True, 'scope': 'real Docker infrastructure, no models or new generated batches',
            'old_qualification_preserved': True, 'observations': results, 'storage_scope': 'Docker system df -v snapshots; no virtual-size sum or cold-cache claim'}))
        print({'passed': True, 'evidence': str(root), 'trials': len(results)})


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir():
            write_json(Path(sys.argv[1]) / 'failure.json', sanitized({'type': type(exc).__name__, 'error': str(exc)}))
        raise
