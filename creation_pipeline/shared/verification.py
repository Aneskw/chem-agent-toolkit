"""Selective verification tied to exact delivered snippets and scripts."""
import re
import uuid
import subprocess
from .environment import OperationError
from pathlib import Path
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.records import digest, read_json, safe_relative, write_json
from creation_pipeline.runtime.runner import process
from .failures import IntegrityError, InfrastructureError


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
        for fixture in case['files']:
            fixture['path'] = work_relative(fixture['path'])
        case['output_files'] = [work_relative(f) for f in case['output_files']]
        iid = case['item_id']
        if iid not in necessary or not case['command'] or not case['basis'].strip():
            raise TestPlanError('Unknown or unsupported execution case')
        if not (case['stdout_contains'] or case['output_files'] or case['check_command']):
            raise TestPlanError('A successful exit alone is not a result check')
        covered.append(iid)
    for item in plan['deferred']:
        if item['item_id'] not in necessary or not item['reason'].strip() or not item['resume_when'].strip():
            raise TestPlanError('Deferred items need a concrete condition and resumption requirement')
        covered.append(item['item_id'])
    if set(covered) != set(necessary) or len(covered) != len(set(covered)):
        raise TestPlanError('Each necessary item needs exactly one case or deferral')


def execute(package, image, platform, items, plan, work, timeout, run=process):
    validate_plan(items, plan)
    before = manifest(package)
    def invoke(command):
        try:
            return run(command, timeout)
        except subprocess.TimeoutExpired as exc:
            raise OperationError('Validation operation timed out', {'command': command[:3], 'timeout': timeout}) from exc
    observations = []
    for case in plan['cases']:
        item = next(i for i in items if i['id'] == case['item_id'])
        directory = Path(work) / ('case-' + item['id'] + '-' + uuid.uuid4().hex)
        code, task = directory / 'code', directory / 'work'
        code.mkdir(parents=True)
        task.mkdir()
        suffix = item['suffix']
        entry = item['id'] + suffix
        (code / entry).write_text(item['code'], encoding='utf-8')
        for f in case['files']:
            target = safe_relative(task, f['path'])
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
        try:
            output = invoke([*prefix, image, *case['command']])
            if output['exit_code'] == 125:
                raise InfrastructureError('Docker failed to start the validation container', output)
            checks = {'exit': output['exit_code'] == case['expected_exit'],
                      'stdout': all(s in output['stdout'] for s in case['stdout_contains']),
                      'files': all(safe_relative(task, f).is_file() for f in case['output_files'])}
            checker = None
            if case['check_command']:
                checker = invoke([*prefix, image, *case['check_command']])
                if checker['exit_code'] == 125:
                    raise InfrastructureError('Docker failed to start the result-check container', checker)
                checks['result_check'] = checker['exit_code'] == 0
            observation = {'item_id': item['id'], 'status': 'passed' if all(checks.values()) else 'failed',
                           'checks': checks, 'command': output, 'checker': checker,
                           'code_sha256': item['sha256'], 'artifacts': task.relative_to(Path(work)).as_posix()}
        finally:
            # A killed client may leave its container; only this case's owned name is removed.
            try:
                run(['docker', 'rm', '--force', name], min(30, timeout))
            except OSError:
                pass
        observations.append(observation)
        write_json(directory / 'receipt.json', observation)
    if manifest(package) != before:
        raise IntegrityError('Execution changed the delivered package')
    return {'status': 'failed' if any(o['status'] == 'failed' for o in observations)
            else 'pending-validation' if plan['deferred'] else 'verified',
            'observations': observations, 'deferred': plan['deferred']}
