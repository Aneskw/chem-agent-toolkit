"""Two fresh full model-generation batches, exact tools, independent acceptance.

Uses the existing atom-map envelope's providers and budgets without overrides.
Every invocation requires a new root; failures are retained, never resumed.
"""
import argparse
import copy
import os
from pathlib import Path
import sys
import time
from datetime import datetime

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from creation_pipeline.records import read_json, write_json, sanitized, file_digest
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import qualify, fingerprint
from creation_pipeline.models import load_config
from creation_pipeline.runtime import runner
from creation_pipeline.runtime.local import LocalExecutor, process
from creation_pipeline.runtime.shared_tool import POLICY


def configs():
    baseline = read_json(Path(__file__).with_name('acceptance-atommap-input.json'))
    common = baseline['prompt'] + (
        '\nThis is an exact shared-tool experiment. Deliver EXACTLY two files: SKILL.md and '
        'scripts/audit_atom_maps.py. Preserve the original script byte-for-byte. Put provenance, '
        'scope, examples and limitations inline in SKILL.md; do not add reference, example, data, '
        'test or helper files to the package. Express generated checks as self-contained argv '
        'programs with inline input fixtures written under {run}, using the unchanged delivered '
        'script. Preserve all business checks and actual file-output assertions; no lost coverage. '
        'The source tree remains available for provenance. The independent reviewer must inspect '
        'this current package and source, not adopt any historical approval. Never claim '
        'scientific correctness or a shared-tool hit before execution proves it.')
    env_constraints = list(baseline['runtime_defaults']['constraints']) + [
        'Use the exact byte-identical package/scripts/audit_atom_maps.py entry, argv '
        '["python", "/opt/skill/package/scripts/audit_atom_maps.py"]. The only external Python '
        'distribution requirement is rdkit with version="unpinned" (as the original source declares). '
        'All dependency installation steps must be an explicit source-independent prefix, with '
        'dependency_files=[]; no code-dependent steps or generated files. Keep platform linux/amd64, '
        'runtime_network=false and resources=[]. Bind resource_assessment.source_path/source_quote '
        'to stable ORIGINAL sources/existing_atommap files, not generated SKILL.md prose. '
        'This is a caller constraint, not permission to change source or weaken checks.'
    ]
    result = []
    for label, style in (('a', 'Write the SKILL prose as a concise laboratory operator guide, with an opening Workflow section.'),
                         ('b', 'Write different SKILL prose as a data-curation guide, with an opening Dataset quality section.')):
        config = copy.deepcopy(baseline)
        config['prompt'] = common + '\n' + style
        config['runtime_defaults']['requirements'] = [common]
        config['runtime_defaults']['constraints'] = env_constraints
        config['runtime_defaults']['shared_tool'] = {
            'closure': 'all-package-and-sources-except-skill-document',
            'requirements': {'imports': {'rdkit': 'unpinned'}, 'executables': []},
            'interface': {'entrypoint': ['python', '/opt/skill/package/scripts/audit_atom_maps.py'],
                          'workdir': '/opt/skill', 'resources': [], 'runtime_network': False},
            'platform': 'linux/amd64', 'policy': POLICY}
        config['batch']['label'] = 'acceptance-only-shared-' + label
        config['notes'] = ('Fresh full-generation experiment; current operator authorization. Original backend and envelope budgets '
                           'unchanged. No manual plan/acceptance_plan, no resume, no push. Common runtime requirements '
                           'are identical; only documentation style differs. Preserve all failing evidence.')
        assert config['model'] == baseline['model'] and config['limits'] == baseline['limits']
        assert config['runtime_defaults']['options'] == baseline['runtime_defaults']['options']
        result.append(config)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--previous-a', type=Path,
                        help='Audit an already successful A batch, then run only a fresh B; never resume a failed batch')
    args = parser.parse_args()
    root = args.evidence.resolve(); root.mkdir(parents=True, exist_ok=False)
    shared = args.previous_a.resolve() if args.previous_a else root
    os.environ['CHEM_AGENT_SHARED_TOOLS'] = str(shared/'shared-tools')
    os.environ['CHEM_AGENT_SHARED_ENVIRONMENTS'] = str(shared/'shared-environments')
    inputs = configs()
    source = Path(inputs[0]['sources'][0]['path'])
    original = manifest(source)
    write_json(root/'source-before.json', original)
    for label, config in zip(('a', 'b'), inputs):
        write_json(root/('input-'+label+'.json'), sanitized(config))
        load_config(root/('input-'+label+'.json'))
    if args.offline:
        print({'preflight': 'passed', 'model_calls': 0, 'budgets': inputs[0]['limits']})
        return
    host = LocalExecutor().host()
    write_json(root/'host.json', sanitized(host))
    assert host['status'] == 'available', host
    results = []; outputs = []
    for label in ('a', 'b'):
        start = time.monotonic()
        run = shared/'a' if label == 'a' and args.previous_a else root/label
        command = [sys.executable, '-m', 'creation_pipeline', 'build', str(root/('input-'+label+'.json')),
                   '--state-dir', str(run/'state'), '--library-dir', str(run/'library'), '--keep-debug']
        if not (label == 'a' and args.previous_a):
            observed = runner.process(command, inputs[0]['limits']['total_seconds']+90, cwd=REPO, supervise=True)
            write_json(run/'command.json', sanitized(observed))
        summaries = sorted((run/'state/outputs').glob('*/summary.json'))
        assert len(summaries) == 1, 'Expected one fresh output, not resume/restart'
        output = summaries[0].parent; summary = read_json(summaries[0]); outputs.append(output)
        assert summary['status'] == 'ready', {'batch': label, 'summary': str(summaries[0]), 'status': summary['status'], 'errors': summary.get('errors')}
        assert len(summary['entities']) == 1
        name = summary['entities'][0]['name']; record = read_json(output/'records'/ (name+'.json'))
        package = output/'bundle/skills'/name
        assert {f['path'] for f in manifest(package)} == {'SKILL.md', 'scripts/audit_atom_maps.py'}
        assert file_digest(package/'scripts/audit_atom_maps.py') == file_digest(source/'scripts/audit_atom_maps.py')
        ref = record['durable_evidence']; attempt = output/record['runtime']['path']
        receipt = read_json(attempt/'receipt.json'); report = read_json(attempt/'execution/report.json')
        assert report['cases'] and all(c['status'] == 'passed' for c in report['cases'])
        accepted, reason = qualify(record['delivery'], runtime_root=output, runtime_ref=record['runtime'],
                                  frozen_directory=output/ref['path'], freeze_sha256=ref['freeze_sha256'])
        assert accepted, reason
        calls = summary['model_calls']; phases = [c['phase'] for c in calls]
        assert all(p in phases for p in ('discovery', 'author', 'review')), phases
        assert len(calls) <= inputs[0]['limits']['model_calls']
        prep = record['runtime_preparation']
        if label == 'b':
            assert prep['shared_tool']['status'] == 'hit', prep
            assert prep['environment_planning_calls'] == 0 and prep['acceptance_planning_calls'] >= 1, prep
            assert 'runtime_planning' not in phases and 'runtime_acceptance_planning' in phases, phases
            assert receipt['build_calls'] == {'environment': 0, 'tool': 0}, receipt
            assert receipt['shared_tool']['artifact_id'] == results[0]['tool']['artifact_id']
            assert file_digest(package/'SKILL.md') != results[0]['skill_sha256']
        result = {'batch': label, 'output': str(output), 'name': name, 'accepted': accepted,
                  'new_generation_in_this_directory': not (label == 'a' and args.previous_a),
                  'cases': len(report['cases']),
                  'elapsed_seconds': (datetime.fromisoformat(summary['finished_at'])-datetime.fromisoformat(summary['started_at'])).total_seconds(),
                  'command_and_audit_seconds_in_this_directory': time.monotonic()-start,
                  'tool': receipt['shared_tool'], 'build_calls': receipt['build_calls'],
                  'preparation': prep, 'skill_sha256': file_digest(package/'SKILL.md'),
                  'acceptance_sha256': record['delivery']['inputs']['acceptance']['sha256'],
                  'model_calls': len(calls), 'phases': phases,
                  'model_receipts': [{k: v for k, v in c.items() if k in {'phase', 'backend', 'model', 'status', 'elapsed_seconds', 'usage', 'request_count'}} for c in calls]}
        results.append(result); write_json(root/'observations.json', sanitized(results))
        print({'batch': label, 'accepted': accepted, 'cases': result['cases'], 'models': len(calls), 'build_calls': receipt['build_calls']}, flush=True)
    assert manifest(source) == original
    assert results[0]['acceptance_sha256'] != results[1]['acceptance_sha256']
    write_json(root/'result.json', sanitized({'passed': True, 'scope': 'two independent complete model-generation batches',
        'previous_a': str(args.previous_a.resolve()) if args.previous_a else None,
        'manual_acceptance_plan': False, 'original_source_unchanged': True, 'observations': results}))


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir():
            write_json(Path(sys.argv[1])/'failure.json', sanitized({'type': type(exc).__name__, 'error': str(exc)}))
        raise
