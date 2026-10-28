"""Isolated, tool-free structured model calls shared by creation and evaluation.

Two backends serve the same ``call`` contract and return the same ``(answer,
receipt)`` pair:

* ``codex_cli`` (default, unchanged) - the isolated ``codex exec`` child process;
* ``deepseek_api`` (opt-in, see ``deepseek_api``) - the DeepSeek chat completions
  API. It is selected explicitly by the caller and is never used as a fallback.

The backend is explicit in every call. An unknown name, a missing credential or a
failing request raises a classified error; nothing silently retries through the
other backend or another model.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import tomllib
from . import process_stats
from .network import model_environment
from creation_pipeline.agent.command import codex_command, model_args
from creation_pipeline.records import redact, sanitized, is_recoverable_notice
from creation_pipeline.validation.runtime import terminate_tree

# A silent child is not evidence of a slow answer. The CLI's own stream idle
# timeout only watches its socket, and in responses-websocket mode any inbound
# text frame (including unusable ones) restarts that per-message timer, so a
# stalled sampling response can wait indefinitely. Bound the wait on the event
# channel we actually consume: no stdout progress at all for this long is a
# stall, not a slow generation.
PROGRESS_TIMEOUT_SECONDS = 240


class ModelExecutionError(ValueError):
    """The model process failed, rather than returning an invalid plan."""

    code = 'model_unavailable'
    kind = 'model_transport'


class ModelOutputInvalid(ValueError):
    """The process answered, but with an unusable contract (tools, non-JSON)."""

    code = 'model_output_invalid'
    kind = 'model_transport'


class ModelConfigError(ValueError):
    """The child configuration cannot be isolated safely; no request was sent."""

    code = 'model_config_invalid'
    kind = 'model_transport'


BACKENDS = ('codex_cli', 'deepseek_api')


def isolated_options(transport="default", reasoning=None, tier=None):
    """Retain model/provider/auth configuration, disable unrelated tool discovery.

    Unlike ignoring the user config, this preserves configured transport and
    reasoning settings. Only configured MCP server names are inspected, never
    their environment or credentials. The answer is still rejected on tool use.
    """
    path = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'config.toml'
    try:
        settings = tomllib.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    except (OSError, ValueError) as exc:
        raise ModelConfigError('Model configuration cannot be read safely: ' + redact(str(exc))) from exc
    if not isinstance(settings.get('mcp_servers', {}), dict):
        raise ModelConfigError('mcp_servers must be a table; isolation cannot be guaranteed')
    args = model_args(transport, reasoning, tier) + ['--enable', 'skip_host_skill_discovery', '-c', 'web_search="disabled"',
            '-c', 'approval_policy="never"',
            '-c', 'notify=[]',
            '-c', 'suppress_unstable_features_warning=true']
    if os.name == 'nt':
        # The Windows transport ignores the system proxy unless this experimental
        # feature is enabled, so a machine that reaches the provider only through
        # a local proxy fails every request with a 15 s connect timeout.
        args += ['--enable', 'respect_system_proxy']
    for feature in ('apps', 'plugins', 'hooks', 'multi_agent', 'shell_tool'):
        args += ['--disable', feature]
    for name in settings.get('mcp_servers', {}):
        # Codex dotted overrides are not a TOML parser for quoted key segments.
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            raise ModelConfigError('Cannot safely isolate MCP server key; use a simple alphanumeric/underscore/hyphen name')
        args += ['-c', 'mcp_servers.' + name + '.enabled=false']
    observed = {key: settings.get(key) for key in
                ('model', 'model_reasoning_effort', 'service_tier', 'model_provider')}
    return args, observed


def run(command, prompt, root, timeout, audit_dir, metadata, *, stderr_filter=None, progress_timeout=None,
        progress_watch="terminate"):
    """Persist lifecycle facts; incomplete I/O never yields a usable answer.

    ``progress_timeout`` bounds the silence on the stdout event channel. It is
    clamped to ``timeout`` and never extends the overall budget; ``None`` keeps
    the historical "wait until the process exits" behaviour.
    """
    from .runner import WindowsProcessJob
    started = time.monotonic()
    destination = Path(audit_dir) if audit_dir else None
    if destination:
        destination.mkdir(parents=True, exist_ok=True)
    progress_limit = None if progress_timeout is None else max(0.05, float(min(progress_timeout, timeout)))
    probe_interval = 2.0 if progress_limit is None else min(2.0, max(0.25, progress_limit / 4.0))
    observation = dict(metadata, command=command, cwd=str(root), timeout_seconds=timeout,
                       progress_timeout_seconds=progress_limit,
                       started_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    def save(name, value):
        if destination:
            (destination / name).write_text(json.dumps(sanitized(value), ensure_ascii=False, indent=2), encoding='utf-8')
    save('request.json', observation)
    job = None
    proc = None
    try:
        job = WindowsProcessJob() if os.name == 'nt' else None
        flags = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | 0x4} if job else {'start_new_session': True}
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding='utf-8', errors='replace', cwd=root,
                                env=model_environment(), **flags)
        if job:
            job.attach_and_resume(proc)
    except BaseException as exc:
        if job:
            job.close()
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                stream.close()
        observation.update(status='start_failed', error=type(exc).__name__,
                           elapsed_seconds=round(time.monotonic()-started, 3))
        save('process.json', observation)
        if isinstance(exc, Exception):
            raise ModelExecutionError('Model process could not start: ' + redact(str(exc))) from exc
        raise
    observation.update(pid=proc.pid, status='running')
    captured = {'stdout': [], 'stderr': []}
    events, failures = [], []
    failed = threading.Event()
    # Progress is claimed by stdout lifecycle events, or by real inbound traffic:
    # a long generation is silent on stdout while deltas stream over the socket,
    # so byte growth must count as activity. Stderr is diagnostics, never progress.
    INBOUND_ACTIVITY_BYTES = 4096
    # Five separate timelines. Only documented lifecycle events count as
    # generation progress; CLI activity and retry notices are recorded but
    # never treated as progress, and process I/O is evidence only.
    progress = {'last_stdout_seconds': None, 'last_activity_seconds': None,
                'last_notice_seconds': None, 'generation_seconds': None,
                'terminal_seconds': None, 'process_io_growth_seen': False}
    def failure(channel, exc):
        failures.append({'channel': channel, 'error': type(exc).__name__})
        failed.set()
    def pump(channel):
        stream = getattr(proc, channel)
        handle = None
        try:
            handle = (destination / (channel + '.txt')).open('w', encoding='utf-8') if destination else None
            for line in stream:
                now = round(time.monotonic()-started, 3)
                observation.setdefault(channel + '_first_line_seconds', now)
                observation[channel + '_last_line_seconds'] = now
                observation[channel + '_lines'] = observation.get(channel + '_lines', 0) + 1
                if channel == 'stdout' or channel == 'stderr':
                    progress['last_activity_seconds'] = now
                if channel == 'stdout':
                    progress['last_stdout_seconds'] = now
                # Opt-in diagnostics must remove sensitive fields before capture or persistence.
                if channel == 'stderr' and stderr_filter is not None:
                    line = stderr_filter(line)
                captured[channel].append(line)
                if handle:
                    handle.write(redact(line)); handle.flush()
                if channel == 'stdout':
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    item = event.get('item')
                    if event.get('type') in {'turn.completed', 'turn.failed', 'error'}:
                        observation.setdefault('first_terminal_event_seconds', now)
                        observation['last_terminal_event_type'] = event['type']
                    message = str(event.get('message', ''))
                    if event.get('type') == 'error' and is_recoverable_notice(message):
                        progress['last_notice_seconds'] = now
                        observation['reconnect_notices'] = observation.get('reconnect_notices', 0) + 1
                    elif event.get('type') in {'turn.completed', 'turn.failed', 'error'}:
                        progress['terminal_seconds'] = now
                    else:
                        progress['generation_seconds'] = now
                    events.append({'elapsed_seconds': round(time.monotonic()-started, 3),
                                   'type': event.get('type'),
                                   'item_type': item.get('type') if isinstance(item, dict) else None})
                    save('events.json', events)
        except Exception as exc:
            failure(channel, exc)
        finally:
            try:
                stream.close()
                if handle: handle.close()
            except Exception as exc:
                failure(channel, exc)
    def send():
        try:
            proc.stdin.write(prompt); proc.stdin.flush()
            observation['stdin_sent_seconds'] = round(time.monotonic()-started, 3)
        except Exception as exc:
            failure('stdin', exc)
        finally:
            try:
                proc.stdin.close()
                observation['stdin_closed_seconds'] = round(time.monotonic()-started, 3)
            except Exception as exc:
                failure('stdin', exc)
    threads = [threading.Thread(target=pump, args=(channel,), daemon=True) for channel in captured]
    threads.append(threading.Thread(target=send, daemon=True))
    active_threads = []
    status = 'cancelled'
    counters = None
    probed = [0.0, None]
    try:
        save('process.json', observation)
        try:
            counters = process_stats.Sampler(proc.pid).start() if proc.pid else None
            if counters is not None:
                probed[1] = counters.latest().get('read_bytes')
        except Exception:
            counters = None
        for thread in threads:
            thread.start(); active_threads.append(thread)
        while proc.poll() is None:
            if failed.is_set():
                status = 'io_failed'
                break
            elapsed = time.monotonic()-started
            remaining = timeout - elapsed
            if remaining <= 0:
                status = 'timed_out'
                observation['timeout_location'] = 'waiting_for_process_completion'
                break
            if progress_limit is not None:
                # Process I/O is evidence about the child, never about the
                # answer: it includes file I/O and cannot prove that the peer is
                # still streaming. It is recorded, not used as progress.
                if counters is not None and (elapsed - probed[0]) >= probe_interval:
                    probed[0] = elapsed
                    read_now = counters.latest().get('read_bytes')
                    if read_now is not None:
                        if probed[1] is not None and read_now - probed[1] >= INBOUND_ACTIVITY_BYTES:
                            progress['process_io_growth_seen'] = True
                        probed[1] = read_now
                last = progress['generation_seconds']
                silent = elapsed - (last if last is not None else 0.0)
                if silent >= progress_limit and progress_watch == 'observe':
                    # Observer batch: record the silence and keep waiting inside
                    # the overall budget. This signal never terminates by itself.
                    observation['progress_observed_silence_seconds'] = round(silent, 3)
                    observation['progress_limit_exceeded'] = True
                    time.sleep(0.05)
                elif silent >= progress_limit:
                    status = 'stalled'
                    observation['timeout_location'] = 'no_lifecycle_event_or_inbound_activity'
                    observation['stall_seconds'] = round(silent, 3)
                    observation['window_meaning'] = 'exceeded the local generation-progress window; the model is not thereby known to be stuck'
                    observation['last_stdout_event_seconds'] = progress['last_stdout_seconds']
                    observation['process_io_growth_seen'] = progress['process_io_growth_seen']
                    break
            try:
                proc.wait(timeout=min(0.1, remaining))
            except subprocess.TimeoutExpired:
                continue
        else:
            status = 'exited'
    finally:
        observation.update(supervision_status_before_cleanup=status,
                           returncode_before_cleanup=proc.poll(),
                           supervision_finished_seconds=round(time.monotonic()-started, 3))
        cleanup_started = time.monotonic()
        # Close the owned job/group even if the parent already exited: descendants
        # can otherwise keep inherited pipes open and survive cancellation.
        try:
            if job:
                job.close()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Never let cleanup replace the verdict: record and continue.
                    observation['cleanup_wait_expired'] = True
            else:
                terminate_tree(proc)
        except subprocess.TimeoutExpired:
            observation['cleanup_wait_expired'] = True
        finally:
            for thread in active_threads:
                thread.join(timeout=5)
            finished = all(not t.is_alive() for t in active_threads)
            if status == 'exited' and (failures or not finished):
                status = 'io_failed'
            observation.update(status=status, returncode=proc.returncode,
                               cleanup_seconds=round(time.monotonic()-cleanup_started, 3),
                               elapsed_seconds=round(time.monotonic()-started, 3),
                               stream_threads_finished=finished, io_errors=failures,
                               process_io_growth_seen=progress['process_io_growth_seen'],
                               cli_activity_seconds=progress['last_activity_seconds'],
                               last_notice_seconds=progress['last_notice_seconds'],
                               generation_progress_seconds=progress['generation_seconds'],
                               terminal_seconds=progress['terminal_seconds'])
            if counters is not None:
                try:
                    observation['process_counters'] = counters.stop()
                    observation['process_counter_timeline'] = counters.timeline()
                except Exception as exc:
                    observation['process_counters'] = {'available': False, 'error': type(exc).__name__}
            save('process.json', observation)
    if status == 'timed_out':
        save('timeout.json', observation)
        raise ModelExecutionError('Model operation timed out; process tree terminated; observations retained')
    if status == 'stalled':
        save('stall.json', observation)
        error = ModelExecutionError(
            'Model stream produced no lifecycle event for {0}s after the last one; '
            'process tree terminated; observations retained'.format(observation.get('stall_seconds')))
        # A stall is a transport fault, never an invalid plan or a slow model.
        error.code = 'model_stalled'
        raise error
    if status != 'exited':
        raise ModelExecutionError('Model transport failed: ' + status + '; observations retained')
    return subprocess.CompletedProcess(command, proc.returncode, ''.join(captured['stdout']), ''.join(captured['stderr']))


def call(prompt, schema, model, timeout=900, audit_dir=None, progress_timeout=PROGRESS_TIMEOUT_SECONDS,
         transport="default", progress_watch="terminate", reasoning=None, tier=None,
         backend="codex_cli", api_options=None):
    """Return ``(answer, receipt)`` from the explicitly selected backend.

    ``backend='codex_cli'`` keeps the historical child-process transport byte for
    byte. ``backend='deepseek_api'`` sends one bounded HTTPS request instead and
    validates the answer against ``schema`` locally. There is no fallback: an
    unknown backend is a configuration error, not a reason to try another one.
    """
    if backend not in BACKENDS:
        raise ModelConfigError('Unknown model backend ' + repr(backend) + '; supported: '
                               + ', '.join(BACKENDS) + '; no request was sent')
    if backend == 'deepseek_api':
        return _deepseek_call(prompt, schema, model, timeout, audit_dir, progress_timeout,
                              reasoning, tier, api_options)
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='chem-decision-') as directory:
        root=Path(directory)
        # Put only the answer schema in the child's working directory. Source
        # documents, skills and test oracles are never discoverable in ancestors.
        target=root/'schema.json'
        target.write_text(json.dumps(schema, ensure_ascii=False), encoding='utf-8')
        command=codex_command()+['exec','--ephemeral','--skip-git-repo-check','--sandbox','read-only']
        isolation, settings = isolated_options(transport, reasoning, tier)
        command += isolation
        if model:
            command += ['--model', model]
        command += ['--output-schema',str(target),'--json','-']
        if audit_dir:
            Path(audit_dir).mkdir(parents=True, exist_ok=True)
            (Path(audit_dir)/'schema.json').write_text(redact(target.read_text(encoding='utf-8')), encoding='utf-8')
        # Production always filters stderr before capture and persistence, so a
        # credential shape in CLI diagnostics can never reach the audit dir or a
        # recorded error message.
        proc=run(command, 'Use only the supplied text. Do not call tools or read files.\n'+prompt,
                 root, timeout, audit_dir, {'model': model, 'inherited_model_settings': settings,
                 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                 'prompt_bytes': len(prompt.encode()), 'schema_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                 'isolation_policy': 'no-tools-v1', 'transport': transport,
                 'requested_model_settings': {'reasoning_effort': reasoning, 'service_tier': tier},
                 'progress_watch': progress_watch},
                 progress_timeout=progress_timeout, progress_watch=progress_watch,
                 stderr_filter=redact)
    answer=None;usage={};tools=[];notices=[]
    completed=False; failed=False
    for line in proc.stdout.splitlines():
        try:event=json.loads(line)
        except ValueError:continue
        if not isinstance(event, dict):
            continue
        if event.get('type')=='turn.completed':
            completed=True; usage=event.get('usage',{})
        if event.get('type') == 'error' and is_recoverable_notice(event.get('message', '')):
            notices.append(str(event.get('message', ''))[:200])
        elif event.get('type') in {'turn.failed', 'error'}:
            failed=True
        if event.get('type')!='item.completed':continue
        item=event.get('item',{})
        if not isinstance(item, dict):
            failed=True
            continue
        if item.get('type')=='agent_message':
            try:answer=json.loads(item['text'])
            except ValueError:pass
        elif item.get('type')=='error':
            # The CLI reports recoverable stream notices as error items too.
            if not is_recoverable_notice(item.get('message', '')):
                tools.append('error')
        elif item.get('type')!='reasoning':tools.append(item.get('type','unknown'))
    if proc.returncode or not completed or failed or answer is None or tools:
        error=f'Model call failed: exit={proc.returncode}, completed={completed}, failed={failed}, answer={answer is not None}, tool_events={tools}; {redact(proc.stderr[-600:])}'
        if proc.returncode or not completed or failed:
            raise ModelExecutionError(error)
        # Answered, but violated the no-tool / JSON-answer contract. That is a
        # model-output defect, never an input problem.
        raise ModelOutputInvalid(error)
    schema_sha256 = hashlib.sha256(json.dumps(schema, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    receipt={'model':model,'usage':usage,'tool_events':tools,'stream_notices':notices,'elapsed_seconds':round(time.monotonic()-started,3),
             'backend':'codex_cli',
             'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
             'prompt_bytes':len(prompt.encode()),
             'schema_sha256':schema_sha256,
             'response_sha256':hashlib.sha256(json.dumps(answer,sort_keys=True).encode()).hexdigest()}
    return answer,receipt


def _translated(exc, target):
    """Keep the public error type while preserving the provider's classification."""
    error = target(redact(str(exc)))
    error.code = getattr(exc, 'code', getattr(target, 'code', 'model_unavailable'))
    error.kind = getattr(exc, 'kind', getattr(target, 'kind', 'model_transport'))
    error.detail = getattr(exc, 'detail', {})
    error.backend = 'deepseek_api'
    return error


def _deepseek_call(prompt, schema, model, timeout, audit_dir, progress_timeout,
                   reasoning, tier, api_options):
    """Delegate to the DeepSeek API backend, keeping the ``(answer, receipt)`` shape.

    The provider raises its own classified exceptions; they are re-raised as the
    module's existing error types so every caller keeps its current handling. The
    provider writes its own audit ledger before raising.
    """
    from . import deepseek_api
    options = dict(api_options or {})
    options.setdefault('stream', True)
    try:
        return deepseek_api.call(prompt, schema, model, timeout=timeout, audit_dir=audit_dir,
                                 options=options, reasoning_effort=reasoning,
                                 service_tier=tier, progress_timeout=progress_timeout)
    except deepseek_api.ApiConfigError as exc:
        raise _translated(exc, ModelConfigError) from exc
    except deepseek_api.ApiOutputInvalid as exc:
        raise _translated(exc, ModelOutputInvalid) from exc
    except deepseek_api.ApiTransportError as exc:
        raise _translated(exc, ModelExecutionError) from exc
