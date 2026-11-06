"""Immutable tool-only build contexts, concrete probes and digest-based publication."""
import json
import re
import shutil
import tempfile
import uuid
import subprocess
from .contracts import CONTRACT_VERSION, validate, runtime, tool_name, tool_version
from pathlib import Path

from creation_pipeline.records import digest, has_link, lease, read_json, safe_relative, write_json
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.runtime.runner import process


def fingerprint(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


class OperationError(ValueError):
    def __init__(self, message, observation=None):
        super().__init__(message)
        self.observation = observation


def run_checked(command, timeout, run=process):
    try:
        result = run(command, timeout)
    except subprocess.TimeoutExpired as exc:
        raise OperationError('Operation timed out', {'command': command[:3], 'timeout': timeout}) from exc
    if result['exit_code'] != 0:
        raise OperationError('Operation failed: ' + ' '.join(command[:3]), result)
    return result


def inventory(root):
    root = Path(root)
    if has_link(root):
        raise ValueError('Linked environment library')
    with lease(root, 'catalog'):
        path = root / 'catalog.json'
        values = read_json(path) if path.exists() else []
        valid = []
        for value in values:
            directory = safe_relative(root, value['path'])
            if manifest(directory / 'context') != value['files']:
                raise ValueError('Environment build materials changed: ' + value['id'])
            valid.append(value)
        return valid


def compatible(record, plan):
    if record.get('contract_version') != CONTRACT_VERSION or plan.get('contract_version') != CONTRACT_VERSION:
        return False
    if record['platform'] != plan['platform'] or record['conditions'] != plan['conditions']:
        return False
    actual = {(x['kind'], tool_name(x['name'])): tool_version(x['version']) for x in record['tools']}
    if any(actual.get((x['kind'], tool_name(x['name']))) != tool_version(x['version']) for x in plan['tools']):
        return False
    resources = {(x['name'], x['version'], x['url'], x['included_in_image']) for x in record['resources']}
    return all((x['name'], x['version'], x['url'], x['included_in_image']) in resources for x in plan['resources'])


class EnvironmentLibrary:
    def __init__(self, config, state, run=process):
        self.settings = config['environments']
        self.root, self.state = Path(self.settings['root']), Path(state)
        self.run, self.timeout = run, self.settings['operation_timeout']

    def command(self, args):
        return run_checked(args, self.timeout, self.run)

    def records(self):
        published = inventory(self.root)
        path = self.state / 'local-environments.json'
        with lease(self.state, 'local-environments'):
            local = read_json(path) if path.exists() else []
        known = {(r['id'], r['version']) for r in published}
        return published + [r for r in local if (r['id'], r['version']) not in known
                            and manifest(safe_relative(self.root, r['path']) / 'context') == r['files']]

    def ensure(self, plan, work):
        validate(plan)
        records = self.records()
        suitable = sorted((r for r in records if compatible(r, plan)), key=lambda r: (len(r['tools']), r['id'], r['version']))
        if suitable:
            record = suitable[0]
            if record.get('image'):
                self.command(['docker', 'pull', '--platform', plan['platform'], record['image']])
            # Probe this exact image for current requirements even when library observations exist.
            self.probe(record.get('image') or record['tag'], plan, work)
            return {**record, 'reuse': True}
        if plan['selection'] == 'reuse':
            raise ValueError('Selected existing environment does not satisfy requirements')
        base = plan['base_image']
        if plan['selection'] == 'extend':
            parents = [r for r in records if r['id'] == plan['environment_id']]
            if plan.get('environment_version'):
                parents = [r for r in parents if r['version'] == plan['environment_version']]
            if not parents:
                raise ValueError('Extension parent not found')
            if len(parents) != 1:
                raise ValueError('Choose an explicit environment_version for extension')
            parent = parents[-1]
            if not compatible({**parent, 'platform': plan['platform'], 'tools': plan['tools'], 'resources': plan['resources'],
                               'conditions': plan['conditions']}, parent):
                raise ValueError('Extension must preserve the original tool/resource contract')
            if not parent.get('image'):
                raise ValueError('Unpublished parent: supply a new complete build context with selection=new, preserving required tools')
            base = parent['image']
        if not base or any(c.isspace() for c in base):
            raise ValueError('Environment needs a concrete base image')
        self.command(['docker', 'pull', '--platform', plan['platform'], base])
        inspected = json.loads(self.command(['docker', 'image', 'inspect', base])['stdout'])[0]
        if inspected.get('Os', 'linux') + '/' + inspected.get('Architecture', plan['platform'].split('/')[1]) != plan['platform']:
            raise ValueError('Observed base platform differs from requested platform')
        pinned = base if '@sha256:' in base else next((r for r in inspected.get('RepoDigests', []) if '@sha256:' in r), None)
        if not pinned:
            raise ValueError('Base image has no repository digest')
        context = Path(work) / ('context-' + uuid.uuid4().hex)
        context.mkdir(parents=True)
        for f in plan['files']:
            target = safe_relative(context, f['path'])
            if target.exists():
                raise ValueError('Duplicate build context path')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f['content'], encoding='utf-8')
        recipe = context / 'Dockerfile'
        if not recipe.exists():
            raise ValueError('Environment plan must include Dockerfile')
        text = recipe.read_text(encoding='utf-8')
        lines = text.splitlines()
        starts = [i for i, line in enumerate(lines) if re.match(r'^\s*FROM\s', line, re.I)]
        if len(starts) != 1:
            raise ValueError('Tool environment requires one explicit base stage')
        lines[starts[0]] = 'FROM ' + pinned
        # Generic environments accept caller argv, without a task-specific inherited entrypoint.
        lines.append('ENTRYPOINT []')
        recipe.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        if not (context / '.dockerignore').exists():
            (context / '.dockerignore').write_text('.git\n.pipeline\n', encoding='utf-8')
        files = manifest(context)
        identity = fingerprint({'files': files, 'platform': plan['platform'], 'base': pinned,
                                'tools': [{k: t[k] for k in ('name', 'kind', 'version')} for t in plan['tools']],
                                'resources': [{k: r[k] for k in ('name', 'url', 'version', 'included_in_image')} for r in plan['resources']],
                                'conditions': plan['conditions']})
        eid = plan['environment_id'] or ('env-' + identity[:12])
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', eid):
            raise ValueError('Invalid environment ID')
        tag = 'chem-env:' + identity
        self.command(['docker', 'build', '--platform', plan['platform'], '--label',
                      'org.opencontainers.image.source=' + self.settings['source_url'], '-t', tag, str(context)])
        self.probe(tag, plan, work)
        version = identity[:16]
        relative = eid + '/' + version
        with lease(self.root, 'catalog'):
            destination = safe_relative(self.root, relative)
            if destination.exists():
                if manifest(destination / 'context') != files:
                    raise ValueError('Immutable environment version collision')
            else:
                destination.mkdir(parents=True)
                shutil.copytree(context, destination / 'context')
            record = {'id': eid, 'version': version, 'path': relative, 'files': files,
                      'contract_version': CONTRACT_VERSION, 'platform': plan['platform'], 'base_image': pinned,
                      'tools': plan['tools'], 'resources': plan['resources'],
                      'conditions': plan['conditions'],
                      'tag': tag, 'image': None, 'reuse': False, 'checks': 'passed'}
            write_json(destination / 'environment.json', record)
        with lease(self.state, 'local-environments'):
            path = self.state / 'local-environments.json'
            local = read_json(path) if path.exists() else []
            local = [r for r in local if (r['id'], r['version']) != (record['id'], record['version'])]
            write_json(path, local + [record])
        return record

    def probe(self, image, plan, work):
        observations = []
        resources = set()
        for tool in plan['tools']:
            command = ['docker', 'run', '--rm', '--platform', plan['platform'], image, *tool['probe']]
            observation = self.command(command)
            try:
                fact = json.loads(observation['stdout'].strip())
            except (ValueError, TypeError) as exc:
                raise OperationError('Tool probe must report JSON with its observed version', observation) from exc
            if fact.get('version') != tool['version']:
                raise OperationError('Observed tool version differs from environment contract: ' + tool['name'], observation)
            resources.update(k for k, v in fact.get('resources', {}).items() if v is True)
            observations.append({'tool': tool['name'], 'observation': observation})
        required = {r['name'] for r in plan['resources'] if r['included_in_image']}
        if not required.issubset(resources):
            raise OperationError('Basic probes did not verify bundled resources: ' + ', '.join(sorted(required - resources)))
        write_json(Path(work) / ('environment-check-' + uuid.uuid4().hex + '.json'), observations)

    def publish(self, record):
        if record.get('image'):
            return record
        prefix = self.settings['image_prefix']
        if not prefix or not self.settings['source_url'].startswith('https://github.com/'):
            raise ValueError('Configure environments.image_prefix and source_url before publication')
        repository = prefix.rstrip('/') + '/' + record['id']
        tag = repository + ':' + record['version']
        self.command(['docker', 'tag', record['tag'], tag])
        self.command(['docker', 'push', tag])
        inspection = json.loads(self.command(['docker', 'image', 'inspect', tag])['stdout'])[0]
        image = next((r for r in inspection.get('RepoDigests', []) if r.startswith(repository + '@sha256:')), None)
        if not image:
            raise ValueError('Published image has no observed repository digest')
        with tempfile.TemporaryDirectory() as anonymous:
            # An authenticated local pull alone does not prove users can download the image.
            self.command(['docker', '--config', anonymous, 'manifest', 'inspect', image])
        record = {**record, 'image': image}
        with lease(self.root, 'catalog'):
            path = self.root / 'catalog.json'
            catalog = read_json(path) if path.exists() else []
            existing = [r for r in catalog if (r['id'], r['version']) == (record['id'], record['version'])]
            if existing and existing[0]['image'] != image:
                raise ValueError('Published environment version changed')
            catalog = [r for r in catalog if (r['id'], r['version']) != (record['id'], record['version'])]
            catalog.append(record)
            write_json(safe_relative(self.root, record['path']) / 'environment.json', record)
            write_json(path, catalog)
        return record
