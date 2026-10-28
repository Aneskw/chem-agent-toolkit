"""Adapt runtime_model_lifecycle.validate/evidence to frozen inputs and sidecar attempts."""
import copy
import json
from pathlib import Path
from creation_pipeline.records import read_json, write_json, now, sanitized, file_digest
from creation_pipeline.contracts import fingerprint
from . import runner
from .coverage import acceptance_coverage


def tool_for(record, request):
    env = record['delivery']['inputs']['environment']['payload']
    p = env['plan']
    return {'entrypoint': p['entrypoint'], 'limits': env['limits'], 'runtime_network': p['runtime_network'],
            'behavior': {'file_io': p['file_io']}, 'acceptance_version': 2,
            'acceptance_policy': json.loads(p['acceptance_json']),
            'input_anchors': (record['delivery']['inputs']['acceptance']['payload'] or {}).get('input_anchors') or {},
            'source_mount': str(Path(request.frozen_directory) / 'sources'), 'execution_scope': Path(request.attempt_directory).name}


def expected_image_files(record, request):
    p = record['delivery']['inputs']['environment']['payload']['plan']
    context = Path(request.frozen_directory) / 'runtime/context'
    names = set(p['source_files']) | {'package/' + f['path'] for f in record['delivery']['inputs']['files']}
    return {name: file_digest(context / name) for name in sorted(names)}


def image_files_match(observation, expected):
    actual = {line[66:]: line[:64] for line in observation.get('stdout', '').splitlines() if len(line) > 66}
    return observation.get('exit_code') == 0 and actual == expected


def locked_inputs(record, request):
    from .preparation import validate
    from .checks import mapped_checks
    d = record['delivery']; env = d['inputs']['environment']['payload']
    root = Path(request.frozen_directory)
    index = {'files': {}}
    for f in d['inputs']['files']:
        index['files']['package/' + f['path']] = {'size': f['bytes'], 'sha256': f['sha256']}
    for source in d['inputs']['sources']:
        for f in source['inventory']:
            index['files']['sources/' + source['id'] + '/' + f['path']] = {'size': f['bytes'], 'sha256': f['sha256']}
    index['read_files'] = list(index['files'])
    from .entry import verify_material, runtime_path
    binding = d['inputs']['bindings']['payload']
    verify_material(root / 'package', binding, root / 'runtime/context')
    if binding.get('kind') == 'markdown_python':
        path = runtime_path(binding)
        p = root / 'runtime/context' / path
        index['files'][path] = {'size': p.stat().st_size, 'sha256': file_digest(p)}
        index['read_files'].append(path)
    # Planner may quote provenance material included in the verified context.
    for name in env['plan']['source_files']:
        if name == 'source-identities.json':
            p = root / 'runtime/context' / name
            index['files'][name] = {'size': p.stat().st_size, 'sha256': file_digest(p)}
            index['read_files'].append(name)
    cases = validate(env['plan'], index, root, d['inputs']['bindings']['payload'], env['limits'],
                     anchors=(d['inputs']['acceptance']['payload'] or {}).get('input_anchors'))
    cases += mapped_checks(d['inputs']['acceptance']['payload'].get('author_tests', {}), env['plan'], [s['id'] for s in d['inputs']['sources']])
    locked = read_json(root / 'runtime/locked-tests.json')
    if (fingerprint(cases) != fingerprint(locked['cases'])
            or fingerprint(cases) != fingerprint(d['inputs']['acceptance']['payload']['cases'])):
        raise ValueError('Locked tests differ from revalidated source/plan/check declarations')
    if fingerprint(locked['policy']) != fingerprint(json.loads(env['plan']['acceptance_json'])):
        raise ValueError('Locked acceptance policy changed')
    return cases


def states(cases):
    # Migrated runtime_model_lifecycle.states; unsupported observations do not count.
    result = {}
    for layer in ('environment', 'interface', 'behavior'):
        group = [c for c in cases if c.get('layer') == layer and c.get('oracle_status') == 'supported']
        result[layer] = 'not_verified' if not group else 'passed' if all(c['status'] == 'passed' for c in group) else 'failed'
    return result


