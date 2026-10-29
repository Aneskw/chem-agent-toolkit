"""Audit saved Open Babel business evidence; never execute models or business code."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import uuid

from audit_extended_acceptance import audit, rows
from creation_pipeline.records import file_digest, read_json, write_json, redact
from creation_pipeline.runtime.coverage import business_args


def ethanol_sdf(text):
    """Check actual atom/bond records, not a success banner or counts alone."""
    lines = text.splitlines()
    try:
        count_index = next(i for i, line in enumerate(lines) if 'V2000' in line)
        counts = lines[count_index]
        atoms, bonds = int(counts[:3]), int(counts[3:6])
        atom_lines = lines[count_index + 1:count_index + 1 + atoms]
        bond_lines = lines[count_index + 1 + atoms:count_index + 1 + atoms + bonds]
        elements = Counter(line[31:34].strip() for line in atom_lines)
        edges = [(int(line[:3]), int(line[3:6]), int(line[6:9])) for line in bond_lines]
        if (atoms, bonds, elements) != (3, 2, Counter({'C': 2, 'O': 1})):
            return False
        if len({tuple(sorted((a, b))) for a, b, _ in edges}) != 2:
            return False
        degrees = Counter(n for a, b, _ in edges for n in (a, b))
        oxygen = [i + 1 for i, line in enumerate(atom_lines) if line[31:34].strip() == 'O']
        if len(oxygen) != 1 or degrees[oxygen[0]] != 1:
            return False  # Reject C-O-C: the supplied SMILES is C-C-O.
        return (len(bond_lines) == 2 and all(1 <= a <= 3 and 1 <= b <= 3 and a != b and order == 1
                                           for a, b, order in edges)
                and len({n for a, b, _ in edges for n in (a, b)}) == 3
                and any(line.strip() == 'M  END' for line in lines) and '$$$$' in text)
    except (StopIteration, ValueError, IndexError):
        return False


def audit_openbabel(batch):
    result = audit(batch, 'generic')
    result['scenario'] = 'openbabel'
    output = Path(result['output'])
    record = read_json(next((output / 'records').glob('*.json')))
    detail = result['records'][0]
    ref = record['durable_evidence']
    frozen = output / ref['path']
    relative = 'scripts/convert_molecule.py'
    sources = [s for s in record['delivery']['inputs']['sources']
               if any(f['path'] == relative for f in s['inventory'])]
    plan = record['delivery']['inputs']['environment']['payload'].get('plan', {})
    if len(sources) != 1:
        result['missing'].append('unique_original_entry_source')
    else:
        original = frozen / 'sources' / sources[0]['id'] / relative
        delivered = frozen / 'package' / relative
        identical = delivered.is_file() and file_digest(delivered) == file_digest(original)
        detail['business_script_identical'] = identical
        if not identical:
            result['missing'].append('business_script_changed')
    if plan.get('script') != 'package/' + relative:
        result['missing'].append('original_script_not_bound_as_actual_entry')
    report = read_json(Path(detail['report'])) if detail.get('report') else {}
    cases = report.get('cases', [])
    # The normal Docker command uses the image's ENTRYPOINT, so it does not
    # repeat that executable in argv. Judge the locked invocation, like the gate.
    locked = read_json(frozen / 'runtime/locked-tests.json')['cases']
    by_name = {c['name']: c for c in locked}
    direct = [c for c in cases if c['name'] in by_name
              and business_args({'entrypoint': plan['entrypoint']}, by_name[c['name']]) is not None]
    normal = [c for c in direct if c.get('exit_code') == 0 and ethanol_sdf(c.get('persisted_output', ''))]
    detail['retained_ethanol_sdf_cases'] = [c['name'] for c in normal]
    if not any(any(r.get('ok') is True and r.get('input_format') == 'smi' and r.get('output_format') == 'sdf'
                   for r in rows(c.get('stdout', ''))) for c in normal):
        result['missing'].append('actual_ethanol_conversion_and_retained_sdf')
    rejected = [c for c in direct if c.get('exit_code') == 2 and '--output-format' in c.get('command', [])
                and c['command'][c['command'].index('--output-format') + 1] == 'nonexistent_format_xyz'
                and any(r.get('ok') is False and 'format' in str(r.get('error', '')).lower()
                        and r.get('status') != 'blocked_resources'
                        for r in rows(c.get('stdout', '')))]
    detail['format_rejection_cases'] = [c['name'] for c in rejected]
    if not rejected:
        result['missing'].append('actual_format_rejection')
    version = [c for c in cases if c.get('exit_code') == 0 and re.search(
        r'Open Babel\s+\d+\.\d+', c.get('stdout', '') + c.get('stderr', ''))]
    detail['obabel_version_evidence_cases'] = [c['name'] for c in version]
    if not version:
        result['missing'].append('real_obabel_version_evidence')
    if not result['missing']:
        # Independent executable metadata check in the bound image, not a
        # chemistry conversion and not another model/provider request.
        from creation_pipeline.runtime.runner import run
        from creation_pipeline.records import sanitized
        tool = {'limits': {'memory': '256m', 'cpus': '1'}, 'behavior': {'file_io': False},
                'runtime_network': False, 'execution_scope': 'openbabel-version-' + uuid.uuid4().hex}
        probe = sanitized(run(tool, detail['image_id'], ['-V'], entrypoint='obabel', timeout=30))
        detail['independent_obabel_version_probe'] = probe
        if probe.get('exit_code') != 0 or not re.search(r'Open Babel\s+\d+\.\d+', probe.get('stdout', '')):
            result['missing'].append('bound_image_obabel_metadata_probe_failed')
    result['passed'] = not result['missing']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('batch', type=Path)
    args = parser.parse_args()
    try:
        result = audit_openbabel(args.batch)
    except Exception as exc:
        result = {'passed': False, 'scenario': 'openbabel', 'audit_error': redact(str(exc))}
    write_json(args.batch / 'acceptance-audit.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}, ensure_ascii=False))
    sys.exit(0 if result['passed'] else 2)
