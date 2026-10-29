"""Exact local dependency-stage reuse, independent of skill acceptance."""
import json
import os
from pathlib import Path
import re
import shutil
import time

from creation_pipeline.contracts import fingerprint
from creation_pipeline.records import file_digest, has_link, read_json, safe_relative, write_json

CACHE_ROOT_ENV = 'CHEM_AGENT_SHARED_ENVIRONMENTS'


def registry_root():
    """Host cache location, never part of a frozen recipe or model context."""
    from creation_pipeline.paths import ROOT
    configured = os.environ.get(CACHE_ROOT_ENV)
    if not configured:
        return ROOT / '.pipeline/shared-environments'
    path = Path(configured).expanduser()
    if not path.is_absolute():
        raise ValueError(CACHE_ROOT_ENV + ' must select an absolute shared environment directory')
    # Preserve links for resolve/inspection to reject; resolving them here would
    # erase the evidence that the operator-provided root is linked.
    return path


class SharedEnvironmentError(ValueError):
    def __init__(self, message, logs, status='runtime_blocked'):
        super().__init__(message)
        self.logs = logs
        if status not in {'runtime_blocked', 'build_failed'}:
            raise ValueError('Invalid shared environment failure state')
        self.status = status


def inheritance_matches(shared, image):
    """Image layers alone do not identify inherited ENV/WORKDIR configuration."""
    if shared['status'] not in {'hit', 'built'}:
        return True
    layers = shared.get('layers', [])
    config = image.get('Config', {})
    return bool(layers and image.get('RootFS', {}).get('Layers', [])[:len(layers)] == layers
                and config.get('Env') == shared.get('inherited_config', {}).get('Env')
                and config.get('WorkingDir') == shared.get('inherited_config', {}).get('WorkingDir'))


def describe(context, plan, pin, prefix_text):
    """Freeze only explicitly declared dependency inputs, never candidate tests."""
    layout = plan['build_layout']
    if not pin or not layout['prefix_steps']:
        return None
    files = []
    for name in layout['dependency_files']:
        path = safe_relative(context, name)
        if not path.is_file() or has_link(path):
            raise ValueError('Unsafe shared dependency input: ' + name)
        files.append({'path': name, 'sha256': file_digest(path), 'mode': path.stat().st_mode & 0o777})
    return {'abi': 1, 'base': pin['repo_digest'], 'platform': plan['platform'],
            'prefix_text': prefix_text, 'files': files}