def classification(cases, observations):
    """Never interpret business output words as missing infrastructure."""
    failed = [o for o in observations if o.get('oracle_status') == 'supported' and o['status'] != 'passed']
    if not failed:
        return None
    # An assertion failure alone proves neither bad source nor a bad oracle.
    by_name = {c['name']: c for c in cases}
    wrong_results = [o for o in failed if o.get('layer') != 'environment' and o.get('exit_code') == by_name[o['name']].get('expected_exit', 0)]
    failed_probes = [o for o in failed if o.get('layer') == 'environment'
                     and type(o.get('exit_code')) is int and o['exit_code'] != 0
                     and o['exit_code'] != by_name[o['name']].get('expected_exit', 0)]
    return 'environment' if not wrong_results and failed_probes else 'unknown'


def validate(executor, request, build):
    from .local import binding_identity
    record, env, materials = executor.inputs(request)
    root = Path(request.attempt_directory) / 'execution'
    root.mkdir(parents=True, exist_ok=False)
    report = {'version': 1, 'acceptance_version': 2, 'request': binding_identity(request),
              'started_at': now(), 'status': 'runtime_blocked', 'cases': [], 'image_id': build.get('image_id'),
              'tag': build.get('tag'), 'build_receipt_sha256': file_digest(Path(request.attempt_directory) / 'receipt.json')}
    write_json(root / 'started.json', report)
    current = executor.verify_current(request, build)
    report['current_host'] = current
    if build['status'] != 'built' or current['status'] != 'available':
        report.update(gaps=[{'code': 'image_or_resource_unavailable', 'detail': 'Current image/resource verification failed'}], repair_lane='resource')
    else:
        cases = locked_inputs(record, request)
        report['locked_cases_sha256'] = fingerprint(cases)
        tool = tool_for(record, request)
        import shlex
        expected = expected_image_files(record, request)
        try:
            integrity = runner.run(tool, build['image_id'], ['-c', 'cd /opt/skill && sha256sum -- ' + ' '.join(shlex.quote(n) for n in expected)],
                                   entrypoint='/bin/sh', timeout=executor.probe_timeout)
        except (OSError, runner.subprocess.TimeoutExpired) as exc:
            integrity = {'error': str(exc), 'cleanup': getattr(exc, 'cleanup', []), 'scope': getattr(exc, 'scope', None)}
        report['source_integrity'] = sanitized(integrity)
        if not image_files_match(integrity, expected):
            report.update(status='execution_failed', repair_lane='environment', gaps=[{'code': 'image_source_integrity', 'detail': 'Image source/support bytes failed integrity verification'}], finished_at=now())
            write_json(root / 'report.json', report)
            return report
        observations = []
        for case in cases:
            observed = runner.run_case(materials, tool, build['image_id'], case, deadline=executor.deadline,
                                       artifact_dir=root / ('case-' + fingerprint(case['name'])[:16]))
            observed = sanitized(observed)
            observations.append(observed)
            write_json(root / 'tests.json', {'cases': observations})
        report.update(cases=observations, validation=states(observations), acceptance=acceptance_coverage(tool, cases, observations))
        lane = classification(cases, observations)
        report.update(status='execution_failed' if lane or not report['acceptance']['complete'] else 'execution_passed',
                      repair_lane=lane or ('contract' if not report['acceptance']['complete'] else None), gaps=[])
        if report['repair_lane']:
            report['diagnosis'] = {'attribution': report['repair_lane'],
                'basis': 'Environment probe failure' if lane == 'environment' else
                         'Observed check failure is not proof of defective Skill code; source diagnosis required',
                'failed_cases': [o['name'] for o in observations if o['status'] != 'passed'],
                'next_action': 'environment_repair' if lane == 'environment' else 'source_diagnosis'}
        executor.inputs(request)
        after = executor.verify_current(request, build)
        report['current_host'] = after
        if after['status'] != 'available' and (report['status'] == 'execution_passed' or all(o.get('exit_code') in {None, 125} for o in observations)):
            report.update(status='runtime_blocked', repair_lane='resource', gaps=[{'code': 'runtime_changed', 'detail': 'Image/resources changed during execution'}])
    report['finished_at'] = now()
    write_json(root / 'report.json', report)
    return report


