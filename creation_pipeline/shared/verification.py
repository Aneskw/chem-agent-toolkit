"""Selective verification tied to exact delivered snippets and scripts."""
import re
import uuid
import subprocess
from .environment import OperationError
from pathlib import Path
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.records import digest, file_digest, long_path, read_json, safe_relative, write_json, has_link
from creation_pipeline.runtime.runner import process
from .failures import IntegrityError, InfrastructureError
from .environment import fingerprint
from .observations import compact, event


LANGUAGES = {'python', 'py', 'bash', 'sh', 'shell', 'r', 'javascript', 'js', 'powershell', 'ps1'}


def code_units(package):
    """Inventory code without requiring that illustrative fragments be standalone programs."""
    units, occurrences = [], {}
    def append(path, start, end, language, code):
        key = fingerprint({'path': path, 'code': code})[:12]
        occurrences[key] = occurrences.get(key, 0) + 1
        units.append({'unit_id': 'unit-' + key + '-' + str(occurrences[key]), 'file': path,
                      'start_line': start, 'end_line': end, 'language': language,
                      'sha256': digest(code.encode())})
    for entry in manifest(package):
        path = Path(package) / entry['path']
        suffix = path.suffix.lower().lstrip('.')
        if suffix not in LANGUAGES | {'md'}:
            continue
        text = path.read_text(encoding='utf-8')
        lines = text.splitlines(keepends=True)
        if suffix != 'md':
            if text.strip():
                append(entry['path'], 1, len(lines), suffix, text)
            continue
        opening = None
        for n, line in enumerate(lines, 1):
            if opening:
                start, fence, language = opening
                if re.match(r'^\s*' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*$', line):
                    code = ''.join(lines[start:n-1])
                    if code.strip() and (not language or language in LANGUAGES):
                        append(entry['path'], start + 1, n - 1, language, code)
                    opening = None
            else:
                match = re.match(r'^\s*(`{3,}|~{3,})([\w+-]*)\s*$', line)
                if match:
                    opening = (n, match[1], match[2].lower())
    return units


def validate_decisions(package, decisions, items):
    units = {u['unit_id']: u for u in code_units(package)}
    if len(decisions) != len(units) or {d['unit_id'] for d in decisions} != set(units):
        raise ReviewPlanError('Every code inventory unit needs one explicit execution/exemption decision')
    necessary = {i['id']: i for i in items if i['necessary']}
    used = []
    for decision in decisions:
        unit = units[decision['unit_id']]
        if not decision['reason'].strip():
            raise ReviewPlanError('Code decisions require reasons')
        if decision['decision'] == 'execute':
            if not decision['execution_ids']:
                raise ReviewPlanError('Execute decision needs necessary item IDs')
            for iid in decision['execution_ids']:
                item = necessary.get(iid)
                if not item or item['file'] != unit['file'] or not unit['start_line'] <= item['start_line'] <= item['end_line'] <= unit['end_line']:
                    raise ReviewPlanError('Execution item must select original code within its inventory unit')
                used.append(iid)
        elif decision['decision'] in {'exempt', 'runtime_example'}:
            if decision['execution_ids']:
                raise ReviewPlanError('Exempt decisions must not name necessary checks')
            if decision['decision'] == 'runtime_example' and unit['language'] not in {'sh', 'bash', 'shell', 'powershell', 'ps1'}:
                raise ReviewPlanError('Business code cannot be classified as a Docker runtime command')
        else:
            raise ReviewPlanError('Unknown code decision')
    if set(used) != set(necessary) or len(used) != len(set(used)):
        raise ReviewPlanError('Every necessary item must belong to exactly one code decision')


def direct_case(item, case):
    command = list(case['command'])
    if not command:
        return False
    interpreter = Path(command.pop(0)).name.lower()
    valid = {'.py': {'python', 'python3', 'python3.11'}, '.sh': {'sh', 'bash'}, '.R': {'rscript'}}
    if interpreter not in valid.get(item['suffix'], set()):
        return False
    while command and command[0] in {'-u', '-B', '-I', '--'}:
        command.pop(0)
    return bool(command) and command[0] in {'/code/' + item['id'] + item['suffix'], '/skill/' + item['file']}


def requires_audit(items, plan):
    by_id = {i['id']: i for i in items}
    return bool(plan['audit_risks'] or plan['deferred'] or any(
        not direct_case(by_id[c['item_id']], c) or any(Path(f['path']).suffix.lower() in {'.py', '.sh', '.r', '.js', '.ps1'} for f in c['files'])
        for c in plan['cases']))


def execution_key(package, environment, item, case):
    payload = [e for e in manifest(package) if e['path'] != 'SKILL.md']
    code = [{k: u[k] for k in ('file', 'sha256')} for u in code_units(package)]
    return fingerprint({'content': environment.get('content_id') or environment.get('digest') or environment.get('tag'),
                        'platform': environment['platform'], 'payload': payload, 'code': code,
                        'item': {k: item[k] for k in ('file', 'sha256', 'expected_check')}, 'case': case})


class ReviewPlanError(ValueError):
    """Invalid reviewer execution ranges; return to the reviewer."""


class TestPlanError(ValueError):
    """Invalid test-support metadata, not evidence of a defective Skill."""


def bind_items(package, items, workspace=None):
    seen, result = set(), []
    for item in items:
        name = item['id']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or name in seen:
            raise ReviewPlanError('Execution item IDs must be unique slugs')
        seen.add(name)
        try:
            path = safe_relative(Path(package), item['file'])
        except ValueError as exc:
            raise ReviewPlanError(str(exc)) from exc
        if not path.is_file() and workspace is not None:
            try:
                alternative = safe_relative(Path(workspace), item['file'])
            except ValueError as exc:
                raise ReviewPlanError(str(exc)) from exc
            if alternative.is_file() and alternative.resolve().is_relative_to(Path(package).resolve()):
                path = alternative
                item = {**item, 'file': path.resolve().relative_to(Path(package).resolve()).as_posix()}
        if not path.is_file():
            raise ReviewPlanError('Reviewer selected a missing package file: ' + item['file'])
        lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
        start, end = item['start_line'], item['end_line']
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
            raise ReviewPlanError('Invalid execution item line range')
        if not item['reason'].strip() or item['necessary'] and not item['expected_check'].strip():
            raise ReviewPlanError('Execution decisions need reasons and necessary checks')
        code = ''.join(lines[start-1:end])
        if path.suffix == '.md' and ('```' in code or '~~~~' in code):
            raise ReviewPlanError('Markdown execution range must select code only, without fences')
        language = path.suffix.lstrip('.')
        if path.suffix == '.md':
            fences = [re.match(r'^\s*```([\w+-]*)', l) for l in lines[:start-1]]
            language = next((m.group(1).lower() for m in reversed(fences) if m and m.group(1)), 'python')
        suffix = {'python': '.py', 'py': '.py', 'bash': '.sh', 'shell': '.sh', 'sh': '.sh', 'r': '.R'}.get(language, path.suffix)
        if item['necessary'] and suffix == '.md':
            raise ReviewPlanError('Execution item needs an identifiable code language')
        result.append({**item, 'code': code, 'suffix': suffix, 'sha256': digest(code.encode())})
    return result


def validate_plan(items, plan):
    necessary = {i['id']: i for i in items if i['necessary']}
    covered = []
    def work_relative(value):
        if value.startswith('/work/'):
            value = value[len('/work/'):]
        from pathlib import PurePosixPath
        if not value or PurePosixPath(value).is_absolute() or '..' in PurePosixPath(value).parts or '\\' in value or ':' in value:
            raise TestPlanError('Test fixture paths must be relative to /work')
        return value
    for case in plan['cases']:
        for value in case.get('inputs', []):
            value['target'] = work_relative(value['target'])
        for fixture in case['files']:
            fixture['path'] = work_relative(fixture['path'])
        case['output_files'] = [work_relative(f) for f in case['output_files']]
        iid = case['item_id']
        if iid not in necessary or not case['command'] or not case['basis'].strip():
            raise TestPlanError('Unknown or unsupported execution case')
        if not (case['stdout_contains'] or case['check_command']):
            raise TestPlanError('Check output content or a source-backed result; exit/file existence alone is insufficient')
        covered.append(iid)
    for item in plan['deferred']:
        if item['item_id'] not in necessary or not item['reason'].strip() or not item['resume_when'].strip():
            raise TestPlanError('Deferred items need a concrete condition and resumption requirement')
        covered.append(item['item_id'])
    if set(covered) != set(necessary) or len(covered) != len(set(covered)):
        raise TestPlanError('Each necessary item needs exactly one case or deferral')


def execute(package, image, platform, items, plan, work, timeout, run=process, *, audited=False):
    validate_plan(items, plan)
    before = manifest(package)
    def invoke(command):
        operation = uuid.uuid4().hex[:12]
        event(work, operation=operation, status='started', command=command[-3:])
        try:
            result = run(command, timeout)
        except subprocess.TimeoutExpired as exc:
            event(work, operation=operation, status='timeout')
            raise OperationError('Validation operation timed out', {'command': command[:3], 'timeout': timeout}) from exc
        except (OSError, KeyboardInterrupt):
            event(work, operation=operation, status='interrupted')
            raise
        event(work, operation=operation, status='completed', exit_code=result['exit_code'])
        return result
    observations = []
    for case in plan['cases']:
        item = next(i for i in items if i['id'] == case['item_id'])
        if not direct_case(item, case) and not audited:
            raise TestPlanError('A wrapper invocation requires independent audit; a path argument alone is insufficient')
        directory = Path(work) / ('case-' + uuid.uuid4().hex)
        code, task = directory / 'code', directory / 'work'
        long_path(code).mkdir(parents=True)
        long_path(task).mkdir()
        suffix = item['suffix']
        entry = item['id'] + suffix
        long_path(code / entry).write_text(item['code'], encoding='utf-8')
        for f in case['files']:
            target = safe_relative(task, f['path'])
            target = long_path(target)
            if target.exists():
                raise TestPlanError('Duplicate test fixture path')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f['content'], encoding='utf-8')
        # Audit stage checks that wrappers actually call these immutable paths.
        original = '/code/' + entry
        if original not in case['command'] and '/skill/' + item['file'] not in case['command']:
            raise TestPlanError('Execution command must explicitly reference the original code')
        name = 'chem-selective-' + uuid.uuid4().hex
        prefix = ['docker', 'run', '--rm', '--name', name, '--platform', platform,
                  '--mount', f'type=bind,source={Path(package).resolve()},target=/skill,readonly',
                  '--mount', f'type=bind,source={code.resolve()},target=/code,readonly',
                  '--mount', f'type=bind,source={task.resolve()},target=/work', '--workdir', '/work']
        if case.get('inputs') and len(case.get('_inputs', [])) != len(case['inputs']):
            raise TestPlanError('Resolve declared binary inputs before execution')
        for source in case.get('_inputs', []):
            host = Path(source['host_path'])
            if has_link(host) or file_digest(host) != source['sha256']:
                raise TestPlanError('Binary test input changed after preparation')
            target = safe_relative(task, source['target'])
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise TestPlanError('Binary input overlaps a text fixture')
            prefix += ['--mount', f'type=bind,source={host.resolve()},target=/work/{source["target"]},readonly']
        try:
            output = invoke([*prefix, image, *case['command']])
            if output['exit_code'] == 125:
                raise InfrastructureError('Docker failed to start the validation container', output)
            checks = {'exit': output['exit_code'] == case['expected_exit'],
                      'stdout': all(s in output['stdout'] for s in case['stdout_contains']),
                      'files': all(long_path(safe_relative(task, f)).is_file() for f in case['output_files'])}
            checker = None
            if case['check_command']:
                checker = invoke([*prefix, image, *case['check_command']])
                if checker['exit_code'] == 125:
                    raise InfrastructureError('Docker failed to start the result-check container', checker)
                checks['result_check'] = checker['exit_code'] == 0
            observation = {'item_id': item['id'], 'status': 'passed' if all(checks.values()) else 'failed',
                           'checks': checks, 'command': output, 'checker': checker,
                           'code_sha256': item['sha256'], 'artifacts': task.relative_to(Path(work)).as_posix()}
            if observation['status'] == 'passed':
                # Assertions above used actual output; keep qualification facts, not routine logs.
                observation['command'] = {'exit_code': output['exit_code']}
                observation['checker'] = {'exit_code': checker['exit_code']} if checker else None
            else:
                observation = compact(observation, work)
        finally:
            # A killed client may leave its container; only this case's owned name is removed.
            try:
                run(['docker', 'rm', '--force', name], 30 if timeout is None else min(30, timeout))
            except OSError:
                pass
        observations.append(observation)
        write_json(directory / 'receipt.json', observation)
    if manifest(package) != before:
        raise IntegrityError('Execution changed the delivered package')
    return {'status': 'failed' if any(o['status'] == 'failed' for o in observations)
            else 'pending-validation' if plan['deferred'] else 'verified',
            'observations': observations, 'deferred': plan['deferred']}
