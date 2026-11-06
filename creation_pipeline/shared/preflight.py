"""One startup protocol shared by readiness and execution, without building images."""
import copy
import json
import subprocess
import time
import uuid
import os
from pathlib import Path
from creation_pipeline.agent.command import codex_command
from creation_pipeline.records import read_json, write_json, file_digest
from creation_pipeline.runtime.runner import process
from .environment import fingerprint


def observe(config, mode='build', run=process):
    checks = []
    try:
        cli = codex_command()
        version = run(cli + ['--version'], 15)
        if version['exit_code']:
            raise ValueError('Codex CLI version command failed')
        for args, flags in [(['exec', '--help'], ['--add-dir', '--output-schema']),
                            (['exec', 'resume', '--help'], ['--output-schema', '--config'])]:
            help_result = run(cli + args, 15)
            if help_result['exit_code'] or any(flag not in help_result['stdout'] for flag in flags):
                raise ValueError('Codex CLI lacks required new/resume options')
        checks.append({'object': 'cli', 'status': 'passed', 'command': cli, 'version': version['stdout'].strip()})
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        checks.append({'object': 'cli', 'status': 'blocked', 'reason': str(exc)})
    if mode == 'build':
        if config['environments'].get('publish', True) and (
                not config['environments']['image_prefix'] or not config['environments']['source_url'].startswith('https://github.com/')):
            checks.append({'object': 'publication', 'status': 'blocked', 'reason': 'Configure image_prefix and GitHub source_url'})
        try:
            result = run(['docker', 'info', '--format', '{{json .}}'], 15)
            if result['exit_code']:
                raise ValueError('Docker server is unreachable: ' + result['stderr'])
            info = json.loads(result['stdout'])
            if info.get('OSType') != 'linux':
                raise ValueError('Linux Docker engine is required')
            checks.append({'object': 'docker', 'status': 'passed',
                           'identity': {k: info.get(k) for k in ('ID', 'ServerVersion', 'OSType', 'Architecture')}})
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            checks.append({'object': 'docker', 'status': 'blocked', 'reason': str(exc)})
    return checks


def startup(config, state, work, notify, mode='build'):
    """Observe cheap prerequisites each time; cache actual model/tool smoke success for one hour."""
    from creation_pipeline.agent.backend import NativeSession
    from creation_pipeline.models import ModelCallError
    from creation_pipeline.resources.intake import Sources
    from creation_pipeline.resources.acquisition import Acquisition
    from .schemas import obj, B
    checks = observe(config, mode)
    blocked = [c for c in checks if c['status'] == 'blocked']
    if blocked:
        raise ValueError('Startup prerequisites failed: ' + json.dumps(blocked))
    cache = Path(state) / 'cache'
    cache.mkdir(parents=True, exist_ok=True)
    code = {p: file_digest(Path(__file__).parents[1] / p) for p in ('shared/preflight.py', 'agent/backend.py', 'agent/tools.py')}
    user_config = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'config.toml'
    user_config_digest = file_digest(user_config) if user_config.is_file() else None
    key = fingerprint({'checks': checks, 'model': config['model'], 'network': config['network'],
                       'http_only': config.get('http_only'), 'work': str(Path(work).resolve()),
                       'cache': str(cache.resolve()), 'code': code, 'user_config_digest': user_config_digest})
    receipt_path = Path(work) / 'preflight-success.json'
    previous = read_json(receipt_path) if receipt_path.exists() else {}
    if previous.get('key') == key and 0 <= time.time() - previous.get('time', 0) < 3600:
        notify('Startup prerequisites passed; reusing recent model/tool preflight')
        return []
    receipt_path.unlink(missing_ok=True)
    cfg = copy.deepcopy(config)
    cfg['sources'] = []
    empty = Sources.__new__(Sources)
    empty.config, empty.limits = cfg, cfg['limits']
    empty.entries, empty.evidence, empty.errors = {}, [], []
    empty.cache, empty.total_bytes = cache, 0
    empty.acquisition = Acquisition(cfg, cache)
    session = NativeSession(cfg, empty, dict(cfg['limits'], model_calls=None, model_timeout=90, total_seconds=180), Path(work) / 'preflight')
    session.notify = notify
    token = uuid.uuid4().hex
    local = session.work / ('probe-' + token + '.txt')
    cached = cache / ('preflight-' + token + '.txt')
    resumed = session.work / ('resume-' + token + '.txt')
    # Prove shell permissions and the native helper path, not merely model connectivity.
    instructions = ('Startup permission check only. Do not acquire sources or install anything. '
                    'Use shell to write the supplied token to local_probe. Use the resource workspace helper write '
                    'to write the same token to cache_probe (package is its parent, path is its filename; encode as base64). Read both back, and invoke helper inventory for this run. '
                    'The cache_probe path is explicitly authorized for this startup check. Return ready=true only after success.')
    context = {'plan': {'name': 'startup'}, '_phase': 'preflight', 'token': token,
               'local_probe': str(local), 'cache_probe': str(cached), 'resume_probe': str(resumed), 'run': str(session.work)}
    try:
        result = session.stage(instructions, context, schema=obj({'ready': B}))
        if not result.get('ready') or any(not p.is_file() or p.read_text(encoding='utf-8').strip() != token for p in (local, cached)):
            raise ModelCallError('Model/tool permission preflight did not complete actual file operations')
        # A second turn exercises resume flags and cache authorization before costly resource work.
        result = session.stage('Resume startup check: read both existing probe files through shell, write token to resume_probe only after matching both, and return ready=true. Do not acquire resources.',
                               context, schema=obj({'ready': B}))
        if not result.get('ready') or not resumed.is_file() or resumed.read_text(encoding='utf-8').strip() != token:
            raise ModelCallError('CLI resume preflight failed')
        write_json(receipt_path, {'key': key, 'time': time.time(), 'checks': checks})
    finally:
        local.unlink(missing_ok=True)
        cached.unlink(missing_ok=True)
        resumed.unlink(missing_ok=True)
    return session.receipts