def resolve(materials, root, host, process, deadline, attempt):
    """Return attempt-local thin context plus observation, or original context.

    A lock collision waits within the existing build deadline. Only its owner
    releases a lock; interrupted/crashed locks are never stolen by age.
    """
    materials, attempt = Path(materials), Path(attempt)
    descriptor = materials / 'shared-environment.json'
    if not descriptor.is_file():
        return materials / 'context', {'status': 'not_applicable'}, []
    root = Path(root) if root is not None else registry_root()
    recipe = read_json(descriptor)
    key = fingerprint(recipe)
    if not host.get('engine_id'):
        raise ValueError('Shared environment needs observed daemon identity')
    if not re.fullmatch(r'python@sha256:[a-f0-9]{64}|[^\s]+@sha256:[a-f0-9]{64}', recipe['base']):
        raise ValueError('Shared environment requires pinned base digest')
    context = materials / 'context'
    original = (context / 'Dockerfile').read_text(encoding='utf-8')
    if not original.startswith(recipe['prefix_text']):
        raise ValueError('Shared recipe differs from frozen Dockerfile')
    for item in recipe['files']:
        path = safe_relative(context, item['path'])
        if has_link(path) or file_digest(path) != item['sha256'] or path.stat().st_mode & 0o777 != item['mode']:
            raise ValueError('Shared dependency input drift')
    if has_link(root):
        raise ValueError('Linked shared environment root')
    root.mkdir(parents=True, exist_ok=True)
    lock = root / (key + '.lock')
    waited_for_builder = False
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError('Shared environment build deadline reached while acquiring lock: '
                             + str(lock))
        try:
            handle = lock.open('x', encoding='utf-8')
            break
        except FileExistsError:
            waited_for_builder = True
            time.sleep(min(.1, remaining))
    logs = []
    layers = []
    inherited_config = {}
    def run(args):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError('Shared environment build deadline reached')
        result = process(args, max(.1, remaining))
        logs.append(result)
        return result
    def inspect(image):
        nonlocal layers, inherited_config
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', str(image)):
            return False
        p = run(['docker', 'image', 'inspect', image])
        try:
            d = json.loads(p['stdout'])[0]
            layers = d.get('RootFS', {}).get('Layers', [])
            inherited_config = {k: d.get('Config', {}).get(k) for k in ('Env', 'WorkingDir')}
            return (p['exit_code'] == 0 and d['Id'] == image and d['Os'] == 'linux'
                    and d['Architecture'] == 'amd64' and d['Config']['Labels'].get('chem.shared.recipe') == key)
        except (ValueError, KeyError, IndexError, TypeError):
            return False
    try:
        with handle:
            handle.write(str(os.getpid()))
        entry_path = root / (key + '.json')
        if has_link(entry_path) or has_link(entry_path.with_suffix('.json.tmp')):
            raise ValueError('Linked shared registry entry')
        image = None
        try:
            if has_link(entry_path):
                raise ValueError('Linked shared registry entry')
            entry = read_json(entry_path)
            if (entry.get('recipe') == recipe and entry.get('daemon_id') == host['engine_id']
                    and inspect(entry.get('image_id'))):
                image = entry['image_id']
        except (OSError, ValueError, KeyError, TypeError):
            pass  # A corrupt/missing observation is a miss, never a trusted hit.
        hit = image is not None
        if not hit:
            build_context = attempt / 'shared-environment-build'
            build_context.mkdir()
            for item in recipe['files']:
                target = safe_relative(build_context, item['path'])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(safe_relative(context, item['path']), target)
            (build_context / 'Dockerfile').write_text(recipe['prefix_text'], encoding='utf-8')
            iid = attempt / 'shared-environment.id'
            p = run(['docker', 'build', '--platform', recipe['platform'], '--iidfile', str(iid),
                     '--label', 'chem.shared.recipe=' + key, str(build_context)])
            if p['exit_code'] != 0:
                raise SharedEnvironmentError('Shared dependency environment build failed', logs, 'build_failed')
            image = iid.read_text(encoding='utf-8').strip()
            if not inspect(image):
                raise SharedEnvironmentError('Shared environment identity verification failed', logs)
            write_json(entry_path, {'recipe': recipe, 'daemon_id': host['engine_id'], 'image_id': image,
                                    'complete_rebuild_lock': False})
        thin = attempt / 'tool-context'
        # BuildKit treats FROM sha256:<local config ID> as a registry name.
        # The tag is transport only; verify it resolves to the observed ID.
        reference = 'chem-shared-env:' + image.split(':', 1)[1]
        tagged = run(['docker', 'tag', image, reference])
        bound = run(['docker', 'image', 'inspect', reference, '--format', '{{.Id}}'])
        if tagged['exit_code'] != 0 or bound['exit_code'] != 0 or bound['stdout'].strip() != image:
            raise SharedEnvironmentError('Shared environment transport tag differs from immutable image', logs)
        shutil.copytree(context, thin)
        (thin / 'Dockerfile').write_text('FROM ' + reference + '\n' + original[len(recipe['prefix_text']):], encoding='utf-8')
        return thin, {'status': 'hit' if hit else 'built', 'recipe_key': key, 'registry': str(root),
                      'waited_for_builder': waited_for_builder,
                      'image_id': image, 'reference': reference, 'layers': layers,
                      'inherited_config': inherited_config,
                      'daemon_id': host['engine_id'], 'complete_rebuild_lock': False}, logs
    finally:
        lock.unlink()
