"""A connection that never opened is retried; anything after it is not.

Runs 19 and 23 aborted on ``WinError 10054`` at 0.07-0.08 s, before any HTTP status:
the request never reached the model, so a retry cannot duplicate model work. That
connect-phase retry is separate from the model-request retry and must never fire once
the connection (and therefore possibly the request) got through.
"""
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.runtime import deepseek_api


class ConnectRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {
            'DEEPSEEK_API_KEY': 'not-a-real-key', 'DEEPSEEK_MODEL': 'deepseek-chat',
            'DEEPSEEK_BASE_URL': 'http://127.0.0.1:%d' % self.closed_port(),
            'DEEPSEEK_ALLOW_CUSTOM_ENDPOINT': '1'})
        self.env.start()
        self.addCleanup(self.env.stop)

    @staticmethod
    def closed_port():
        probe = socket.socket()
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
        probe.close()
        return port

    def call(self, connect_retries, audit='audit'):
        return deepseek_api.call('prompt', {'type': 'object'}, 'deepseek-chat', timeout=20,
                                 audit_dir=self.root / audit,
                                 options={'retries': 0, 'connect_retries': connect_retries})

    def attempts(self, audit='audit'):
        import json
        return json.loads((self.root / audit / 'attempts.json').read_text(encoding='utf-8'))

    def test_a_connection_retry_is_recorded_and_bounded(self):
        with self.assertRaises(deepseek_api.ApiTransportError) as caught:
            self.call(connect_retries=1)
        self.assertEqual(caught.exception.code, 'model_connection_failed')
        ledger = self.attempts()
        self.assertEqual(len(ledger['attempts']), 2)
        self.assertTrue(ledger['attempts'][0].get('connect_retry'))
        self.assertFalse(ledger['attempts'][1].get('connect_retry'))
        self.assertEqual(ledger['connect_retries'], 1)

    def test_zero_connect_retries_keeps_the_old_single_attempt(self):
        with self.assertRaises(deepseek_api.ApiTransportError):
            self.call(connect_retries=0, audit='none')
        self.assertEqual(len(self.attempts('none')['attempts']), 1)

    def test_an_out_of_range_setting_is_a_config_error_before_any_request(self):
        with self.assertRaises(deepseek_api.ApiConfigError):
            self.call(connect_retries=5, audit='bad')

    def test_a_failure_after_connect_is_not_retried(self):
        # The transport connects, then the stream breaks: no connect retry may occur.
        class Broken(deepseek_api.ApiTransportError):
            pass
        calls = {'n': 0}
        real = deepseek_api._consume_stream

        def broken(*args, **kwargs):
            calls['n'] += 1
            raise deepseek_api.ApiTransportError('cut mid-stream', code='model_stream_incomplete')

        with patch.object(deepseek_api, '_consume_stream', broken), \
                patch.object(self, 'closed_port', return_value=0):
            # Use a live local server instead of the closed port for this case.
            server = FakeServer()
            self.addCleanup(server.stop)
            with patch.dict(os.environ, {'DEEPSEEK_BASE_URL': 'http://127.0.0.1:%d' % server.port}):
                with self.assertRaises(deepseek_api.ApiTransportError) as caught:
                    self.call(connect_retries=2, audit='mid')
        self.assertEqual(caught.exception.code, 'model_stream_incomplete')
        self.assertEqual(calls['n'], 1)
        self.assertEqual(len(self.attempts('mid')['attempts']), 1)


class FakeServer:
    """Minimal SSE endpoint returning a complete answer."""

    def __init__(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length', 0)))
                body = b'data: {"id":"x","choices":[{"delta":{"content":"{}"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


if __name__ == '__main__':
    unittest.main()
