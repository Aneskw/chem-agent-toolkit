"""Opt-in DeepSeek API backend for tool-free structured model calls.

Scope: only the structured ``model_call.call`` interface used by runtime planning,
entry association and contract diagnosis. The native discovery / author / review
sessions keep the Codex CLI transport; this module is not part of that path.

Configuration is explicit and is never guessed:

* ``DEEPSEEK_API_KEY``  - required credential, read from the process environment or
  the repository ``.env`` (the file is git-ignored and its values are never logged);
* ``DEEPSEEK_BASE_URL`` - optional, defaults to the official OpenAI-compatible host;
* ``DEEPSEEK_MODEL``    - required model identifier for a live call.

There is no automatic fallback. A missing setting, an unknown model name, a
non-official endpoint or a failing request raises a classified error instead of
silently retrying through Codex or through another model.

Protocol facts this module is written against (api-docs.deepseek.com, read on
2026-10-27):

* ``POST /chat/completions`` with ``Authorization: Bearer <key>`` and an
  OpenAI-compatible JSON body. Official base URLs are ``https://api.deepseek.com``
  (OpenAI format) and ``https://api.deepseek.com/anthropic`` (Anthropic format).
* ``response_format`` accepts only ``text`` or ``json_object``. The service never
  enforces a caller JSON Schema, so every answer is validated locally with
  ``jsonschema``. Syntactically valid JSON is *not* a schema-conforming answer.
* ``finish_reason`` is one of ``stop``, ``length``, ``content_filter``,
  ``tool_calls``, ``insufficient_system_resource`` or ``aborted``. Only ``stop``
  is a completed answer; ``length`` is a truncated answer.
* Streaming is SSE terminated by ``data: [DONE]``. Usage rides on the last chunk
  before that marker, whose ``choices`` entry carries no new content and a
  non-null ``finish_reason``. ``: keep-alive`` comments and (for non-streaming
  requests) leading blank lines are liveness signal only: they are never
  generation progress and never evidence of success.
* The service closes a request that has not started inference after ten minutes,
  so a short silence is not by itself a fault. The enforceable bound is the
  caller's total deadline, applied to connect, send, read, stream consumption and
  any configured retry.

The finished answer is a JSON object validated against the caller schema. The
receipt records provider, model, the parameters actually sent, prompt and schema
fingerprints, the per-attempt ledger, elapsed time, completion state, the error
classification and every request id the service returned. Authentication material
is never written to disk or to an error message.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import socket
import ssl
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from creation_pipeline.paths import ROOT
from creation_pipeline.records import redact, sanitized

# ---- provider constants -------------------------------------------------------
PROVIDER = 'deepseek'
OFFICIAL_BASE_URL = 'https://api.deepseek.com'
OFFICIAL_HOSTS = frozenset({'api.deepseek.com'})
CHAT_PATH = '/chat/completions'

ENV_KEY = 'DEEPSEEK_API_KEY'
ENV_BASE_URL = 'DEEPSEEK_BASE_URL'
ENV_MODEL = 'DEEPSEEK_MODEL'
ENV_ALLOW_CUSTOM = 'DEEPSEEK_ALLOW_CUSTOM_ENDPOINT'

# ``.env`` in the repository root. Tests repoint this attribute at a temporary file.
ENV_FILE = ROOT / '.env'

# Documented request bounds.
MIN_MAX_TOKENS = 1
MAX_MAX_TOKENS = 393216
DEFAULT_MAX_TOKENS = 65536  # thinking-mode default is 64K; stated explicitly
MAX_RETRIES = 3
MAX_CONNECT_RETRIES = 2

# The provider maps these requested efforts onto its own ladder. The mapping is a
# documented compatibility shim, not an equivalence claim, so both values are kept.
EFFORT_MAP = {'minimal': 'low', 'low': 'low', 'medium': 'high', 'high': 'high',
              'xhigh': 'high', 'max': 'max', 'none': 'none'}
EFFORT_NOTE = ('reasoning_effort uses the provider compatibility ladder '
               '(minimal->low, medium->high, xhigh->high); the requested and sent '
               'values are different and are not claimed to be equivalent')

# One socket read is bounded by the remaining deadline; the granularity constant
# below is gone on purpose. A shorter slice would time out a healthy slow stream and
# poison http.client's reader ("cannot read from timed out object").
ERROR_BODY_LIMIT = 8192
REQUEST_ID_HEADERS = ('x-request-id', 'x-ds-request-id', 'request-id', 'x-trace-id')


class ApiTransportError(ValueError):
    """The request did not produce a trustworthy completion."""

    code = 'model_unavailable'
    kind = 'model_transport'

    def __init__(self, message, code=None, detail=None):
        super().__init__(message)
        if code:
            self.code = code
        self.detail = detail or {}


class ApiOutputInvalid(ApiTransportError):
    """The service answered, but the answer violates the caller contract."""

    code = 'model_output_invalid'


class ApiConfigError(ApiTransportError):
    """Configuration is missing or unsafe; no request was sent."""

    code = 'model_config_invalid'


# ---- configuration ------------------------------------------------------------
def read_env_file(path=None):
    """Read a minimal ``KEY=VALUE`` file. Never raises, never returns comments.

    Only a plain assignment grammar is accepted; shell substitution is not
    evaluated. A malformed line is ignored rather than interpreted.
    """
    values = {}
    try:
        text = Path(path if path is not None else ENV_FILE).read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError):
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[len('export '):].strip()
        name, separator, value = line.partition('=')
        name = name.strip()
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        values[name] = value
    return values


def _setting(name, dotenv, environ):
    for source in (environ, dotenv):
        value = source.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _flag(name, dotenv, environ, default=False):
    value = _setting(name, dotenv, environ)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def endpoint_parts(base_url):
    """Split a base URL into (scheme, host, port, path_prefix) or raise ApiConfigError."""
    try:
        parsed = urlsplit(base_url)
    except ValueError as exc:
        raise ApiConfigError('DEEPSEEK_BASE_URL is not a valid URL') from exc
    scheme = (parsed.scheme or '').lower()
    if scheme not in ('https', 'http'):
        raise ApiConfigError('DEEPSEEK_BASE_URL must use https (http is accepted only for a declared custom endpoint)')
    if parsed.username or parsed.password or '@' in parsed.netloc:
        raise ApiConfigError('DEEPSEEK_BASE_URL must not embed credentials; use DEEPSEEK_API_KEY')
    if parsed.query or parsed.fragment:
        raise ApiConfigError('DEEPSEEK_BASE_URL must not carry a query or fragment')
    host = (parsed.hostname or '').lower()
    if not host:
        raise ApiConfigError('DEEPSEEK_BASE_URL must include a host')
    try:
        port = parsed.port
    except ValueError as exc:
        raise ApiConfigError('DEEPSEEK_BASE_URL has an invalid port') from exc
    path = (parsed.path or '').rstrip('/')
    return scheme, host, port, path


def is_official(scheme, host, port):
    return scheme == 'https' and host in OFFICIAL_HOSTS and port in (None, 443)


class Settings:
    """Resolved, ready-to-use call settings. ``api_key`` is never persisted."""

    def __init__(self, *, api_key, scheme, host, port, prefix, endpoint_kind, model,
                 max_output_tokens, stream, retries, connect_retries, timeout, reasoning_effort,
                 thinking, effort_sent, effort_note, service_tier, progress_timeout):
        self.api_key = api_key
        self.scheme = scheme
        self.host = host
        self.port = port
        self.prefix = prefix
        self.endpoint_kind = endpoint_kind
        self.base_url = '%s://%s%s' % (scheme, host if port is None else '%s:%d' % (host, port), prefix)
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.stream = stream
        self.retries = retries
        self.connect_retries = connect_retries
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort
        self.thinking = thinking
        self.effort_sent = effort_sent
        self.effort_note = effort_note
        self.service_tier = service_tier
        self.progress_timeout = progress_timeout

    def path(self):
        return self.prefix + CHAT_PATH

    def scrub(self, value):
        """Remove the resolved credential from any text before it is stored."""
        value = redact(value)
        if self.api_key and self.api_key in value:
            value = value.replace(self.api_key, '[REDACTED]')
        return value


def _positive_int(value, name, minimum, maximum):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ApiConfigError('%s must be an integer between %d and %s' % (name, minimum, maximum))
    return value


def resolve(model=None, *, timeout, options=None, environ=None, dotenv=None):
    """Resolve credentials, endpoint and request parameters without sending anything."""
    options = dict(options or {})
    environ = os.environ if environ is None else environ
    dotenv = read_env_file() if dotenv is None else dotenv

    api_key = _setting(ENV_KEY, dotenv, environ)
    if api_key is None:
        raise ApiConfigError(
            'DEEPSEEK_API_KEY is not configured (process environment or repository .env); '
            'no request was sent')

    base_url = _setting(ENV_BASE_URL, dotenv, environ) or OFFICIAL_BASE_URL
    scheme, host, port, prefix = endpoint_parts(base_url)
    official = is_official(scheme, host, port)
    if not official:
        permitted = (options.get('allow_custom_endpoint')
                     or _flag(ENV_ALLOW_CUSTOM, dotenv, environ))
        if not permitted:
            raise ApiConfigError(
                'DEEPSEEK_BASE_URL is not the official DeepSeek service and was not '
                'declared as a custom endpoint; refusing to treat a third-party address '
                'as the official provider; no request was sent')

    configured_model = model if isinstance(model, str) and model.strip() else _setting(ENV_MODEL, dotenv, environ)
    if not configured_model:
        raise ApiConfigError(
            'No DeepSeek model is configured (set model.name in the runtime options or '
            'DEEPSEEK_MODEL); the model name is never guessed; no request was sent')
    configured_model = str(configured_model).strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', configured_model):
        raise ApiConfigError('Configured model identifier is not a plain model name')

    max_tokens = options.get('max_output_tokens')
    if max_tokens is None:
        max_tokens = DEFAULT_MAX_TOKENS
    _positive_int(max_tokens, 'max_output_tokens', MIN_MAX_TOKENS, MAX_MAX_TOKENS)

    retries = options.get('retries', 0)
    if type(retries) is not int or not 0 <= retries <= MAX_RETRIES:
        raise ApiConfigError('retries must be an integer between 0 and %d' % MAX_RETRIES)

    # A connection that never opened cannot have reached the model, so retrying it
    # cannot duplicate model work. This is separate from ``retries`` (which is a
    # model-request retry) and is bounded the same way.
    connect_retries = options.get('connect_retries', 0)
    if type(connect_retries) is not int or not 0 <= connect_retries <= MAX_CONNECT_RETRIES:
        raise ApiConfigError('connect_retries must be an integer between 0 and %d'
                             % MAX_CONNECT_RETRIES)

    stream = options.get('stream', True)
    if type(stream) is not bool:
        raise ApiConfigError('stream must be a boolean')

    if timeout is None or float(timeout) <= 0:
        raise ApiConfigError('A positive total call deadline is required')
    timeout = float(timeout)

    requested_effort = options.get('reasoning_effort')
    if requested_effort is not None:
        token = str(requested_effort).strip().lower()
        if token not in EFFORT_MAP:
            raise ApiConfigError('reasoning_effort must be one of ' + ', '.join(sorted(EFFORT_MAP)))
        requested_effort = token
        effort_sent = EFFORT_MAP[token]
    else:
        effort_sent = None

    if effort_sent == 'none':
        thinking = {'type': 'disabled'}
        effort_payload = None
    elif effort_sent is None:
        # Provider default: thinking enabled with high effort. Not asserted here.
        thinking = None
        effort_payload = None
    else:
        thinking = {'type': 'enabled'}
        effort_payload = effort_sent

    return Settings(
        api_key=api_key, scheme=scheme, host=host, port=port, prefix=prefix,
        endpoint_kind='official' if official else 'custom',
        model=configured_model, max_output_tokens=max_tokens, stream=stream,
        retries=retries, connect_retries=connect_retries, timeout=timeout, reasoning_effort=requested_effort,
        thinking=thinking, effort_sent=effort_sent, effort_note=EFFORT_NOTE,
        service_tier=options.get('service_tier'),
        progress_timeout=options.get('progress_timeout'))


# ---- request building ---------------------------------------------------------
SYSTEM_PROMPT = (
    'You are a tool-free structured data producer. Answer with exactly one JSON '
    'object and no other text, commentary or code fence. Do not call tools and do '
    'not read files. The object must validate against the JSON Schema below; a '
    'syntactically valid JSON document that does not satisfy the schema is a '
    'failed answer.\n\nJSON Schema:\n')


def build_body(settings, prompt, schema):
    """Assemble the OpenAI-compatible request body and its recorded parameters."""
    schema_text = json.dumps(schema, ensure_ascii=False, sort_keys=True)
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT + schema_text},
        {'role': 'user', 'content': prompt},
    ]
    body = {'model': settings.model, 'messages': messages, 'stream': settings.stream,
            'response_format': {'type': 'json_object'},
            'max_tokens': settings.max_output_tokens}
    if settings.stream:
        body['stream_options'] = {'include_usage': True}
    if settings.thinking is not None:
        body['thinking'] = settings.thinking
    if settings.effort_sent not in (None, 'none'):
        body['reasoning_effort'] = settings.effort_sent
    # The service has no ``json_schema`` response_format, so the schema travels in the
    # system message and is enforced locally in ``_decode_answer``.
    recorded = {
        'model': body['model'],
        'stream': body['stream'],
        'stream_options': body.get('stream_options'),
        'response_format': body['response_format'],
        'max_tokens': body['max_tokens'],
        'thinking': body.get('thinking'),
        'reasoning_effort': body.get('reasoning_effort'),
        'messages_count': len(messages),
        'structured_output_mode': 'json_object + local JSON Schema validation '
                                  '(the service does not accept a caller JSON Schema)',
        'temperature': 'not sent (has no effect in thinking mode)',
        'tools': 'not sent (tool-free contract; any tool call is rejected)',
    }
    return body, messages, recorded


# ---- audit helpers ------------------------------------------------------------
def _prepare_audit(audit_dir):
    if not audit_dir:
        return None
    destination = Path(audit_dir)
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def _save(settings, destination, name, value):
    if not destination:
        return
    text = json.dumps(sanitized(value), ensure_ascii=False, indent=2, sort_keys=True)
    # A failed audit write raises: it must never be reported as a usable answer.
    (destination / name).write_text(settings.scrub(text), encoding='utf-8')


def _ledger(settings, attempts):
    return {'attempts': attempts, 'request_count': len(attempts),
            'sdk_implicit_retries': 'none (no SDK used)',
            'retry_policy': {'configured': settings.retries,
                             'counted_in_total_deadline': True},
            # A connect retry is a transport retry, never a second model request.
            'connect_retries': sum(1 for item in attempts if item.get('connect_retry')),
            'connect_retry_policy': {'configured': settings.connect_retries,
                                     'scope': 'only when the TCP/TLS connection never opened'}}


# ---- transport ----------------------------------------------------------------
def _exception_text(exc, limit=200):
    """Keep the exception class and message; the caller scrubs credentials."""
    message = str(exc).strip()
    text = type(exc).__name__ + (': ' + message if message else '')
    return text[:limit]


class _Reader:
    """Buffered reader bounded by one wall-clock deadline.

    The read timeout is armed from the remaining budget and is never shorter than
    it. A timeout therefore means the deadline expired, so the reader is never
    reused after a timeout: ``socket.SocketIO`` raises
    ``OSError: cannot read from timed out object`` on the next read, which would be
    misreported as a broken connection.
    """

    def __init__(self, response, connection, deadline, sock=None):
        self.response = response
        self.connection = connection
        self.deadline = deadline
        # ``HTTPConnection.getresponse()`` closes its own reference when the server
        # says ``Connection: close``, so keep the socket captured after connect().
        self.sock = sock if sock is not None else getattr(connection, 'sock', None)
        self.buffer = b''
        self.gaps = 0
        self.bytes = 0
        self.eof = False

    def _fill(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ApiTransportError(
                'Total model call deadline expired while reading the response; '
                'the connection was closed', code='model_timeout',
                detail={'phase': 'stream_read', 'bytes_received': self.bytes})
        if self.sock is not None:
            try:
                self.sock.settimeout(max(0.05, remaining))
            except OSError:
                pass
        try:
            data = self.response.read1(65536)
        except (socket.timeout, TimeoutError) as exc:
            raise ApiTransportError(
                'Total model call deadline expired while waiting for the model stream',
                code='model_timeout',
                detail={'phase': 'stream_read', 'bytes_received': self.bytes,
                        'exception': _exception_text(exc)}) from exc
        except ssl.SSLError as exc:
            raise ApiTransportError('TLS failure while reading the model response: '
                                    + _exception_text(exc), code='model_stream_interrupted',
                                    detail={'bytes_received': self.bytes}) from exc
        except (OSError, http.client.HTTPException) as exc:
            raise ApiTransportError('Model connection failed while reading the response: '
                                    + _exception_text(exc), code='model_stream_interrupted',
                                    detail={'bytes_received': self.bytes,
                                            'errno': getattr(exc, 'errno', None)}) from exc
        if not data:
            self.eof = True
            return False
        self.bytes += len(data)
        self.buffer += data
        return True

    def readline(self):
        """Return one line without its newline, or None at end of stream."""
        while b'\n' not in self.buffer:
            if self.eof:
                if not self.buffer:
                    return None
                line, self.buffer = self.buffer, b''
                return line
            if not self._fill():
                if not self.buffer:
                    return None
        line, _, self.buffer = self.buffer.partition(b'\n')
        return line

    def read_all(self):
        while self._fill():
            pass
        data, self.buffer = self.buffer, b''
        return data


def _resolve_before(host, port, deadline):
    """Resolve the model host under the caller's deadline.

    ``socket.getaddrinfo`` is a blocking C call with no timeout argument, so a slow
    resolver would otherwise sit outside the total budget. It runs in a daemon worker
    and is abandoned if the deadline expires first: the call fails closed and reports
    ``model_timeout`` instead of silently overrunning.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ApiTransportError('Total model call deadline expired before DNS resolution',
                                code='model_timeout')
    outcome = {}

    def work():
        try:
            outcome['addresses'] = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except BaseException as exc:                       # noqa: BLE001 - reported below
            outcome['error'] = exc

    worker = threading.Thread(target=work, daemon=True, name='deepseek-resolve')
    worker.start()
    worker.join(max(0.0, remaining))
    if worker.is_alive():
        raise ApiTransportError(
            'DNS resolution for the model host did not finish inside the total call deadline',
            code='model_timeout', detail={'phase': 'dns'})
    if 'error' in outcome:
        raise outcome['error']
    addresses = outcome.get('addresses') or []
    if not addresses:
        raise OSError('The model host did not resolve to any address')
    return addresses


