"""LOCAL DESIGN PROTOTYPE ONLY. No adapter to the installed CLI and no model call.

Exercises a proposed metadata-only producer contract. Passing its tests does NOT
establish that the installed CLI exports these signals; the launch gate stays shut.
"""
import json
import re
import time

REQUIRED = frozenset({'wire_frame_metadata', 'connection_request_identity', 'warmup_identity',
    'parse_event_identity', 'internal_forward', 'stdout_forward', 'retry_identity'})
INSTALLED_VERIFIED = frozenset({'warmup_identity', 'stdout_forward'})

def launch_gate(verified=INSTALLED_VERIFIED):
    missing = sorted(REQUIRED - verified)
    return {'allowed': not missing, 'missing_verified_signals': missing}

class ProposedObserver:
    """Sink prototype; real producer would live INSIDE WsStream before Ping handling."""
    def __init__(self, sink, clock=time.monotonic):
        self.sink, self.clock = sink, clock
        self.start = clock()
        self.connection = self.request = 0
        self.warmup = False

    def emit(self, stage, **metadata):
        record = dict(stage=stage, monotonic_seconds=round(self.clock()-self.start, 6),
                      connection=self.connection, request=self.request, warmup=self.warmup, **metadata)
        self.sink.write(json.dumps(record, sort_keys=True)+'\n')
        self.sink.flush()

    def connect(self):
        self.connection += 1
        self.emit('connect_start')
        self.emit('handshake', status=101)  # LOCAL FIXTURE status, never asserted for real CLI.

    def send(self, warmup=False):
        self.request += 1
        self.warmup = warmup
        self.emit('send_start')
        self.emit('send_complete')

    def inbound(self, frame_kind, payload, forward=True):
        if frame_kind not in {'ping', 'pong', 'text', 'binary', 'close'}:
            self.emit('stream_error', error_class='unknown_frame_type')
            return
        self.emit('inbound_frame', frame_kind=frame_kind, byte_count=len(payload))
        if frame_kind in {'ping', 'pong', 'close'}:
            return
        if frame_kind != 'text':
            self.emit('stream_error', error_class='unexpected_binary')
            return
        try:
            event = json.loads(payload)
            kind = event.get('type') if isinstance(event, dict) else None
            if kind not in {'response.created', 'response.output_text.delta',
                            'response.completed', 'response.failed'}:
                self.emit('parse_unknown', error_class='unknown_event_type')
                return
            fields = {'event_type': kind}
            response = event.get('response', {})
            identity = response.get('id') if isinstance(response, dict) else None
            if isinstance(identity, str) and re.fullmatch(r'resp_[A-Za-z0-9_-]{1,96}', identity):
                fields['response_id'] = identity
            self.emit('parsed_event', **fields)
            if forward:
                self.emit('internal_forward', event_type=kind)
        except (ValueError, UnicodeError):
            # Never stringify parser exceptions: they can expose input contents.
            self.emit('parse_error', error_class='invalid_json')

    def retry(self):
        self.emit('retry', error_class='stream_error')
        self.connect()
        self.send(self.warmup)

    def stdout(self, event_type):
        if event_type in {'turn.started', 'item.completed', 'turn.completed', 'turn.failed'}:
            self.emit('stdout_forward', event_type=event_type)

    def deadline(self):
        self.emit('watchdog_timeout')

def safe_unknown_log(line):
    """Prototype projection, not a claim that CLI emits any missing frame signal."""
    plain = re.sub(r'\x1b\[[0-9;]*m', '', line)
    match = re.search(r'\b(TRACE|DEBUG|INFO|WARN|ERROR)\s+([a-z_][a-z0-9_:]+):', plain)
    modules = {'codex_api::endpoint::responses_websocket', 'codex_core::responses_retry',
               'codex_models_manager::manager', 'codex_otel.trace_safe'}
    result = {'level': 'unknown', 'module': 'other', 'error_class': 'unclassified'}
    if match:
        result['level'] = match[1]
        result['module'] = match[2] if match[2] in modules else 'other'
    for marker, category in [('failed to parse websocket event', 'parse_failure'),
                             ('timed out', 'timeout'), ('tls', 'tls_error'),
                             ('retry', 'retry'), ('closed', 'stream_closed')]:
        if marker in plain.lower():
            result['error_class'] = category
            break
    return result
