"""Local subprocess probes only; no real model or chemistry execution."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

from creation_pipeline.runtime import model_call
from validation.planner_wait_stage_support import project, StderrProjection


class WaitStageTests(unittest.TestCase):
    def test_terminal_event_does_not_mean_process_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = 'import sys,time; sys.stdin.read(); print(\'{"type":"turn.completed"}\',flush=True); time.sleep(20)'
            with self.assertRaises(model_call.ModelExecutionError):
                model_call.run([sys.executable, '-c', code], 'input', root, 1, root/'audit', {})
            seen = json.loads((root/'audit/process.json').read_text())
            self.assertEqual(seen['status'], 'timed_out')
            self.assertEqual(seen['last_terminal_event_type'], 'turn.completed')
            self.assertLess(seen['first_terminal_event_seconds'], 1)
            self.assertIsNone(seen['returncode_before_cleanup'])
            self.assertTrue(seen['stream_threads_finished'])
            self.assertIn('stdin_closed_seconds', seen)

    def test_duplex_pipes_and_eof_do_not_deadlock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = ('import sys,threading; '
                    't=threading.Thread(target=lambda:sys.stderr.write("x"*200000+"\\n")); t.start(); '
                    'sys.stdout.write("y"*200000+"\\n"); sys.stdout.flush(); '
                    'data=sys.stdin.read(); t.join(); print(len(data))')
            result = model_call.run([sys.executable, '-c', code], 'p'*200000, root, 10, root/'audit', {})
            self.assertTrue(result.stdout.endswith('200000\n'))
            seen = json.loads((root/'audit/process.json').read_text())
            self.assertEqual(seen['returncode_before_cleanup'], 0)
            self.assertEqual(seen['supervision_status_before_cleanup'], 'exited')
            self.assertEqual(seen['io_errors'], [])

    def test_diagnostic_projection_drops_secrets_and_payloads(self):
        line = ('event.name="codex.api_request" duration_ms=200 attempt=2 '
                'http.response.status_code=503 endpoint="https://u:private@host/responses?token=private" '
                'auth.request_id="private" authorization="Bearer private" cookie="private" '
                'error.message="private attempt=private" user.email="private"')
        safe = project(line)
        self.assertNotIn('private', json.dumps(safe))
        self.assertEqual(safe['attempt'], 2)
        self.assertEqual(safe['endpoint_role'], 'responses')
        self.assertEqual(safe['http.response.status_code'], 503)
        self.assertEqual(len(safe['request_id_sha256']), 64)
        self.assertEqual(project('unknown password=private'), {'event': 'unclassified_line'})

    def test_filter_applies_before_capture_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = model_call.run([sys.executable, '-c',
                'import sys; sys.stdin.read(); print("secret=private",file=sys.stderr)'],
                '', root, 5, root/'audit', {}, stderr_filter=StderrProjection())
            self.assertNotIn('private', result.stderr)
            self.assertNotIn('private', (root/'audit/stderr.txt').read_text())
            self.assertEqual(json.loads(result.stderr)['event'], 'unclassified_line')

    def test_unread_stdin_remains_inside_watchdog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(model_call.ModelExecutionError):
                model_call.run([sys.executable, '-c', 'import time; time.sleep(20)'],
                               'p'*1000000, root, 1, root/'audit', {})
            seen = json.loads((root/'audit/process.json').read_text())
            self.assertEqual(seen['status'], 'timed_out')
            self.assertNotIn('stdin_sent_seconds', seen)
            self.assertTrue(seen['stream_threads_finished'])
            self.assertLess(seen['elapsed_seconds'], 5)

    def test_filter_failure_is_io_failure_without_raw_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def fail(_):
                raise ValueError('private')
            with self.assertRaises(model_call.ModelExecutionError):
                model_call.run([sys.executable, '-c',
                    'import sys,time; print("private",file=sys.stderr,flush=True); time.sleep(20)'],
                    '', root, 5, root/'audit', {}, stderr_filter=fail)
            seen = json.loads((root/'audit/process.json').read_text())
            self.assertEqual(seen['status'], 'io_failed')
            self.assertNotIn('private', (root/'audit/stderr.txt').read_text())
            self.assertEqual(seen['io_errors'], [{'channel': 'stderr', 'error': 'ValueError'}])

    def test_span_warmup_and_stream_kind_survive_projection(self):
        safe = project('model_client.stream_responses_websocket{websocket.warmup=false}: '
                       'event.name="codex.websocket_request" success="true" duration_ms=1')
        self.assertIs(safe['websocket.warmup'], False)
        self.assertTrue(safe['success'])
        safe = project('event.name="codex.sse_event" event.kind=response.completed')
        self.assertEqual(safe['kind'], 'response.completed')