def _connect_before(host, port, deadline):
    """Open one TCP connection, resolving and connecting inside the deadline."""
    addresses = _resolve_before(host, port, deadline)
    failure = None
    for family, socktype, protocol, _, sockaddr in addresses:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ApiTransportError('Total model call deadline expired during connection',
                                    code='model_timeout', detail={'phase': 'connect'})
        candidate = socket.socket(family, socktype, protocol)
        try:
            candidate.settimeout(max(0.05, remaining))
            candidate.connect(sockaddr)
            # The TLS handshake runs inside http.client right after this returns, so
            # re-arm with the budget that is actually left instead of the pre-connect
            # value.
            candidate.settimeout(max(0.05, deadline - time.monotonic()))
            return candidate
        except OSError as exc:
            candidate.close()
            failure = exc
            if time.monotonic() >= deadline:
                raise ApiTransportError(
                    'Total model call deadline expired during connection',
                    code='model_timeout', detail={'phase': 'connect'}) from exc
    raise failure or OSError('No usable address for the model host')


def _arm(connection, deadline, sock=None):
    """Re-derive the socket timeout from the remaining budget before a blocking step.

    This is what keeps connect, send, header wait and stream reads inside one total
    deadline: each step is bounded by what is actually left, not by a stale timeout.
    ``sock`` is the reference captured after connect(), because http.client drops its
    own when the server answers ``Connection: close``.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ApiTransportError(
            'Total model call deadline expired before the next network step',
            code='model_timeout')
    target = sock if sock is not None else getattr(connection, 'sock', None)
    if target is not None:
        try:
            target.settimeout(max(0.05, remaining))
        except OSError:
            pass
    return remaining


def _connection(settings, deadline):
    remaining = max(0.05, deadline - time.monotonic())
    if settings.scheme == 'https':
        connection = http.client.HTTPSConnection(
            settings.host, settings.port, timeout=remaining,
            context=ssl.create_default_context())
    else:
        connection = http.client.HTTPConnection(settings.host, settings.port, timeout=remaining)
    # Route name resolution and the TCP connect through the deadline-aware helpers.
    # The TLS handshake stays inside http.client and inherits the socket timeout that
    # ``_connect_before`` installed, so it is bounded by the same deadline.
    connection._create_connection = (
        lambda address, timeout=None, source_address=None:
        _connect_before(address[0], address[1], deadline))
    return connection


def _request_id(headers, body_id):
    for name, value in headers:
        if name.lower() in REQUEST_ID_HEADERS and value:
            return {'value': value, 'source': 'header:' + name.lower()}
    if body_id:
        return {'value': body_id, 'source': 'body:id'}
    return None


def _error_payload(reader, settings):
    """Read a bounded, scrubbed error body; never raise from the error path."""
    try:
        raw = reader.read_all()
    except ApiTransportError:
        return None
    text = raw[:ERROR_BODY_LIMIT].decode('utf-8', 'replace').strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except ValueError:
        return {'body_excerpt': settings.scrub(text[:400])}
    if isinstance(parsed, dict) and isinstance(parsed.get('error'), dict):
        error = parsed['error']
        return {k: settings.scrub(str(error.get(k))) for k in ('message', 'type', 'code')
                if error.get(k) is not None}
    return {'body_excerpt': settings.scrub(text[:400])}


STATUS_CODES = {400: 'model_request_invalid', 401: 'model_auth_failed', 402: 'model_insufficient_balance',
                403: 'model_auth_failed', 404: 'model_request_invalid', 413: 'model_request_invalid',
                422: 'model_request_invalid', 429: 'model_rate_limited', 500: 'model_server_error',
                502: 'model_server_error', 503: 'model_server_error', 504: 'model_server_error'}


def _status_error(status, payload):
    code = STATUS_CODES.get(status, 'model_http_error')
    detail = {'http_status': status}
    if isinstance(payload, dict):
        detail.update({k: v for k, v in payload.items()
                       if k in ('type', 'code', 'message', 'body_excerpt')})
    message = 'DeepSeek request failed with HTTP %d (%s)' % (status, code)
    if isinstance(payload, dict) and payload.get('message'):
        message += ': ' + str(payload['message'])[:300]
    return ApiTransportError(message, code=code, detail=detail)


def _stream_error(settings, error):
    raw_code = error.get('code')
    status = raw_code if isinstance(raw_code, int) else None
    payload = {'type': settings.scrub(str(error.get('type') or '')),
               'code': settings.scrub(str(raw_code or '')),
               'message': settings.scrub(str(error.get('message') or ''))}
    if status is not None:
        return _status_error(status, payload)
    return ApiTransportError(
        'The service reported an error inside the stream: ' + payload['message'][:300],
        code='model_stream_interrupted', detail=payload)


# ---- completion interpretation ------------------------------------------------
TRUNCATED = 'length'
INTERRUPTED = {'insufficient_system_resource', 'aborted'}


def _check_finish(finish_reason):
    """Only ``stop`` is a completed answer; every other reason is classified."""
    if finish_reason == 'stop':
        return
    if finish_reason == TRUNCATED:
        raise ApiTransportError(
            'The model stopped at the max_tokens limit (finish_reason=length); the answer '
            'is incomplete and is never accepted', code='model_output_truncated',
            detail={'finish_reason': finish_reason})
    if finish_reason in INTERRUPTED:
        raise ApiTransportError(
            'The service interrupted generation (finish_reason=' + str(finish_reason)
            + '); the answer is incomplete', code='model_stream_interrupted',
            detail={'finish_reason': finish_reason})
    if finish_reason == 'content_filter':
        raise ApiTransportError('The response was withheld by a server content filter',
                                code='model_content_filtered',
                                detail={'finish_reason': finish_reason})
    if finish_reason == 'tool_calls':
        raise ApiOutputInvalid('The response contains tool calls, which the tool-free '
                               'contract forbids', code='model_output_invalid',
                               detail={'finish_reason': finish_reason})
    raise ApiTransportError('Unexpected finish_reason ' + str(finish_reason)
                            + '; completion cannot be proven',
                            code='model_output_incomplete',
                            detail={'finish_reason': finish_reason})


def _decode_answer(content, schema):
    """Parse and locally validate. Valid JSON is not a schema-conforming answer."""
    if content is None or not str(content).strip():
        raise ApiOutputInvalid('The model returned empty content; JSON Output can do this '
                               'and it is never accepted as an answer',
                               code='model_output_empty')
    text = str(content)
    try:
        answer = json.loads(text)
    except ValueError as exc:
        raise ApiOutputInvalid('The model content is not valid JSON; the response is '
                               'incomplete or malformed: ' + str(exc)[:200]) from exc
    if not isinstance(answer, dict):
        raise ApiOutputInvalid('The structured answer must be a JSON object, got '
                               + type(answer).__name__)
    try:
        import jsonschema
    except ImportError as exc:
        raise ApiConfigError('jsonschema is required for local schema validation') from exc
    try:
        jsonschema.validate(answer, schema)
    except jsonschema.ValidationError as exc:
        location = '/'.join(str(p) for p in exc.absolute_path) or '<root>'
        raise ApiOutputInvalid('The answer does not satisfy the caller JSON Schema at '
                               + location + ': ' + str(exc.message)[:300],
                               code='model_schema_mismatch',
                               detail={'schema_path': location}) from exc
    except jsonschema.SchemaError as exc:
        raise ApiConfigError('The caller JSON Schema itself is invalid: '
                             + str(exc.message)[:200]) from exc
    return answer


def _consume_stream(settings, response, connection, deadline, destination, state, sock=None):
    reader = _Reader(response, connection, deadline, sock)
    content = []
    data_lines = []

    def dispatch():
        nonlocal data_lines
        payload = b'\n'.join(data_lines).decode('utf-8', 'replace').strip()
        data_lines = []
        if not payload:
            return
        if payload == '[DONE]':
            state['done'] = True
            return
        try:
            chunk = json.loads(payload)
        except ValueError as exc:
            raise ApiTransportError('Malformed streamed JSON frame; the stream is '
                                    'incomplete', code='model_stream_interrupted') from exc
        if not isinstance(chunk, dict):
            raise ApiTransportError('Malformed streamed frame; the stream is incomplete',
                                    code='model_stream_interrupted')
        if isinstance(chunk.get('error'), dict):
            raise _stream_error(settings, chunk['error'])
        state['chunks'] += 1
        if chunk.get('id') and state['body_id'] is None:
            state['body_id'] = str(chunk['id'])
        if isinstance(chunk.get('usage'), dict):
            state['usage'] = chunk['usage']
        choices = chunk.get('choices') or []
        if not isinstance(choices, list) or not choices:
            return
        choice = choices[0]
        if not isinstance(choice, dict):
            return
        delta = choice.get('delta') or {}
        if isinstance(delta, dict):
            if delta.get('tool_calls'):
                raise ApiOutputInvalid('The response contains tool call deltas, which the '
                                       'tool-free contract forbids')
            piece = delta.get('content')
            if isinstance(piece, str):
                content.append(piece)
            reasoning = delta.get('reasoning_content')
            if isinstance(reasoning, str):
                state['reasoning_chars'] += len(reasoning)
        if choice.get('finish_reason') is not None:
            state['finish_reason'] = choice['finish_reason']

    while not state['done']:
        line = reader.readline()
        if line is None:
            break
        line = line.rstrip(b'\r')
        if not line.strip():
            dispatch()
            continue
        if line.startswith(b':'):
            state['keepalives'] += 1
            continue
        if line.startswith(b'data:'):
            data_lines.append(line[5:].lstrip(b' '))
            continue
        # Other SSE fields (event:/id:/retry:) carry no answer content.
        state['other_fields'] += 1
    if data_lines:
        dispatch()
    state['bytes'] = reader.bytes
    state['gap_retries'] = reader.gaps
    if not state['done']:
        raise ApiTransportError(
            'The stream ended without the data: [DONE] completion marker; the answer is '
            'incomplete', code='model_stream_interrupted',
            detail={'chunks': state['chunks'], 'finish_reason': state['finish_reason'],
                    'bytes': reader.bytes})
    if state['finish_reason'] is None:
        raise ApiTransportError('The stream finished without a terminal finish_reason; '
                                'completion is unproven', code='model_stream_interrupted',
                                detail={'chunks': state['chunks']})
    if destination:
        _save(settings, destination, 'stream.json',
              {'chunks': state['chunks'], 'keepalives': state['keepalives'],
               'other_fields': state['other_fields'], 'bytes': reader.bytes,
               'finish_reason': state['finish_reason'], 'done_marker': True,
               'reasoning_chars': state['reasoning_chars']})
    return ''.join(content)


def _consume_single(settings, response, connection, deadline, destination, state, sock=None):
    reader = _Reader(response, connection, deadline, sock)
    raw = reader.read_all()
    state['bytes'] = len(raw)
    state['gap_retries'] = reader.gaps
    # Non-streaming keep-alives are leading blank lines; they are not content.
    text = raw.lstrip()
    if not text:
        raise ApiTransportError('The response body was empty; no completion was returned',
                                code='model_stream_interrupted')
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise ApiTransportError('The response body is not valid JSON; the answer is '
                                'incomplete', code='model_stream_interrupted') from exc
    if not isinstance(payload, dict):
        raise ApiTransportError('Malformed response body; the answer is incomplete',
                                code='model_stream_interrupted')
    if isinstance(payload.get('error'), dict):
        raise _stream_error(settings, payload['error'])
    state['chunks'] = 1
    state['body_id'] = str(payload['id']) if payload.get('id') else None
    if isinstance(payload.get('usage'), dict):
        state['usage'] = payload['usage']
    choices = payload.get('choices') or []
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ApiTransportError('The response carries no choice; completion is unproven',
                                code='model_stream_interrupted')
    choice = choices[0]
    state['finish_reason'] = choice.get('finish_reason')
    message = choice.get('message') or {}
    if not isinstance(message, dict):
        message = {}
    if message.get('tool_calls'):
        raise ApiOutputInvalid('The response contains tool calls, which the tool-free '
                               'contract forbids')
    if isinstance(message.get('reasoning_content'), str):
        state['reasoning_chars'] = len(message['reasoning_content'])
    if state['finish_reason'] is None:
        raise ApiTransportError('The response has no finish_reason; completion is unproven',
                                code='model_stream_interrupted')
    if destination:
        _save(settings, destination, 'stream.json',
              {'chunks': 1, 'keepalives': 0, 'bytes': len(raw),
               'finish_reason': state['finish_reason'], 'done_marker': None,
               'reasoning_chars': state['reasoning_chars']})
    return message.get('content')


# ---- public entry point -------------------------------------------------------
def call(prompt, schema, model, *, timeout, audit_dir=None, options=None, reasoning_effort=None,
         service_tier=None, progress_timeout=None, environ=None, dotenv=None):
    """One bounded DeepSeek request. Returns ``(answer, receipt)`` or raises.

    ``timeout`` is the total application-level deadline. It covers connection,
    sending, reading, stream consumption and every configured retry; it is never
    replaced by a per-read timeout.
    """
    started = time.monotonic()
    deadline = started + float(timeout)
    resolved_options = dict(options or {})
    resolved_options.setdefault('reasoning_effort', reasoning_effort)
    resolved_options.setdefault('service_tier', service_tier)
    resolved_options.setdefault('progress_timeout', progress_timeout)

    destination = _prepare_audit(audit_dir)
    try:
        settings = resolve(model, timeout=timeout, options=resolved_options,
                           environ=environ, dotenv=dotenv)
    except ApiConfigError as exc:
        if destination:
            _save_settings_free(destination, {
                'backend': 'deepseek_api', 'provider': PROVIDER, 'status': 'config_invalid',
                'error_class': exc.code, 'request_sent': False,
                'error': redact(str(exc)), 'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'model_requested': model, 'audit_note': 'No request was sent.'})
            _save_settings_free(destination, {'error_class': exc.code,
                                              'message': redact(str(exc)),
                                              'request_sent': False}, name='error.json')
        raise

    body, messages, recorded = build_body(settings, prompt, schema)
    payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
    observation = {
        'backend': 'deepseek_api',
        'provider': PROVIDER,
        'endpoint': {'base_url': settings.base_url, 'path': settings.path(),
                     'kind': settings.endpoint_kind},
        'model': settings.model,
        'timeout_seconds': settings.timeout,
        'deadline_scope': 'connect, send, read, stream consumption and all configured retries',
        'retries': settings.retries,
        'connect_retries': settings.connect_retries,
        'sdk': 'none (stdlib http.client); no implicit SDK retries exist',
        'request_params': recorded,
        'requested_settings': {'reasoning_effort': settings.reasoning_effort,
                               'service_tier': settings.service_tier},
        'mapped_settings': {'reasoning_effort_sent': settings.effort_sent,
                            'thinking': settings.thinking,
                            'service_tier': 'not supported by this backend; recorded, never sent',
                            'note': settings.effort_note},
        'prompt_sha256': hashlib.sha256(str(prompt).encode('utf-8')).hexdigest(),
        'prompt_bytes': len(str(prompt).encode('utf-8')),
        'schema_sha256': hashlib.sha256(
            json.dumps(schema, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest(),
        'messages_sha256': hashlib.sha256(
            json.dumps(messages, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest(),
        'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'progress_watch': 'not applied: keep-alives are not generation progress and the '
                          'provider closes a request that has not started inference after '
                          'ten minutes; the total deadline is the only bound',
        'progress_timeout_seconds': progress_timeout,
        'status': 'starting',
    }
    if destination:
        (destination / 'schema.json').write_text(
            settings.scrub(json.dumps(schema, ensure_ascii=False)), encoding='utf-8')
        _save(settings, destination, 'request.json', observation)

    attempts = []
    last_error = None
    connect_retries_used = 0
    retries_used = 0
    attempt = 0
    while True:
        if retries_used:
            pause = min(1.0 * retries_used, max(0.0, deadline - time.monotonic()))
            if pause <= 0:
                break
            time.sleep(pause)
        elif connect_retries_used:
            pause = min(0.5 * connect_retries_used, max(0.0, deadline - time.monotonic()))
            if pause <= 0:
                break
            time.sleep(pause)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            last_error = ApiTransportError(
                'Total model call deadline expired before the request could be sent',
                code='model_timeout', detail={'attempt': attempt + 1})
            break
        record = {'attempt': attempt + 1, 'started_seconds': round(time.monotonic() - started, 3)}
        state = {'done': False, 'chunks': 0, 'keepalives': 0, 'other_fields': 0,
                 'finish_reason': None, 'usage': None, 'body_id': None,
                 'reasoning_chars': 0, 'bytes': 0, 'gap_retries': 0}
        connection = None
        response = None
        sock = None
        connected = False
        try:
            connection = _connection(settings, deadline)
            connection.connect()                       # DNS + TCP + TLS, all deadline-bounded
            connected = True
            # Capture the live socket here: getresponse() drops connection.sock for a
            # Connection: close response, and every later timeout must still be armed.
            sock = getattr(connection, 'sock', None)
            record['connected_seconds'] = round(time.monotonic() - started, 3)
            _arm(connection, deadline, sock)           # send is bounded by what is left
            connection.putrequest('POST', settings.path())
            connection.putheader('Content-Type', 'application/json; charset=utf-8')
            connection.putheader('Accept', 'text/event-stream' if settings.stream else 'application/json')
            connection.putheader('Authorization', 'Bearer ' + settings.api_key)
            connection.putheader('Content-Length', str(len(payload)))
            connection.endheaders()
            connection.send(payload)
            record['sent_seconds'] = round(time.monotonic() - started, 3)
            _arm(connection, deadline, sock)           # header wait is re-derived, not stale
            response = connection.getresponse()
            record['http_status'] = response.status
            record['connection_close'] = bool(getattr(response, 'will_close', False))
            headers = response.getheaders()
            record['response_headers'] = {name.lower(): value for name, value in headers
                                          if name.lower() in ('content-type', 'connection') + REQUEST_ID_HEADERS}
            header_id = _request_id(headers, None)
            if header_id:
                record['request_id'] = header_id
            if response.status != 200:
                reader = _Reader(response, connection, deadline, sock)
                raise _status_error(response.status, _error_payload(reader, settings))
            if settings.stream:
                content = _consume_stream(settings, response, connection, deadline,
                                          destination, state, sock)
            else:
                content = _consume_single(settings, response, connection, deadline,
                                          destination, state, sock)
            _check_finish(state['finish_reason'])
            answer = _decode_answer(content, schema)
            request_id = header_id or (_request_id((), state['body_id']))
            record.update(status='completed', finish_reason=state['finish_reason'],
                          elapsed_seconds=round(time.monotonic() - started, 3),
                          response_bytes=state['bytes'], keepalives=state['keepalives'],
                          chunks=state['chunks'], done_marker=state['done'])
            if request_id:
                record['request_id'] = request_id
            attempts.append(record)
            if destination:
                _save(settings, destination, 'response.json', {
                    'request_id': request_id, 'model': settings.model,
                    'finish_reason': state['finish_reason'], 'usage': state['usage'],
                    'content': content, 'reasoning_chars': state['reasoning_chars'],
                    'schema_validated': True})
            receipt = _receipt(settings, answer, prompt, schema, messages, state,
                               request_id, started, attempts)
            observation.update(status='completed', request_count=len(attempts),
                               elapsed_seconds=round(time.monotonic() - started, 3))
            if destination:
                _save(settings, destination, 'request.json', observation)
                _save(settings, destination, 'attempts.json', _ledger(settings, attempts))
            return answer, receipt
        except ApiTransportError as exc:
            last_error = exc
            record.update(status='failed', error_class=exc.code,
                          error=settings.scrub(str(exc))[:500],
                          elapsed_seconds=round(time.monotonic() - started, 3))
            if getattr(exc, 'detail', None):
                # Keep the failure forensics: bytes already received and the original
                # exception distinguish "no data" from "cut mid-stream".
                record['detail'] = sanitized(exc.detail)
            attempts.append(record)
            if destination:
                _save(settings, destination, 'attempts.json', _ledger(settings, attempts))
            if exc.code in ('model_auth_failed', 'model_insufficient_balance',
                            'model_request_invalid', 'model_config_invalid'):
                # Retrying a credential, balance or request-shape failure cannot help.
                break
            if retries_used < settings.retries:
                retries_used += 1
                attempt += 1
                continue
            break
        except (ssl.SSLError, OSError, http.client.HTTPException, socket.timeout) as exc:
            # A socket timeout was armed from the remaining budget, so once it fires
            # the total deadline has expired: that is a deadline verdict, not a plain
            # connection failure. Anything else stays a transport fault.
            expired = time.monotonic() >= deadline - 0.01
            last_error = ApiTransportError(
                ('Total model call deadline expired during a network step'
                 if expired else 'DeepSeek connection failed: ' + type(exc).__name__),
                code='model_timeout' if expired else 'model_connection_failed',
                detail={'attempt': attempt + 1,
                        'exception': type(exc).__name__})
            record.update(status='failed', error_class=last_error.code,
                          error=settings.scrub(str(exc))[:500],
                          elapsed_seconds=round(time.monotonic() - started, 3))
            attempts.append(record)
            if destination:
                _save(settings, destination, 'attempts.json', _ledger(settings, attempts))
            if (not expired and not connected and not record.get('sent_seconds')
                    and connect_retries_used < settings.connect_retries):
                # The connection never opened, so no request reached the provider and
                # retrying cannot duplicate model work. Anything after a successful
                # connect (or a deadline verdict) is never retried here.
                connect_retries_used += 1
                record['connect_retry'] = True
                attempt += 1
                continue
            if not expired and retries_used < settings.retries:
                retries_used += 1
                attempt += 1
                continue
            if expired or retries_used >= settings.retries:
                break
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    error = last_error or ApiTransportError('DeepSeek request did not complete',
                                            code='model_unavailable')
    observation.update(status='failed', error_class=error.code,
                       error=settings.scrub(str(error))[:500],
                       request_count=len(attempts),
                       elapsed_seconds=round(time.monotonic() - started, 3))
    if destination:
        _save(settings, destination, 'request.json', observation)
        _save(settings, destination, 'error.json', {
            'error_class': error.code, 'message': settings.scrub(str(error)),
            'detail': sanitized(error.detail), 'attempts': attempts,
            'request_count': len(attempts),
            'retry_policy': {'configured': settings.retries,
                             'counted_in_total_deadline': True}})
    raise error


def _save_settings_free(destination, value, name='request.json'):
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    (destination / name).write_text(redact(text), encoding='utf-8')


def _receipt(settings, answer, prompt, schema, messages, state, request_id, started, attempts):
    return {
        'backend': 'deepseek_api',
        'provider': PROVIDER,
        'model': settings.model,
        'usage': state['usage'] or {},
        'tool_events': [],
        'stream_notices': [],
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'prompt_sha256': hashlib.sha256(str(prompt).encode('utf-8')).hexdigest(),
        'schema_sha256': hashlib.sha256(
            json.dumps(schema, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest(),
        'messages_sha256': hashlib.sha256(
            json.dumps(messages, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest(),
        'response_sha256': hashlib.sha256(
            json.dumps(answer, sort_keys=True).encode('utf-8')).hexdigest(),
        'endpoint': {'base_url': settings.base_url, 'path': settings.path(),
                     'kind': settings.endpoint_kind},
        'request_params': {'model': settings.model, 'stream': settings.stream,
                           'max_tokens': settings.max_output_tokens,
                           'response_format': 'json_object',
                           'thinking': settings.thinking,
                           'reasoning_effort_sent': settings.effort_sent,
                           'reasoning_effort_requested': settings.reasoning_effort,
                           'service_tier_requested': settings.service_tier},
        'mapping': {'reasoning_effort': settings.effort_note,
                    'service_tier': 'not supported by this backend; recorded, never sent'},
        'request_id': request_id,
        'request_count': len(attempts),
        'requests': attempts,
        'completion': {'status': 'completed', 'finish_reason': state['finish_reason'],
                       'done_marker': state['done'], 'chunks': state['chunks'],
                       'keepalives': state['keepalives'], 'schema_validated': True,
                       'schema_mode': 'local jsonschema'},
        'retry_policy': {'configured': settings.retries, 'sdk_implicit_retries': 'none',
                         'counted_in_total_deadline': True},
    }
