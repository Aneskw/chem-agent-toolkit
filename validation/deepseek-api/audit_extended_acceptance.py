"""Independent checks of a completed batch; never runs models or business code."""
import argparse
import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from creation_pipeline.records import read_json, write_json, file_digest, redact, sanitized
from creation_pipeline.artifacts.evidence import verify
from creation_pipeline.contracts import qualify


def rows(text):
    try:
        value = json.loads(text or '')
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    except (ValueError, TypeError):
        pass
    result = []
    for line in (text or '').splitlines():
        try:
            value = json.loads(line)
            result.extend(value if isinstance(value, list) else [value])
        except (ValueError, TypeError):
            pass
    return [r for r in result if isinstance(r, dict)]


def pinned_version_matches(actual, expected):
    if not isinstance(actual, str):
        return False
    # All pins in this suite are numeric release versions; RDKit may present
    # a zero-padded month. Do not accept a different or prerelease version.
    if all(part.isdigit() for part in actual.split('.') + expected.split('.')):
        return tuple(map(int, actual.split('.'))) == tuple(map(int, expected.split('.')))
    return actual == expected


def audit(batch, scenario):
    outputs = list((batch / 'state/outputs').iterdir())
    if len(outputs) != 1:
        raise ValueError('Expected one independent build output')
    output = outputs[0]
    summary = read_json(output / 'summary.json')
    result = {'build_id': summary['build_id'], 'scenario': scenario,
              'status': summary['status'], 'model_calls': len(summary['model_calls']),
              'started_at': summary['started_at'], 'finished_at': summary.get('finished_at'),
              'output': str(output.resolve()), 'missing': [], 'records': []}
    missing = result['missing']
    if summary['status'] != 'ready':
        missing.append('batch_not_ready')
    records = list((output / 'records').glob('*.json'))
    if len(records) != 1:
        missing.append('expected_one_exported_record')
    for path in records:
        record = read_json(path)
        detail = {'name': record['name'], 'status': record['status'],
                  'preparation': record.get('runtime_preparation'), 'runtime': record.get('runtime')}
        result['records'].append(detail)
        if record.get('runtime_preparation', {}).get('status') != 'prepared':
            missing.append('not_prepared')
        ref = record.get('durable_evidence')
        if not ref:
            missing.append('missing_frozen_evidence')
            continue
        frozen = output / ref['path']
        verify(frozen, ref['freeze_sha256'])
        detail['freeze_verified'] = True
        runtime = record.get('runtime') or {}
        report_path = output / runtime.get('path', 'missing') / 'execution/report.json'
        if not report_path.is_file():
            missing.append('no_business_report')
            continue
        report = read_json(report_path)
        observations = report.get('cases', [])
        detail['report'] = str(report_path)
        detail['cases'] = [{'name': c['name'], 'status': c['status']} for c in observations]
        detail['image_id'] = report.get('image_id')
        image_file = report_path.parent.parent / 'image.id'
        if not image_file.is_file() or image_file.read_text(encoding='utf-8').strip() != report.get('image_id'):
            missing.append('missing_or_mismatched_image_id')
        if not observations or any(c.get('status') != 'passed' for c in observations):
            missing.append('not_all_cases_passed')
        if not report.get('acceptance', {}).get('complete'):
            missing.append('acceptance_incomplete')
        pin = frozen / 'runtime/base-image.json'
        if not pin.is_file() or '@sha256:' not in read_json(pin).get('repo_digest', ''):
            missing.append('base_not_pinned')
        else:
            detail['base_image'] = read_json(pin)
        accepted, reason = qualify(record['delivery'], runtime_root=output, runtime_ref=runtime,
                                   frozen_directory=frozen, freeze_sha256=ref['freeze_sha256'])
        detail['current_qualification'] = {'accepted': accepted, 'reason': reason}
        if not accepted:
            missing.append('current_qualification_failed')
        locked = read_json(frozen / 'runtime/locked-tests.json')['cases']
        plan = record['delivery']['inputs']['environment']['payload']['plan']
        by_name = {c['name']: c for c in locked}
        all_rows = [r for c in observations for r in rows(c.get('stdout', '')) + rows(c.get('persisted_output', ''))]
        script = {'descriptors-a': 'calc_descriptors.py', 'descriptors-b': 'calc_descriptors.py',
                  'atommap': 'audit_atom_maps.py', 'geometry': 'check_structure.py'}.get(scenario)
        if script:
            relative_script = 'scripts/' + script
            if plan['script'] != 'package/' + relative_script:
                missing.append('actual_entry_is_not_original_business_script')
            candidates = [s for s in record['delivery']['inputs']['sources']
                          if any(f['path'] == relative_script for f in s['inventory'])]
            if len(candidates) != 1:
                raise ValueError('Expected one frozen original business script')
            original = frozen / 'sources' / candidates[0]['id'] / relative_script
            delivered = frozen / 'package/scripts' / script
            detail['original_script_source'] = str(original)
            detail['business_script_identical'] = delivered.is_file() and file_digest(original) == file_digest(delivered)
            if not detail['business_script_identical']:
                missing.append('business_script_changed')
        if accepted and observations and all(c.get('status') == 'passed' for c in observations):
            packages = ({'rdkit': '2024.9.6', 'numpy': '1.26.4', 'pillow': '11.3.0'}
                        if scenario.startswith('descriptors') else
                        {'ase': '3.26.0', 'numpy': None} if scenario == 'geometry' else
                        {'rdkit': None} if scenario == 'atommap' else {})
            if packages:
                # Inspect installed distribution metadata in the bound container,
                # without importing chemistry/geometry code or installing anything.
                from creation_pipeline.runtime.runner import run
                program = ('import importlib.metadata as m,json; '
                           'print(json.dumps({n:m.version(n) for n in ' + repr(list(packages)) + '}))')
                tool = {'limits': {'memory': '256m', 'cpus': '1'}, 'behavior': {'file_io': False},
                        'runtime_network': False, 'execution_scope': 'audit-' + uuid.uuid4().hex}
                interpreter = plan['entrypoint'][0]
                if not Path(interpreter).name.startswith('python'):
                    interpreter = 'python'
                probe = sanitized(run(tool, report['image_id'], ['-c', program], entrypoint=interpreter, timeout=30))
                detail['dependency_metadata_probe'] = probe
                versions = rows(probe.get('stdout'))
                actual = versions[0] if len(versions) == 1 else {}
                detail['observed_dependency_versions'] = actual
                if probe.get('exit_code') != 0 or any(name not in actual or (version is not None and not pinned_version_matches(actual[name], version))
                                                      for name, version in packages.items()):
                    missing.append('bound_image_dependency_versions_do_not_match')
        if scenario.startswith('descriptors'):
            if not any(r.get('canonical_smiles') == 'CCO'
                       and r.get('descriptors', {}).get('molecular_weight') == 46.069
                       and r.get('descriptors', {}).get('h_bond_donors') == 1
                       and r.get('descriptors', {}).get('h_bond_acceptors') == 1 for r in all_rows):
                missing.append('missing_ethanol_numeric_result')
            for label in ('empty', 'invalid'):
                def rejected(c):
                    if c.get('exit_code') != 2 or '--smiles' not in c.get('command', []):
                        return False
                    return any(r.get('ok') is False and isinstance(r.get('input'), str)
                               and (r['input'] == '' if label == 'empty' else bool(r['input'].strip()))
                               and r['input'] in c['command'] for r in rows(c.get('stdout')))
                if not any(rejected(c) for c in observations):
                    missing.append('missing_' + label + '_rejection')
        if scenario in {'descriptors-a', 'descriptors-b', 'atommap'}:
            valid_file = mixed_file = False
            for observed in observations:
                case = by_name[observed['name']]
                if not case.get('input_files') or not case.get('output_file') or case.get('capture_stdout'):
                    continue
                output_rows = rows(observed.get('persisted_output'))
                if observed.get('exit_code') == 0 and output_rows and all(r.get('ok') is True for r in output_rows):
                    valid_file = True
                flags = [r.get('ok') for r in output_rows]
                if observed.get('exit_code') == 2 and False in flags:
                    rejected_index = flags.index(False)
                    if True in flags[rejected_index + 1:]:
                        mixed_file = True
            if not valid_file:
                missing.append('missing_actual_valid_file_output')
            if not mixed_file:
                missing.append('missing_actual_mixed_file_continuation')
        if scenario == 'atommap':
            if not any(r.get('ok') is True and r.get('reactant_only_maps') == [3] for r in all_rows):
                missing.append('missing_leaving_group_map_result')
            errors = '\n'.join(str(e) for r in all_rows if r.get('ok') is False for e in r.get('errors', []))
            for text in ('duplicate atom-map', 'no map number', 'absent from reactants', 'reactants>>products'):
                if text not in errors:
                    missing.append('missing_map_diagnostic:' + text)
        if scenario == 'geometry':
            if not any(r.get('status') == 'success' and any(g.get('kind') == 'distance' and g.get('value') == 2.0
                       for g in r.get('geometry_checks', [])) for r in all_rows):
                missing.append('missing_distance_calculation')
            if not any(c.get('exit_code') == 0 and any(r.get('status') == 'success' and r.get('passed') is False
                       for r in rows(c.get('stdout'))) for c in observations):
                missing.append('missing_completed_failed_inspection')
            if not any(c.get('exit_code') == 2 and any(r.get('status') == 'error' and r.get('error', {}).get('code') == 'INVALID_REQUEST'
                       for r in rows(c.get('stdout'))) for c in observations):
                missing.append('missing_invalid_request_rejection')
    result['passed'] = not missing
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('batch', type=Path)
    parser.add_argument('scenario', choices=('descriptors-a', 'descriptors-b', 'atommap', 'geometry'))
    args = parser.parse_args()
    try:
        result = audit(args.batch, args.scenario)
    except Exception as exc:
        result = {'passed': False, 'scenario': args.scenario, 'audit_error': redact(str(exc))}
    write_json(args.batch / 'acceptance-audit.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}, ensure_ascii=False))
    sys.exit(0 if result['passed'] else 2)
