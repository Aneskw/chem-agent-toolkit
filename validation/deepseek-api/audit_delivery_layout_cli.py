"""Read-only audit of descriptor layout closure through ordinary CLI A/B batches."""
import argparse
import ast
from collections import Counter
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from creation_pipeline.artifacts.layout import extract, require
from creation_pipeline.artifacts.package import manifest, verify_bundle
from creation_pipeline.contracts import qualify
from creation_pipeline.models import load_config
from creation_pipeline.records import file_digest, read_json, sanitized, write_json
from audit_extended_acceptance import audit as business_audit
from audit_extended_acceptance import native_file_result
from audit_extended_acceptance import rows


def audit(root, labels):
    for item in read_json(root/'code-at-generation.json'):
        assert file_digest(REPO/item['path']) == item['sha256'], item['path']
    original = read_json(root/'source-before.json')
    assert manifest(Path(original['path'])) == original['files']
    if (root/'additional-sources-before.json').exists():
        for item in read_json(root/'additional-sources-before.json'):
            assert file_digest(item['path']) == item['sha256'], item['path']
    for item in read_json(root/'old-before.json'):
        assert manifest(Path(item['path'])) == item['files'], 'Historical evidence changed: ' + item['path']
    observations = []
    for label in labels:
        config_path = root/('descriptors-'+label+'.json')
        scope = read_json(root/'scope.json')
        templates = REPO/scope.get('config_templates', 'validation/deepseek-api/shared-cli-expansion')
        assert read_json(config_path) == read_json(templates/config_path.name)
        baseline = read_json(REPO/'validation/deepseek-api/shared-cli-expansion'/config_path.name)
        raw = read_json(config_path)
        if templates.name == 'delivery-layout-input':
            # Added upstream evidence and a stronger retained-case requirement;
            # original requirements, source, interfaces, providers and budgets stay exact.
            for key in baseline.keys()-{'sources', 'runtime_defaults'}:
                assert raw[key] == baseline[key], key
            assert raw['sources'][:-1] == baseline['sources']
            assert raw['sources'][-1]['id'] == 'rdkit_canonical_reference'
            current = dict(raw['runtime_defaults'])
            assert current['constraints'][:-1] == baseline['runtime_defaults']['constraints']
            current['constraints'] = current['constraints'][:-1]
            assert current == baseline['runtime_defaults']
        config = load_config(config_path)
        assert not set(config['runtime_defaults']) & {'plan', 'acceptance_plan', 'tool_artifact'}
        summaries = list((root/label/'state/outputs').glob('*/summary.json'))
        assert len(summaries) == 1, 'No failed-round resume/restart'
        output = summaries[0].parent
        summary, _ = verify_bundle(output)
        assert summary['status'] == 'ready'
        name = summary['entities'][0]['name']
        record = read_json(output/'records'/(name+'.json'))
        delivery = record['delivery']
        assert delivery['protocol'] == 2
        assert delivery['inputs']['layout']['payload'] == extract(config, name)
        package = output/'bundle/skills'/name
        require(manifest(package), delivery['inputs']['layout']['payload'])
        source = Path(original['path'])
        for path in ('scripts/calc_descriptors.py', 'requirements.txt'):
            assert file_digest(package/path) == file_digest(source/path), path
        ref = record['durable_evidence']
        accepted, reason = qualify(delivery, runtime_root=output, runtime_ref=record['runtime'],
            frozen_directory=output/ref['path'], freeze_sha256=ref['freeze_sha256'])
        assert accepted, reason
        receipt = read_json(output/record['runtime']['path']/'receipt.json')
        report = read_json(output/record['runtime']['path']/'execution/report.json')
        retained = []
        if templates.name == 'delivery-layout-input':
            locked = read_json(output/ref['path']/'runtime/locked-tests.json')['cases']
            by_name = {c['name']: c for c in locked}
            def canonical_asserted(case, index, value):
                expected = case.get('expected_json_lines', [])
                if len(expected)>index and expected[index].get('canonical_smiles') == value:
                    return True
                assertion = case.get('acceptance', {}).get('assertion', {})
                return (assertion.get('kind') == 'jsonl' and assertion.get('record_index') == index
                        and assertion.get('path') == ['canonical_smiles']
                        and assertion.get('allowed_values') == [value])
            for observed in report['cases']:
                case = by_name[observed['name']]
                data = rows(observed.get('persisted_output', ''))
                if (observed.get('exit_code') == 0 and len(data) == 2
                        and [r.get('input') for r in data] == ['CCO', 'c1ccccc1O']
                        and [r.get('canonical_smiles') for r in data] == ['CCO', 'Oc1ccccc1']
                        and canonical_asserted(case, 0, 'CCO') and canonical_asserted(case, 1, 'Oc1ccccc1')):
                    retained.append(observed['name'])
                # Native author checks can enforce the whole persisted-file
                # contract in one program; do not confuse them with the single
                # assertion allowed in each planner case. Inspect locked code
                # and its observed result without executing or changing it.
                args = case.get('args', [])
                if len(args) < 3 or args[0] != '-c' or args[-1] != 'valid':
                    continue
                tree = ast.parse(args[1])
                assertions = '\n'.join(ast.unparse(n.test) for n in ast.walk(tree)
                                       if isinstance(n, ast.Assert))
                code = ast.unparse(tree)
                required = ("first['input'] == 'CCO'", "last['input'] == 'c1ccccc1O'",
                    "first['canonical_smiles'] == 'CCO'", "last['canonical_smiles'] == 'Oc1ccccc1'",
                    "src.read_bytes() == content.encode('utf-8')", "p.returncode == (2 if mode == 'mixed' else 0)",
                    "len(rows) == (3 if mode == 'mixed' else 2)")
                if not all(text in assertions for text in required):
                    continue
                assert all(text in code for text in ("first = rows[0]", "last = rows[-1]",
                    "raw = dst.read_bytes()", "json.loads(line)", "raw.decode('utf-8').splitlines()"))
                result = native_file_result(case, observed)
                assert result is not None
                assert result['exit_code'] == 0 and result['byte_count'] > 0
                assert [(r['input'], r['canonical_smiles']) for r in result['rows']] == [
                    ('CCO', 'CCO'), ('c1ccccc1O', 'Oc1ccccc1')]
                retained.append(observed['name'])
            assert retained, 'The failed two-row persisted canonical-output obligation was not retained'
        phases = dict(Counter(r['phase'] for r in summary['model_calls']))
        assert all(phases.get(p, 0)>0 for p in ('discovery', 'author', 'review'))
        sessions = read_json(root/label/'state/runs'/summary['build_id']/'agent-state.json')['sessions']
        assert sessions['review:'+name] != sessions['build:'+name], 'Review must have its own native session'
        assert len(summary['model_calls']) <= config['limits']['model_calls']
        business = business_audit(root/label, 'descriptors-'+label)
        write_json(root/label/'acceptance-audit.json', sanitized(business))
        assert business['passed'], business['missing']
        observations.append({'label': label, 'output': str(output), 'name': name,
            'config_sha256': file_digest(config_path),
            'baseline_config_sha256': file_digest(REPO/'validation/deepseek-api/shared-cli-expansion'/config_path.name),
            'config_supplement': ('official version-pinned canonical reference and stronger retained-case constraint'
                                  if templates.name == 'delivery-layout-input' else None),
            'revision_id': delivery['revision_id'], 'qualification': {'accepted': accepted, 'reason': reason},
            'cases': len(report['cases']), 'package_files': manifest(package), 'layout': delivery['inputs']['layout'],
            'model_calls': len(summary['model_calls']), 'phases': phases, 'model_receipts': summary['model_calls'],
            'independent_review_session': True,
            'retained_two_row_canonical_cases': retained,
            'preparation': record['runtime_preparation'], 'build_calls': receipt['build_calls'],
            'shared_tool': receipt['shared_tool'], 'skill_sha256': file_digest(package/'SKILL.md'),
            'acceptance_sha256': delivery['inputs']['acceptance']['sha256']})
    if labels == ['a', 'b']:
        a, b = observations
        assert a['shared_tool']['artifact_id'] == b['shared_tool']['artifact_id']
        assert a['skill_sha256'] != b['skill_sha256'] and a['revision_id'] != b['revision_id']
        # Equivalent obligations may produce equal case hashes. Fresh model calls,
        # current frozen revisions and independently verified attempts prove the
        # compilation/execution here; random test differences are not required.
        assert b['preparation']['environment_planning_calls'] == 0
        assert b['preparation']['acceptance_planning_calls'] > 0
        assert b['build_calls'] == {'environment': 0, 'tool': 0}
        assert b['preparation']['shared_tool']['status'] == 'hit'
    result = {'passed': True, 'labels': labels, 'scope': 'new public CLI generation plus read-only current qualification',
        'configured_inputs_and_original_source_bytes_unchanged': True,
        'original_requirement_fields_providers_and_per_batch_budget_unchanged': True,
        'old_outputs_and_tool_records_unchanged': True,
        'manual_acceptance_plan': False, 'internal_state_injection': False, 'observations': observations}
    write_json(root/('audit-'+''.join(labels)+'.json'), sanitized(result))
    print({'passed': True, 'cases': sum(o['cases'] for o in observations), 'labels': labels})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--labels', nargs='+', choices=['a', 'b'], default=['a', 'b'])
    args = parser.parse_args()
    audit(args.root.resolve(), args.labels)
