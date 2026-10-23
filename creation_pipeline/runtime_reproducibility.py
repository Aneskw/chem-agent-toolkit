"""Separate requested requirements, observed inventories and rebuild inputs."""
import json
import re
import time
import subprocess
from runtime_common import read, sha
import runtime_package as runner


def resolve_base(requested, platform, timeout):
    command = ['docker', 'buildx', 'imagetools', 'inspect', requested, '--format', '{{json .Manifest}}']
    result = runner.process(command, timeout)
    if result['exit_code']:
        raise OSError('Base digest resolution failed: ' + result['stderr'][-2000:])
    manifest = json.loads(result['stdout'])
    digest = manifest.get('digest', '')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise ValueError('Registry did not return a valid immutable manifest digest')
    if manifest.get('manifests'):
        matches = [m for m in manifest['manifests'] if '/'.join(m.get('platform', {}).get(k, '') for k in ('os', 'architecture')) == platform]
        if len(matches) != 1:
            raise ValueError('Base manifest platform missing or ambiguous: ' + platform)
        digest = matches[0]['digest']
    if '@' in requested and requested.split('@', 1)[1] not in {digest, manifest['digest']}:
        raise ValueError('Registry digest differs from requested immutable reference')
    return {'requested': requested, 'platform': platform, 'digest': digest,
            'reference': requested.split('@')[0] + '@' + digest,
            'registry_receipt': result, 'scope': 'Immutable base manifest; dependency steps may remain unlocked'}


def observe(tool, info, tool_root, deadline):
    plan = read(tool_root / 'environment_plan.json')
    lock = tool_root / 'context/.skillnet/base-lock.json'
    result = {'requested_dependencies': plan['dependencies'], 'image_id': info['Id'],
              'platform': tool['platform'], 'base_lock': read(lock) if lock.exists() else None,
              'inventories': {}, 'complete_rebuild_lock': False,
              'limitations': ['Inventories are observations, not complete dependency locks.',
                  'No retained wheel/source/package archive closure; remote repositories may change.',
                  'Container CPU/memory/PID limits do not constrain Docker build resources.'],
              'source_inputs': {n: sha(tool_root / 'context' / n) for n in plan['source_files']},
              'source_install_steps': plan['steps']}
    probes = {'pip': 'python -m pip freeze --all',
              'conda_explicit': 'conda list --explicit --md5',
              'system': "if command -v dpkg-query >/dev/null; then dpkg-query -W; elif command -v apk >/dev/null; then apk info -v; elif command -v rpm >/dev/null; then rpm -qa; else exit 127; fi"}
    for name, command in probes.items():
        seconds = int(deadline - time.monotonic())
        if seconds <= 0:
            result['inventories'][name] = {'status': 'budget_exhausted'}
            continue
        try:
            observed = runner.run(tool, info['Id'], ['-c', command], entrypoint='/bin/sh', timeout=min(seconds, 30))
        except (OSError,subprocess.TimeoutExpired) as exc:
            result['inventories'][name]={'status':'unavailable','error':str(exc)}
            continue
        result['inventories'][name] = dict(observed, classification='rebuild_urls_with_checksums' if name == 'conda_explicit' and observed['exit_code'] == 0 else 'observed_inventory')
    return result