def observations_pass(cases, observations, image_id, directory):
    """Re-evaluate immutable raw results and persisted bytes; never trust passed flags."""
    if len(cases) != len(observations) or [c['name'] for c in cases] != [o.get('name') for o in observations]:
        return False
    for c, o in zip(cases, observations):
        if c.get('oracle_status') != 'supported':
            continue
        if o.get('status') != 'passed' or o.get('timed_out') or o.get('error'):
            return False
        runs = o.get('runs', [o])
        expected_runs = c.get('relation', {}).get('runs', [c])
        if len(runs) != len(expected_runs):
            return False
        for r, spec in zip(runs, expected_runs):
            cmd = r.get('command', [])
            suffix = [image_id, *spec['args']]
            if r.get('exit_code') != c.get('expected_exit', 0) or cmd[-len(suffix):] != suffix or cmd[:2] != ['docker', 'run']:
                return False
            entry = spec.get('entrypoint') or c.get('entrypoint')
            if entry and ('--entrypoint' not in cmd or cmd[cmd.index('--entrypoint')+1] != entry):
                return False
        if c.get('relation'):
            if not runner.relation_matches(c, runs):
                return False
        else:
            text = o['stdout']
            if c.get('output_file'):
                path = Path(directory) / ('case-' + fingerprint(c['name'])[:16]) / c['output_file']
                if not path.is_file() or path.is_symlink():
                    return False
                text = path.read_text(encoding='utf-8')
                if text != o.get('persisted_output'):
                    return False
            if not runner.output_matches(c, o, text):
                return False
            for name in c.get('artifacts', []):
                artifact = Path(directory) / ('case-' + fingerprint(c['name'])[:16]) / name
                if not artifact.is_file() or (c.get('mapped_check') and artifact.stat().st_size == 0):
                    return False
        artifacts = o.get('output_artifacts', {})
        if artifacts.get('omitted'):
            return False
        for name, f in artifacts.get('files', {}).items():
            from creation_pipeline.records import safe_relative
            path = safe_relative(Path(directory) / ('case-' + fingerprint(c['name'])[:16]), name)
            if file_digest(path) != f['sha256'] or path.stat().st_size != f['bytes']:
                return False
    return True


def evidence(executor, request, build, directory):
    """Migrated lifecycle.evidence + strict_acceptance: recheck all current inputs."""
    record, env, _ = executor.inputs(request)
    report = read_json(Path(directory) / 'report.json')
    from .local import binding_identity
    cases = locked_inputs(record, request)
    if (report.get('acceptance_version') != 2 or report.get('status') != 'execution_passed'
            or report['request'] != binding_identity(request) or report['image_id'] != build['image_id'] or report['tag'] != build['tag']
            or report['locked_cases_sha256'] != fingerprint(cases)
            or report['build_receipt_sha256'] != file_digest(Path(directory).parent / 'receipt.json')):
        raise ValueError('Execution report is not bound to this input/image/test revision')
    if not image_files_match(report.get('source_integrity', {}), expected_image_files(record, request)):
        raise ValueError('Image source/support integrity evidence is invalid')
    if not observations_pass(cases, report['cases'], build['image_id'], directory):
        raise ValueError('Current raw results or retained outputs do not satisfy locked assertions')
    coverage = acceptance_coverage(tool_for(record, request), cases, report['cases'])
    current = executor.verify_current(request, build)
    if not coverage['complete'] or current['status'] != 'available':
        raise ValueError('Current acceptance coverage/image/resources are not valid')
    measured_engine = report.get('current_host', {}).get('preflight', {}).get('host', {}).get('engine_id')
    current_engine = current.get('preflight', {}).get('host', {}).get('engine_id')
    if not measured_engine or current_engine != measured_engine:
        raise ValueError('Execution host changed or is unbound; explicit revalidation required')
    return {'status': 'execution_passed', 'acceptance_version': 2, 'current_acceptance_validated': True}
