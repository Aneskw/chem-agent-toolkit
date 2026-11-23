"""Immutable tool-only contexts, concrete probes and verified version tags."""
import json
import re
import shutil
import tempfile
import uuid
import subprocess
from .registry import Registry, RegistryError
from .environment_state import locations, locked
from .environment_metadata import describe, index_entry, observation, restore, state_path
from creation_pipeline.records import now
from .contracts import CONTRACT_VERSION, validate, runtime, tool_name, tool_version, bundled
from pathlib import Path

from creation_pipeline.records import digest, file_digest, has_link, read_json, safe_relative, write_json
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.runtime.runner import process


def fingerprint(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


class EnvironmentPlanError(ValueError):
    pass


class PublicationPending(ValueError):
    def __init__(self, message, record):
        super().__init__(message)
        self.record = record


class OperationError(ValueError):
    def __init__(self, message, observation=None):
        super().__init__(message)
        self.observation = observation


def timeout_observation(command, timeout, error):
    def decoded(value):
        return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''
    return {'command': command[:3], 'timeout': timeout,
            'stdout': decoded(error.output), 'stderr': decoded(error.stderr),
            'cleanup': getattr(error, 'cleanup', [])}


def run_checked(command, timeout, run=process):
    try:
        result = run(command, timeout)
    except subprocess.TimeoutExpired as exc:
        raise OperationError('Operation timed out', timeout_observation(command, timeout, exc)) from exc
    if result['exit_code'] != 0:
        raise OperationError('Operation failed: ' + ' '.join(command[:3]), result)
    return result


def inventory(root):
    root = Path(root)
    if has_link(root):
        raise ValueError('Linked environment library')
    with locked(root, 'catalog') as private:
        return _records(root, private)


def _records(root, private):
    path = root / 'catalog.json'
    values = read_json(path) if path.exists() else []
    valid, seen = [], set()
    for entry in values:
        value = restore(root, private, entry)
        key = (value['id'], value['version'])
        if key in seen:
            raise ValueError('Duplicate environment version in index')
        seen.add(key)
        directory = safe_relative(root, value['path'])
        if manifest(directory / 'context') != value['files']:
            raise ValueError('Environment build materials changed: ' + value['id'])
        valid.append(value)
    return valid


def compatible(record, plan):
    if record.get('contract_version') != CONTRACT_VERSION or plan.get('contract_version') != CONTRACT_VERSION:
        return False
    if record['platform'] != plan['platform'] or record['conditions']['accelerator'] != plan['conditions']['accelerator']:
        return False
    actual = {(x['kind'], tool_name(x['name'])): tool_version(x['version']) for x in record['tools']}
    if any(actual.get((x['kind'], tool_name(x['name']))) != tool_version(x['version']) for x in plan['tools']):
        return False
    resources = {(x['name'], x['version'], x['url']) for x in bundled(record)}
    return all((x['name'], x['version'], x['url']) in resources for x in bundled(plan))


class EnvironmentLibrary:
    def __init__(self, config, state, run=process, registry=None):
        self.settings = config['environments']
        self.root, self.state = Path(self.settings['root']), Path(state)
        self.library_state = locations(self.root)[1]
        self.run, self.timeout = run, self.settings['operation_timeout']
        self.registry = registry or Registry(self.timeout)

    def command(self, args):
        from .observations import event
        operation = uuid.uuid4().hex[:12]
        event(self.state, operation=operation, command=args[:3], status='started')
        try:
            result = run_checked(args, self.timeout, self.run)
        except (ValueError, OSError, KeyboardInterrupt) as exc:
            event(self.state, operation=operation, status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                  error=type(exc).__name__)
            raise
        event(self.state, operation=operation, status='passed', exit_code=result['exit_code'])
        return result

    def records(self):
        return inventory(self.root)

    def persist(self, record):
        with locked(self.root, 'catalog'):
            path = self.root / 'catalog.json'
            records = _records(self.root, self.library_state)
            previous = next((r for r in records if (r['id'], r['version']) == (record['id'], record['version'])), None)
            public = describe(record)
            if previous:
                before = {k: v for k, v in describe(previous).items() if k not in {'image', 'digest'}}
                after = {k: v for k, v in public.items() if k not in {'image', 'digest'}}
                if before != after or (previous.get('fingerprint') and record.get('fingerprint')
                                      and previous['fingerprint'] != record['fingerprint']):
                    raise ValueError('Immutable environment materials changed')
            self._store(record, public)
            # Existing full entries remain readable until their metadata is compacted.
            raw = read_json(path) if path.exists() else []
            write_json(path, [r for r in raw if (r['id'], r['version']) != (record['id'], record['version'])] + [index_entry(record)])
        return record

    def _store(self, record, public):
        if 'anonymous_pull' in record:
            receipt = safe_relative(self.library_state, 'observations/' + record['id'] + '/' + record['version'] + '/anonymous-pull.json')
            write_json(receipt, {'image': record.get('image'), 'digest': record.get('digest'),
                'at': now(), 'observation': record['anonymous_pull']})
        write_json(state_path(self.library_state, record), observation(record, public))
        write_json(safe_relative(self.root, record['path']) / 'environment.json', public)

    def compact(self):
        """Rewrite portable metadata without building images or changing references."""
        with locked(self.root, 'catalog'):
            records = _records(self.root, self.library_state)
            descriptions = [describe(record) for record in records]
            for record, public in zip(records, descriptions):
                self._store(record, public)
            write_json(self.root / 'catalog.json', [index_entry(r) for r in records])
        return records

    def remote_tag(self, eid, version):
        repository = self.settings.get('repository') or self.settings.get('image_prefix')
        if not repository:
            raise EnvironmentPlanError('Configure environments.repository before publication')
        return repository.rstrip('/') + ':' + eid + '-' + version

    def reserve(self, eid):
        with locked(self.root, 'versions') as private:
            path = private / 'versions.json'
            counters = read_json(path) if path.exists() else {}
            existing = [int(r['version'][1:]) for r in self.records() if r['id'] == eid
                        and re.fullmatch(r'v[1-9][0-9]*', r['version'])]
            number = max([counters.get(eid, 0)] + existing) + 1
            while self.settings.get('publish', True) and self.registry.resolve(self.remote_tag(eid, 'v' + str(number)), authenticated=True) is not None:
                number += 1
            counters[eid] = number
            write_json(path, counters)
            return 'v' + str(number)

    def ensure(self, plan, work):
        try:
            validate(plan)
        except ValueError as exc:
            raise EnvironmentPlanError(str(exc)) from exc
        if plan['conditions']['accelerator'] != 'none':
            raise EnvironmentPlanError('GPU execution is not yet supported by this workflow')
        records = self.records()
        suitable = sorted((r for r in records if compatible(r, plan)), key=lambda r: (len(r['tools']), r['id'], r['version']))
        for record in suitable:
            if record.get('image'):
                self.command(['docker', 'pull', '--platform', plan['platform'], record['image'].split(':', 1)[0] + '@' + record['digest']])
            else:
                # A catalogue entry survives Docker's local image pruning.
                # Missing unpublished content cannot grant reuse qualification.
                try:
                    self.command(['docker', 'image', 'inspect', record.get('content_id') or record['tag']])
                except OperationError as exc:
                    error = (exc.observation or {}).get('stderr', '').lower()
                    if 'no such image' in error or 'no such object' in error:
                        continue
                    raise
            # Probe this exact image for current requirements even when library observations exist.
            self.probe(record.get('content_id') or record['tag'], plan, work)
            return {**record, 'reuse': True, 'checks': 'passed'}
        if plan['selection'] == 'reuse':
            raise EnvironmentPlanError('Selected existing environment does not satisfy requirements')
        base = plan['base_image']
        if plan['selection'] == 'extend':
            parents = [r for r in records if r['id'] == plan['environment_id']]
            if plan.get('environment_version'):
                parents = [r for r in parents if r['version'] == plan['environment_version']]
            if not parents:
                raise EnvironmentPlanError('Extension parent not found')
            if len(parents) != 1:
                raise EnvironmentPlanError('Choose an explicit environment_version for extension')
            parent = parents[-1]
            if not compatible({**parent, 'platform': plan['platform'], 'tools': plan['tools'], 'resources': plan['resources'],
                               'conditions': plan['conditions']}, parent):
                raise EnvironmentPlanError('Extension must preserve the original tool/resource contract')
            if not parent.get('image'):
                raise EnvironmentPlanError('Unpublished parent: supply a new complete build context with selection=new, preserving required tools')
            base = parent['image'].split(':', 1)[0] + '@' + parent['digest']
        if not base or any(c.isspace() for c in base):
            raise EnvironmentPlanError('Environment needs a concrete base image')
        self.command(['docker', 'pull', '--platform', plan['platform'], base])
        inspected = json.loads(self.command(['docker', 'image', 'inspect', base])['stdout'])[0]
        if inspected.get('Os', 'linux') + '/' + inspected.get('Architecture', plan['platform'].split('/')[1]) != plan['platform']:
            raise EnvironmentPlanError('Observed base platform differs from requested platform')
        pinned = base if '@sha256:' in base else next((r for r in inspected.get('RepoDigests', []) if '@sha256:' in r), None)
        if not pinned:
            raise EnvironmentPlanError('Base image has no repository digest')
        context = Path(work) / ('context-' + uuid.uuid4().hex)
        context.mkdir(parents=True)
        for f in plan['files']:
            target = safe_relative(context, f['path'])
            if target.exists():
                raise EnvironmentPlanError('Duplicate build context path')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f['content'], encoding='utf-8')
        recipe = context / 'Dockerfile'
        if not recipe.exists():
            raise EnvironmentPlanError('Environment plan must include Dockerfile')
        text = recipe.read_text(encoding='utf-8')
        lines = text.splitlines()
        starts = [i for i, line in enumerate(lines) if re.match(r'^\s*FROM\s', line, re.I)]
        if len(starts) != 1:
            raise EnvironmentPlanError('Tool environment requires one explicit base stage')
        lines[starts[0]] = 'FROM ' + pinned
        # Generic environments accept caller argv, without a task-specific inherited entrypoint.
        lines.append('ENTRYPOINT []')
        recipe.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        if not (context / '.dockerignore').exists():
            (context / '.dockerignore').write_text('.git\n.pipeline\n', encoding='utf-8')
        files = manifest(context)
        identity = fingerprint({'files': files, 'platform': plan['platform'], 'base': pinned,
                                'tools': [{k: t[k] for k in ('name', 'kind', 'version')} for t in plan['tools']],
                                'resources': [{k: r[k] for k in ('name', 'url', 'version', 'included_in_image')} for r in bundled(plan)],
                                'accelerator': plan['conditions']['accelerator'],
                                'source_label': self.settings['source_url']})
        eid = plan['environment_id']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', eid):
            raise EnvironmentPlanError('Invalid environment ID')
        tag = 'chem-env:' + identity
        self.command(['docker', 'build', '--provenance=false', '--platform', plan['platform'], '--label',
                      'org.opencontainers.image.source=' + self.settings['source_url'], '-t', tag, str(context)])
        self.probe(tag, plan, work)
        observed = json.loads(self.command(['docker', 'image', 'inspect', tag])['stdout'])[0]
        content_id = observed['Id']
        version = self.reserve(eid)
        relative = eid + '/' + version
        with locked(self.root, 'catalog'):
            destination = safe_relative(self.root, relative)
            if destination.exists():
                if manifest(destination / 'context') != files:
                    raise EnvironmentPlanError('Immutable environment version collision')
            else:
                destination.mkdir(parents=True)
                shutil.copytree(context, destination / 'context')
            record = {'id': eid, 'version': version, 'path': relative, 'files': files,
                      'contract_version': CONTRACT_VERSION, 'platform': plan['platform'], 'base_image': pinned,
                      'tools': plan['tools'], 'resources': bundled(plan),
                      'conditions': plan['conditions'],
                      'tag': tag, 'content_id': content_id, 'fingerprint': identity,
                      'state': 'built', 'image': None, 'digest': None, 'anonymous_access': {'status': 'unverified'},
                      'reuse': False, 'checks': 'passed'}
        return self.persist(record)

    def probe(self, image, plan, work):
        observations = []
        resources = set()
        for tool in plan['tools']:
            probe = tool['probe']
            prefix = ['docker', 'run', '--rm', '--platform', plan['platform']]
            if probe[0] in {'@python-version', '@python-import'}:
                if probe[0] == '@python-import' and len(probe) != 2:
                    raise EnvironmentPlanError('A common import probe needs an explicit import module')
                checker = Path(__file__).with_name('runtime_probe.py').resolve()
                command = [*prefix, '--mount', f'type=bind,source={checker},target=/pipeline-check.py,readonly',
                           image, 'python', '/pipeline-check.py', tool['name']]
                if probe[0] == '@python-import':
                    command.append(probe[1])
            else:
                command = [*prefix, image, *probe]
            observation = self.command(command)
            try:
                fact = json.loads(observation['stdout'].strip())
            except (ValueError, TypeError) as exc:
                raise OperationError('Tool probe must report JSON with its observed version', observation) from exc
            observed_version = fact.get('version')
            if not isinstance(observed_version, str) or tool_version(observed_version) != tool_version(tool['version']):
                raise OperationError('Observed tool version differs from environment contract: ' + tool['name'], observation)
            resources.update(k for k, v in fact.get('resources', {}).items() if v is True)
            observations.append({'tool': tool['name'], 'version': observed_version})
        required = {r['name'] for r in plan['resources'] if r['included_in_image']}
        if not required.issubset(resources):
            raise OperationError('Basic probes did not verify bundled resources: ' + ', '.join(sorted(required - resources)))
        write_json(Path(work) / 'environment-check.json', {'image': image,
            'definition': fingerprint({'tools': plan['tools'], 'resources': bundled(plan),
                'checker': file_digest(Path(__file__).with_name('runtime_probe.py'))}),
            'tools': observations})

    def verify_public(self, record):
        if not record.get('image') or not record.get('digest'):
            raise RegistryError('A published tag and internal content digest are required')
        try:
            proof = self.registry.public(record['image'], record['digest'], record['platform'])
        except RegistryError as exc:
            self.persist({**record, 'anonymous_access': {'status': 'unavailable', 'reason': str(exc), 'checked_at': now()}})
            raise
        return self.persist({**record, 'anonymous_access': proof})

    def anonymous_pull(self, image, digest, platform):
        # An empty directory alone lets Docker auto-select the OS credential store.
        # HTTP independently proves remote readability despite cached local layers.
        checks = self.state / 'registry-checks'
        checks.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='anonymous-', dir=checks) as directory:
            write_json(Path(directory) / 'config.json', {'auths': {'ghcr.io': {}}, 'credsStore': '', 'credHelpers': {}})
            return self.command(['docker', '--config', directory, 'pull', '--platform', platform,
                                 image.split(':', 1)[0] + '@' + digest])

    def publish(self, record):
        current = next((r for r in self.records() if (r['id'], r['version']) == (record['id'], record['version'])), record)
        current = {**current, 'reuse': record.get('reuse', False),
                   'checks': record.get('checks', current.get('checks', 'unverified'))}
        target = self.remote_tag(current['id'], current['version'])
        previous_digest = current.get('digest') if current.get('image') == target else None
        try:
            remote = self.registry.resolve(target, authenticated=True)
            if remote is not None:
                if previous_digest is None:
                    inspection = json.loads(self.command(['docker', 'image', 'inspect', current['tag']])['stdout'])[0]
                    owned = {v.split('@', 1)[1] for v in inspection.get('RepoDigests', []) if v.startswith(target.split(':')[0] + '@')}
                    if remote not in owned:
                        raise RegistryError('Existing version tag is not the verified local image; refusing overwrite')
                elif remote != previous_digest:
                    raise RegistryError('Published version tag changed; refusing overwrite')
            else:
                if previous_digest:
                    raise RegistryError('Published version tag disappeared; explicit recovery required')
                self.command(['docker', 'tag', current.get('content_id') or current['tag'], target])
                self.command(['docker', 'push', target])
                inspection = json.loads(self.command(['docker', 'image', 'inspect', target])['stdout'])[0]
                expected = next((v.split('@', 1)[1] for v in inspection.get('RepoDigests', []) if v.startswith(target.split(':')[0] + '@')), None)
                remote = self.registry.resolve(target, authenticated=True)
                if not expected or remote != expected:
                    raise RegistryError('Published tag does not match the pushed image digest')
            current = self.persist({**current, 'state': 'published', 'image': target, 'digest': remote,
                                    'anonymous_access': {'status': 'unverified'}})
            proof = self.registry.public(target, remote, current['platform'])
            pulled = self.anonymous_pull(target, remote, current['platform'])
            return self.persist({**current, 'anonymous_access': proof, 'anonymous_pull': pulled})
        except (RegistryError, OperationError) as exc:
            current = self.persist({**current, 'anonymous_access': {'status': 'unavailable', 'reason': str(exc), 'checked_at': now()}})
            raise PublicationPending('Publication is not qualified: ' + str(exc) +
                                     '. Resolve the recorded upload/access/transport failure, then resume.', current) from exc
