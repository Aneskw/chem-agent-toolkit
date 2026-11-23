"""Version-scoped CLI stderr projection: never persist raw diagnostic lines."""
import hashlib
import json
import re
import time

# Only trace-safe telemetry and selected INFO lifecycle events, never HTTP/header/body tracing.
RUST_LOG = ('error,codex_otel.trace_safe=info,'
            'codex_api::endpoint::responses_websocket=info,'
            'codex_models_manager=info,codex_exec=info,codex_core::client=info,'
            'codex_core::session::startup_prewarm=info')
EVENTS = {'codex.api_request', 'codex.websocket_connect', 'codex.websocket_request',
          'codex.websocket_event', 'codex.sse_event'}
MARKERS = {
    'connecting to websocket:': 'websocket_connect_start',
    'successfully connected to websocket:': 'websocket_connect_success',
    'failed to connect to websocket:': 'websocket_connect_failed',
    'failed to refresh available models:': 'model_catalog_refresh_failed',
    'models cache: evaluating cache eligibility': 'model_cache_check',
    'models cache: no usable cache entry': 'model_cache_miss',
    'models cache: provider or auth identity mismatch': 'model_cache_identity_mismatch',
    'Sent prompt with event ID:': 'local_turn_start_ack',
    'startup websocket prewarm timed out': 'startup_prewarm_timeout',
    'startup websocket prewarm setup failed:': 'startup_prewarm_failed',
}

def project(line):
    line = re.sub(r'\x1b\[[0-9;]*m', '', line)
    # Parse quoted values as complete values so embedded field-looking text cannot leak.
    fields = {}
    for match in re.finditer(r'(?<![\w.])([\w.]+)=("(?:[^"\\]|\\.)*"|[^\s]+)', line):
        key, value = match.groups()
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                continue
        else:
            value = value.rstrip('}:,')
        fields[key] = value
    name = fields.get('event.name')
    out = {'event': name} if name in EVENTS else None
    if out is not None:
        for key in ('duration_ms', 'attempt', 'http.response.status_code'):
            if re.fullmatch(r'\d{1,12}', str(fields.get(key, ''))):
                out[key] = int(fields[key])
        for key in ('success', 'auth.connection_reused', 'auth.retry_after_unauthorized', 'websocket.warmup'):
            if fields.get(key) in ('true', 'false'):
                out[key] = fields[key] == 'true'
        kind = fields.get('event.kind', fields.get('kind', ''))
        if re.fullmatch(r'response\.[a-z_.]{1,80}|unknown|parse_error', kind):
            out['kind'] = kind
        endpoint = fields.get('endpoint', '')
        if endpoint:
            # Endpoint role only, never host, query parameters or userinfo.
            path = endpoint.split('?', 1)[0].rstrip('/')
            out['endpoint_role'] = ('models' if path.endswith('/models') else
                                    'responses' if path.endswith('/responses') else 'other')
        if fields.get('auth.request_id'):
            out['request_id_sha256'] = hashlib.sha256(fields['auth.request_id'].encode()).hexdigest()
    else:
        for marker, event in MARKERS.items():
            if marker in line:
                out = {'event': event}
                break
    if out is None:
        return {'event': 'unclassified_line'}
    # No raw error text, which can contain URLs, response bodies or credentials.
    out['timeout_mentioned'] = 'timed out' in line or 'timeout' in line
    return out

class StderrProjection:
    def __init__(self):
        self.started = time.monotonic()

    def __call__(self, line):
        event = project(line)
        event['observed_seconds'] = round(time.monotonic() - self.started, 3)
        return json.dumps(event, sort_keys=True) + '\n'
