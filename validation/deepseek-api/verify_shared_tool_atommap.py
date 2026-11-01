"""Revalidate unchanged historical atom-map contracts in exact tool mode.

Not a new generation batch: content and cases come from the supplied frozen
source, never from a ToolArtifact. No model calls, no source-library mutation.
"""
import argparse
import copy
import os
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo))
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.artifacts.evidence import seal
from creation_pipeline.contracts import finalize, qualify
from creation_pipeline.records import read_json, write_json, sanitized
from creation_pipeline.runtime import shared_tool, local
from creation_pipeline.runtime.preparation import prepare
from creation_pipeline.runtime.service import execute_prepared


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--library', type=Path, default=repo.parent/'acceptance-atommap-run64-20261029/library')
    args = parser.parse_args()
    root = args.evidence.resolve(); root.mkdir(parents=True, exist_ok=False)
    original = next(args.library.glob('evidence/*/*/record.json')).parent
    before = manifest(original)
    saved = read_json(original/'record.json')
    p = read_json(original/'runtime/plan.json')
    assert len(p['steps']) == 1 and p['steps'][0]['command'] == 'python -m pip install --no-cache-dir rdkit'
    p['build_layout'] = {'dependency_files': [], 'prefix_steps': 1, 'reason': 'Explicit source-independent original RDKit installation'}
    os.environ['CHEM_AGENT_SHARED_TOOLS'] = str(root/'tools')
    os.environ['CHEM_AGENT_SHARED_ENVIRONMENTS'] = str(root/'environments')
    executor = local.LocalExecutor()
    pin = executor._local_base_image(p['base_image'], 30)
    if not pin:
        raise ValueError('Original base RepoDigest not currently available')
    executor.resolve_base_image = lambda reference, timeout=120: dict(pin, resolved_from='local_cache')
    declaration = {'closure': 'all-package-and-sources-except-skill-document',
                   'requirements': {'imports': {'rdkit': 'unpinned'}, 'executables': []},
                   'interface': {'entrypoint': p['entrypoint'], 'workdir': '/opt/skill', 'resources': [], 'runtime_network': False},
                   'platform': p['platform'], 'policy': shared_tool.POLICY}
    results = []
    with patch('creation_pipeline.runtime.model_call.call', side_effect=AssertionError('No models allowed')), \
         patch('creation_pipeline.agent.backend.NativeSession.stage', side_effect=AssertionError('No native models allowed')):
        for name in ('atommap-first', 'atommap-hit'):
            base = root/name; base.mkdir()
            package = base/'package'; shutil.copytree(original/'package', package)
            sources = []
            for s in saved['delivery']['inputs']['sources']:
                item = copy.deepcopy(s); item['path'] = str(original/'sources'/s['id']); sources.append(item)
            record = copy.deepcopy(saved)
            record.update(name=name, status='ready', files=manifest(package))
            record['plan']['name'] = name
            for field in ('delivery', 'runtime', 'durable_evidence', 'execution_location'):
                record.pop(field, None)
            finalize(record, sources, saved['delivery']['inputs']['requirement'])
            spec = {'plan': p, 'shared_tool': declaration, 'options': {'pin_base_image': True},
                    'acceptance_plan': {k: copy.deepcopy(p[k]) for k in shared_tool.ACCEPTANCE}}
            start = time.monotonic()
            materials = prepare(record, package, sources, base/'work', spec, executor,
                                review_evidence=read_json(original/'runtime/independent-contract-review.json')
                                if (original/'runtime/independent-contract-review.json').exists() else None)
            write_json(base/'preparation.json', sanitized(record['runtime_preparation']))
            assert record['runtime_preparation']['status'] == 'prepared', record['runtime_preparation']
            freeze = seal(base/'evidence/frozen', package, record, sources, materials)
            record['durable_evidence'] = {'path': 'evidence/frozen', 'freeze_sha256': freeze}
            prepared = time.monotonic()
            receipt = execute_prepared(base, record, executor)
            accepted, reason = qualify(record['delivery'], runtime_root=base, runtime_ref=record['runtime'],
                frozen_directory=base/'evidence/frozen', freeze_sha256=freeze, executor=executor)
            write_json(base/'record.json', sanitized(record))
            result = {'name': name, 'accepted': accepted, 'reason': reason, 'build_calls': receipt.get('build_calls'),
                      'tool': receipt.get('shared_tool'), 'cases': len(receipt.get('execution', {}).get('cases', [])),
                      'preparation_seconds': prepared-start, 'execution_and_build_seconds': time.monotonic()-prepared,
                      'model_calls': record['runtime_preparation']['model_calls'], 'attempt': record['runtime']['path']}
            results.append(result); write_json(root/'observations.json', sanitized(results))
            assert accepted, result
        assert results[1]['build_calls'] == {'environment': 0, 'tool': 0}
        assert results[0]['tool']['artifact_id'] == results[1]['tool']['artifact_id']
        assert manifest(original) == before
        write_json(root/'result.json', sanitized({'passed': True, 'scope': 'unchanged historical chemistry contract revalidation',
            'new_generation_batches': 0, 'model_calls': 0, 'original_unchanged': True, 'observations': results}))
        print({'passed': True, 'evidence': str(root), 'cases': sum(r['cases'] for r in results)})


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir():
            write_json(Path(sys.argv[1])/'failure.json', sanitized({'type': type(exc).__name__, 'error': str(exc)}))
        raise
