"""Tests a LOCAL observation contract, not installed-CLI signal emission."""
import io
import json
from pathlib import Path
import unittest

from validation.planner_frame_observation import ProposedObserver, launch_gate, safe_unknown_log

ROOT = Path(__file__).resolve().parents[2]

def simulate(frames=(), retry=False, stdout=None):
    sink = io.StringIO()
    ticks = iter(i / 100 for i in range(1000))
    observer = ProposedObserver(sink, clock=lambda: next(ticks))
    observer.connect()
    observer.send()
    for kind, payload, forward in frames:
        observer.inbound(kind, payload, forward)
    if retry:
        observer.retry()
    if stdout:
        observer.stdout(stdout)
    observer.deadline()
    return [json.loads(line) for line in sink.getvalue().splitlines()]

def event(kind, forward=True, **extra):
    return ('text', json.dumps(dict(type=kind, **extra)).encode(), forward)

class FrameContractTests(unittest.TestCase):
    def test_no_frames_vs_control_frames(self):
        quiet = simulate()
        controls = simulate([('ping', b'private', True), ('pong', b'private', True)])
        self.assertFalse(any(e['stage']=='inbound_frame' for e in quiet))
        frames = [e for e in controls if e['stage']=='inbound_frame']
        self.assertEqual([e['frame_kind'] for e in frames], ['ping','pong'])
        self.assertEqual([e['byte_count'] for e in frames], [7,7])
        self.assertLess(frames[0]['monotonic_seconds'], frames[1]['monotonic_seconds'])

    def test_created_stall_keeps_remote_identity(self):
        records = simulate([event('response.created', response={'id':'resp_fixture'})])
        parsed = [e for e in records if e['stage']=='parsed_event']
        self.assertEqual(parsed[0]['response_id'], 'resp_fixture')
        self.assertEqual(parsed[0]['event_type'], 'response.created')
        self.assertEqual(records[-1]['stage'], 'watchdog_timeout')

    def test_business_event_without_completion(self):
        records = simulate([event('response.created'), event('response.output_text.delta', delta='private')])
        self.assertEqual([e['event_type'] for e in records if e['stage']=='parsed_event'],
                         ['response.created','response.output_text.delta'])
        self.assertNotIn('private', json.dumps(records))

    def test_parse_forward_and_stdout_are_distinct(self):
        records = simulate([event('response.created', forward=False)])
        self.assertTrue(any(e['stage']=='parsed_event' for e in records))
        self.assertFalse(any(e['stage'] in {'internal_forward','stdout_forward'} for e in records))

    def test_retry_reconnect_request_identity(self):
        records = simulate(retry=True)
        sends = [e for e in records if e['stage']=='send_complete']
        self.assertEqual([(e['connection'],e['request']) for e in sends], [(1,1),(2,2)])
        self.assertEqual(sum(e['stage']=='retry' for e in records), 1)

    def test_terminal_is_not_cli_terminal_or_process_exit(self):
        records = simulate([event('response.completed')], stdout='turn.completed')
        self.assertTrue(any(e.get('event_type')=='response.completed' for e in records))
        self.assertTrue(any(e.get('event_type')=='turn.completed' for e in records))
        self.assertEqual(records[-1]['stage'], 'watchdog_timeout')
        self.assertFalse(any(e['stage']=='process_exit' for e in records))

    def test_warmup_does_not_confirm_main_request(self):
        sink = io.StringIO()
        observer = ProposedObserver(sink)
        observer.connect(); observer.send(warmup=True)
        observer.inbound('text', b'{"type":"response.completed"}')
        observer.send(warmup=False); observer.deadline()
        rows = [json.loads(line) for line in sink.getvalue().splitlines()]
        completed = next(e for e in rows if e['stage']=='parsed_event')
        self.assertTrue(completed['warmup'])
        self.assertFalse(rows[-1]['warmup'])
        self.assertNotEqual(completed['request'], rows[-1]['request'])

    def test_no_sensitive_body_or_exception_persistence(self):
        secret = 'sensitive-fixture-value'
        records = simulate([('text', ('{"'+secret).encode(), True),
            event('response.failed', response={'id': 'sk-'+secret},
                  authorization=secret, cookie=secret, token=secret, headers={'private':secret})])
        self.assertNotIn(secret, json.dumps(records))
        self.assertTrue(any(e.get('error_class')=='invalid_json' for e in records))
        safe = safe_unknown_log('2026-10-26T00:00:00Z ERROR codex_api::endpoint::responses_websocket: '
                                'failed to parse websocket event data='+secret)
        self.assertEqual(safe, {'level':'ERROR', 'module':'codex_api::endpoint::responses_websocket',
                                'error_class':'parse_failure'})
        self.assertNotIn(secret, json.dumps(safe))

    def test_installed_source_explains_signal_loss(self):
        sources = json.loads((ROOT/'validation/planner-frame-gate/source-excerpts.json').read_text())
        by_path = {s['path']: '\n'.join(r['text'] for r in s['ranges']) for s in sources['sources']}
        pump = by_path['codex-api/src/endpoint/responses_websocket.rs']
        self.assertIn('Ok(Message::Pong(_)) => {}', pump)
        self.assertIn('inner.send(Message::Pong(payload)).await', pump)
        metrics = by_path['otel/src/events/session_telemetry.rs']
        self.assertIn('self.counter(WEBSOCKET_EVENT_COUNT_METRIC', metrics)
        self.assertIn('Message::Pong(_) => {\n                    return;', metrics)

    def test_prototype_does_not_open_real_call_gate(self):
        gate = launch_gate()
        self.assertFalse(gate['allowed'])
        self.assertIn('wire_frame_metadata', gate['missing_verified_signals'])
        self.assertIn('parse_event_identity', gate['missing_verified_signals'])
