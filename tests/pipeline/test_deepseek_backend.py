"""Offline contract tests for the opt-in DeepSeek API structured backend.

Every test here is hermetic: a scripted loopback HTTP server stands in for the
provider, no credential is real, and no test reaches the official service. The
suite fixes the behaviour the migration depends on - completion markers, local
schema enforcement, failure classification, the total deadline, cancellation,
retry accounting and credential redaction - without spending a request.
"""
import contextlib
import http.server
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.runtime import deepseek_api, model_call, planner

MODEL = 'deepseek-flash'
SENTINEL_KEY = 'sk-sentinel-DO-NOT-LEAK-0123456789'
SCHEMA = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}, 'note': {'type': 'string'}},
          'required': ['ok', 'note'], 'additionalProperties': False}


# ---- scripted loopback provider ------------------------------------------------
class ScriptedHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length)
        self.server.requests.append({'path': self.path, 'headers': dict(self.headers),
                                     'body': body, 'at': time.monotonic()})
        script = self.server.pop_script()
        try:
            script(self)
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.server.aborted.append(time.monotonic())
        finally:
            self.close_connection = True

    def finish(self):
        self.server.closed.append(time.monotonic())
        with contextlib.suppress(Exception):
            super().finish()


class ScriptedServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self):
        super().__init__(('127.0.0.1', 0), ScriptedHandler)
        self.requests = []
        self.closed = []
        self.aborted = []
        self.scripts = []
        self._lock = threading.Lock()

    @property
    def base_url(self):
        return 'http://127.0.0.1:%d' % self.server_address[1]

    def push(self, script):
        with self._lock:
            self.scripts.append(script)

    def pop_script(self):
        with self._lock:
            if not self.scripts:
                return lambda handler: reply(handler, 500, {'error': {'message': 'no script'}})
            return self.scripts.pop(0)


def _write(handler, items):
    for item in items:
        if isinstance(item, tuple) and item[0] == 'sleep':
            time.sleep(item[1])
            continue
        handler.wfile.write(item.encode('utf-8') if isinstance(item, str) else item)
        handler.wfile.flush()


def reply(handler, status, payload, headers=None, leading=b''):
    raw = json.dumps(payload).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(raw) + len(leading)))
    handler.send_header('Connection', 'close')
    for name, value in (headers or {}).items():
        handler.send_header(name, value)
    handler.end_headers()
    handler.wfile.write(leading + raw)
    handler.wfile.flush()


def single(payload, status=200, headers=None, leading=b''):
    return lambda handler: reply(handler, status, payload, headers, leading)


def sse(items, status=200, headers=None):
    def script(handler):
        handler.send_response(status)
        handler.send_header('Content-Type', 'text/event-stream')
        handler.send_header('Connection', 'close')
        for name, value in (headers or {}).items():
            handler.send_header(name, value)
        handler.end_headers()
        _write(handler, items)
    return script


def sse_chunked(items, status=200):
    """Keep-alive chunked SSE: http.client keeps its socket instead of closing it.

    That is the mode in which a short per-read timeout used to poison the reader
    ("cannot read from timed out object"), so it is exercised explicitly.
    """
    def script(handler):
        handler.send_response(status)
        handler.send_header('Content-Type', 'text/event-stream')
        handler.send_header('Transfer-Encoding', 'chunked')
        handler.end_headers()
        for item in items:
            if isinstance(item, tuple) and item[0] == 'sleep':
                time.sleep(item[1])
                continue
            data = item.encode('utf-8') if isinstance(item, str) else item
            handler.wfile.write(('%x\r\n' % len(data)).encode() + data + b'\r\n')
            handler.wfile.flush()
        handler.wfile.write(b'0\r\n\r\n')
        handler.wfile.flush()
    return script


def data_line(payload):
    return 'data: %s\n\n' % json.dumps(payload)


def frames(content='', finish='stop', usage=None, request_id='chatcmpl-test-1', extra=()):
    """A documented stream: content deltas, terminal chunk, then ``data: [DONE]``."""
    out = []
    if content:
        step = max(1, len(content) // 2)
        for index in range(0, len(content), step):
            out.append(data_line({'id': request_id, 'object': 'chat.completion.chunk',
                                  'choices': [{'index': 0, 'delta': {'role': 'assistant',
                                                                     'content': content[index:index + step]}}]}))
    out.append(data_line({'id': request_id, 'object': 'chat.completion.chunk',
                          'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish}],
                          'usage': usage or {'prompt_tokens': 11, 'completion_tokens': 7,
                                             'total_tokens': 18}}))
    out.extend(extra)
    out.append('data: [DONE]\n\n')
    return out


def answer_body(content, finish='stop', request_id='chatcmpl-test-1'):
    return {'id': request_id, 'object': 'chat.completion', 'model': MODEL,
            'choices': [{'index': 0, 'finish_reason': finish,
                         'message': {'role': 'assistant', 'content': content}}],
            'usage': {'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 18}}


class DeepSeekCase(unittest.TestCase):
    """Base case: loopback provider, throw-away audit dir, no real ``.env``."""

    def setUp(self):
        self.server = ScriptedServer()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.tmp = tempfile.TemporaryDirectory(prefix='deepseek-offline-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {
            'DEEPSEEK_API_KEY': SENTINEL_KEY,
            'DEEPSEEK_BASE_URL': self.server.base_url,
            'DEEPSEEK_ALLOW_CUSTOM_ENDPOINT': '1',
            'DEEPSEEK_MODEL': MODEL,
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        # Never let a real repository `.env` influence a test.
        self.dotenv = patch.object(deepseek_api, 'ENV_FILE', self.root / 'absent.env')
        self.dotenv.start()
        self.addCleanup(self.dotenv.stop)

    def audit(self):
        return self.root / 'audit'

    def read(self, *parts):
        return json.loads(self.root.joinpath('audit', *parts).read_text(encoding='utf-8'))

    def files(self):
        return sorted(p.relative_to(self.audit()).as_posix()
                      for p in self.audit().rglob('*') if p.is_file())

    def call(self, *, timeout=10, options=None, model=MODEL, schema=SCHEMA, prompt='q',
             reasoning=None):
        return model_call.call(prompt, schema, model, timeout=timeout, audit_dir=self.audit(),
                               backend='deepseek_api', api_options=options, reasoning=reasoning)

    def record_connections(self):
        created = []
        original = deepseek_api._connection

        def recording(settings, timeout):
            connection = original(settings, timeout)
            created.append(connection)
            return connection

        patcher = patch.object(deepseek_api, '_connection', recording)
        patcher.start()
        self.addCleanup(patcher.stop)
        return created


class CompletionTests(DeepSeekCase):
    def test_stream_completion_returns_answer_receipt_and_ledger(self):
        body = json.dumps({'ok': True, 'note': 'two words'})
        self.server.push(sse(frames(body)))
        answer, receipt = self.call()

        self.assertEqual(answer, {'ok': True, 'note': 'two words'})
        self.assertEqual(receipt['backend'], 'deepseek_api')
        self.assertEqual(receipt['provider'], 'deepseek')
        self.assertEqual(receipt['model'], MODEL)
        self.assertEqual(receipt['request_count'], 1)
        self.assertEqual(receipt['completion']['finish_reason'], 'stop')
        self.assertTrue(receipt['completion']['done_marker'])
        self.assertTrue(receipt['completion']['schema_validated'])
        self.assertEqual(receipt['usage']['total_tokens'], 18)
        self.assertEqual(receipt['request_id'], {'value': 'chatcmpl-test-1', 'source': 'body:id'})
        self.assertEqual(receipt['endpoint']['kind'], 'custom')  # loopback is not the official host
        self.assertEqual(receipt['request_params']['response_format'], 'json_object')
        self.assertEqual(receipt['request_params']['max_tokens'], 65536)
        self.assertEqual(receipt['retry_policy']['configured'], 0)

        sent = json.loads(self.server.requests[0]['body'])
        self.assertEqual(sent['response_format'], {'type': 'json_object'})
        self.assertTrue(sent['stream'])
        self.assertEqual(sent['stream_options'], {'include_usage': True})
        self.assertEqual(sent['messages'][1]['content'], 'q')
        self.assertIn('JSON Schema', sent['messages'][0]['content'])
        self.assertIn('"additionalProperties": false', sent['messages'][0]['content'])
        self.assertEqual(self.server.requests[0]['headers']['Authorization'],
                         'Bearer ' + SENTINEL_KEY)

        self.assertEqual(self.files(), ['attempts.json', 'request.json', 'response.json',
                                        'schema.json', 'stream.json'])
        observation = self.read('request.json')
        self.assertEqual(observation['status'], 'completed')
        self.assertEqual(observation['request_count'], 1)
        self.assertEqual(observation['request_params']['model'], MODEL)
        self.assertEqual(len(observation['prompt_sha256']), 64)
        self.assertEqual(len(observation['schema_sha256']), 64)
        # The prompt body is not archived, only its fingerprint.
        self.assertNotIn('"q"', (self.audit() / 'request.json').read_text(encoding='utf-8'))

    def test_single_response_with_keepalive_blank_lines(self):
        payload = answer_body(json.dumps({'ok': False, 'note': 'non stream'}))
        self.server.push(lambda handler: reply(handler, 200, payload, leading=b'\r\n\r\n'))
        answer, receipt = self.call(options={'stream': False})
        self.assertEqual(answer, {'ok': False, 'note': 'non stream'})
        self.assertEqual(receipt['completion']['finish_reason'], 'stop')
        self.assertFalse(receipt['request_params']['stream'])
        self.assertEqual(self.server.requests[0]['path'], '/chat/completions')
        self.assertNotIn('stream_options', json.loads(self.server.requests[0]['body']))

    def test_keepalive_comments_are_recorded_but_are_not_progress(self):
        self.server.push(sse([': keep-alive\n\n'] * 3
                             + frames(json.dumps({'ok': True, 'note': 'k'}))))
        answer, receipt = self.call()
        self.assertEqual(answer['note'], 'k')
        self.assertGreaterEqual(receipt['completion']['keepalives'], 3)

    def test_reasoning_content_never_becomes_the_answer(self):
        reasoning = {'id': 'r', 'choices': [{'index': 0,
                                             'delta': {'reasoning_content': 'thinking...'}}]}
        self.server.push(sse([data_line(reasoning)]
                             + frames(json.dumps({'ok': True, 'note': 'x'}))))
        answer, receipt = self.call(reasoning='medium')
        self.assertEqual(answer, {'ok': True, 'note': 'x'})
        self.assertTrue(receipt['completion']['schema_validated'])
        self.assertGreater(receipt['completion']['chunks'], 1)

    def test_requested_effort_is_recorded_with_explicit_mapping(self):
        self.server.push(sse(frames(json.dumps({'ok': True, 'note': 'm'}))))
        _, receipt = self.call(reasoning='medium')
        self.assertEqual(receipt['request_params']['reasoning_effort_requested'], 'medium')
        self.assertEqual(receipt['request_params']['reasoning_effort_sent'], 'high')
        self.assertIn('not claimed to be equivalent', receipt['mapping']['reasoning_effort'])
        sent = json.loads(self.server.requests[0]['body'])
        self.assertEqual(sent['reasoning_effort'], 'high')
        self.assertEqual(sent['thinking'], {'type': 'enabled'})

    def test_disabled_effort_disables_thinking(self):
        self.server.push(sse(frames(json.dumps({'ok': True, 'note': 'n'}))))
        _, receipt = self.call(reasoning='none')
        sent = json.loads(self.server.requests[0]['body'])
        self.assertEqual(sent['thinking'], {'type': 'disabled'})
        self.assertNotIn('reasoning_effort', sent)
        self.assertEqual(receipt['request_params']['reasoning_effort_sent'], 'none')

    def test_service_tier_is_recorded_and_never_sent(self):
        self.server.push(sse(frames(json.dumps({'ok': True, 'note': 't'}))))
        _, receipt = self.call()
        self.assertIsNone(receipt['request_params']['service_tier_requested'])
        self.assertIn('not supported', receipt['mapping']['service_tier'])
        self.assertNotIn('service_tier', json.loads(self.server.requests[0]['body']))

    def test_non_stream_completion_is_also_schema_checked(self):
        self.server.push(single(answer_body(json.dumps({'ok': True}))))
        with self.assertRaises(model_call.ModelOutputInvalid):
            self.call(options={'stream': False})


class SchemaEnforcementTests(DeepSeekCase):
    def test_valid_json_that_violates_the_schema_is_rejected(self):
        self.server.push(sse(frames(json.dumps({'ok': True}))))  # missing required note
        with self.assertRaises(model_call.ModelOutputInvalid) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_schema_mismatch')
        self.assertIn('note', str(caught.exception))
        self.assertEqual(self.read('error.json')['error_class'], 'model_schema_mismatch')

    def test_type_violation_is_rejected(self):
        self.server.push(sse(frames(json.dumps({'ok': 'yes', 'note': 'n'}))))
        with self.assertRaises(model_call.ModelOutputInvalid) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_schema_mismatch')

    def test_non_json_content_is_rejected(self):
        self.server.push(sse(frames('this is not json')))
        with self.assertRaises(model_call.ModelOutputInvalid) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_output_invalid')

    def test_json_array_is_not_an_object_contract(self):
        self.server.push(sse(frames('[1, 2]')))
        with self.assertRaises(model_call.ModelOutputInvalid):
            self.call()

    def test_empty_content_is_rejected(self):
        self.server.push(sse(frames('')))
        with self.assertRaises(model_call.ModelOutputInvalid) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_output_empty')


class IncompleteOutputTests(DeepSeekCase):
    def test_truncated_answer_is_never_accepted(self):
        self.server.push(sse(frames('{"ok": tr', finish='length')))
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_output_truncated')
        self.assertEqual(caught.exception.kind, 'model_transport')
        self.assertEqual(self.read('error.json')['error_class'], 'model_output_truncated')

    def test_stream_without_done_marker_is_rejected(self):
        items = frames(json.dumps({'ok': True, 'note': 'n'}))[:-1]  # drop data: [DONE]
        self.server.push(sse(items))
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_stream_interrupted')

    def test_finish_reason_without_done_marker_is_not_success(self):
        item = {'id': 'x', 'choices': [{'index': 0,
                                        'delta': {'content': '{"ok":true,"note":"n"}'},
                                        'finish_reason': 'stop'}]}
        self.server.push(sse([data_line(item)]))
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_stream_interrupted')

    def test_done_marker_without_finish_reason_is_not_success(self):
        item = {'id': 'x', 'choices': [{'index': 0,
                                        'delta': {'content': '{"ok":true,"note":"n"}'}}]}
        self.server.push(sse([data_line(item), 'data: [DONE]\n\n']))
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_stream_interrupted')

    def test_malformed_frame_mid_stream_is_rejected(self):
        self.server.push(sse(['data: {"broken": \n\n', 'data: [DONE]\n\n']))
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_stream_interrupted')

    def test_server_interrupted_finish_reason_is_rejected(self):
        self.server.push(sse(frames('{"ok":true,"note":"n"}',
                                    finish='insufficient_system_resource')))
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_stream_interrupted')

    def test_connection_dropped_mid_stream_is_rejected(self):
        def script(handler):
            handler.send_response(200)
            handler.send_header('Content-Type', 'text/event-stream')
            handler.end_headers()
            handler.wfile.write(data_line({'id': 'x', 'choices': [
                {'index': 0, 'delta': {'content': '{"ok":'}}]}).encode())
            handler.wfile.flush()
            handler.close_connection = True
            with contextlib.suppress(OSError):
                handler.connection.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(OSError):
                handler.connection.close()

        self.server.push(script)
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_stream_interrupted')

    def test_streamed_error_frame_is_classified(self):
        self.server.push(sse([data_line({'error': {'message': 'upstream failed',
                                                  'type': 'server_error', 'code': 503}})]))
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_server_error')

    def test_tool_calls_are_rejected_by_the_tool_free_contract(self):
        item = {'id': 'x', 'choices': [{'index': 0, 'finish_reason': 'tool_calls',
                                        'message': {'role': 'assistant', 'content': None,
                                                    'tool_calls': [{'id': 't', 'type': 'function',
                                                                    'function': {'name': 'f',
                                                                                 'arguments': '{}'}}]}}]}
        self.server.push(single(item))
        with self.assertRaises(model_call.ModelOutputInvalid):
            self.call(options={'stream': False})


class FailureClassificationTests(DeepSeekCase):
    def test_authentication_failure_is_not_retried(self):
        self.server.push(single({'error': {'message': 'bad key',
                                           'type': 'authentication_error',
                                           'code': 'invalid_api_key'}}, status=401))
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call(options={'retries': 2})
        self.assertEqual(caught.exception.code, 'model_auth_failed')
        self.assertEqual(len(self.server.requests), 1)
        self.assertEqual(self.read('error.json')['request_count'], 1)

    def test_insufficient_balance_is_classified(self):
        self.server.push(single({'error': {'message': 'no balance'}}, status=402))
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_insufficient_balance')

    def test_rate_limit_is_classified_and_retryable_when_configured(self):
        self.server.push(single({'error': {'message': 'too many'}}, status=429))
        self.server.push(sse(frames(json.dumps({'ok': True, 'note': 'after retry'}))))
        answer, receipt = self.call(options={'retries': 1})
        self.assertEqual(answer['note'], 'after retry')
        self.assertEqual(len(self.server.requests), 2)
        self.assertEqual(receipt['request_count'], 2)
        self.assertEqual(receipt['retry_policy']['configured'], 1)
        ledger = self.read('attempts.json')
        self.assertEqual([a['status'] for a in ledger['attempts']], ['failed', 'completed'])
        self.assertEqual(ledger['sdk_implicit_retries'], 'none (no SDK used)')
        self.assertTrue(ledger['retry_policy']['counted_in_total_deadline'])

    def test_rate_limit_without_retries_sends_exactly_one_request(self):
        self.server.push(single({'error': {'message': 'too many'}}, status=429))
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_rate_limited')
        self.assertEqual(len(self.server.requests), 1)

    def test_server_error_is_classified(self):
        self.server.push(single({'error': {'message': 'overloaded'}}, status=503))
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 'model_server_error')

    def test_connection_failure_is_classified(self):
        probe = socket.socket()
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
        probe.close()  # nothing listens here any more
        with patch.dict(os.environ, {'DEEPSEEK_BASE_URL': 'http://127.0.0.1:%d' % port}):
            with self.assertRaises(model_call.ModelExecutionError) as caught:
                self.call(timeout=10)
        self.assertEqual(caught.exception.code, 'model_connection_failed')
        self.assertEqual(self.read('error.json')['error_class'], 'model_connection_failed')

    def test_unknown_model_name_is_not_guessed(self):
        with patch.dict(os.environ, {'DEEPSEEK_MODEL': ''}):
            with self.assertRaises(model_call.ModelConfigError) as caught:
                self.call(model=None)
        self.assertEqual(caught.exception.code, 'model_config_invalid')
        self.assertEqual(self.server.requests, [])
        self.assertFalse(self.read('request.json')['request_sent'])

    def test_missing_credential_sends_no_request(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': ''}):
            with self.assertRaises(model_call.ModelConfigError) as caught:
                self.call()
        self.assertIn('DEEPSEEK_API_KEY', str(caught.exception))
        self.assertEqual(self.server.requests, [])

    def test_third_party_endpoint_is_refused_unless_declared(self):
        with patch.dict(os.environ, {'DEEPSEEK_ALLOW_CUSTOM_ENDPOINT': '0'}):
            with self.assertRaises(model_call.ModelConfigError) as caught:
                self.call()
        self.assertIn('official', str(caught.exception).lower())
        self.assertEqual(self.server.requests, [])

    def test_unknown_backend_never_falls_back(self):
        with self.assertRaises(model_call.ModelConfigError):
            model_call.call('q', SCHEMA, MODEL, timeout=5, backend='openai_api')


class DeadlineAndCancellationTests(DeepSeekCase):
    def test_total_deadline_bounds_a_silent_stream(self):
        def script(handler):
            handler.send_response(200)
            handler.send_header('Content-Type', 'text/event-stream')
            handler.end_headers()
            for _ in range(20):
                try:
                    handler.wfile.write(b': keep-alive\n\n')
                    handler.wfile.flush()
                except OSError:
                    return
                time.sleep(0.2)

        self.server.push(script)
        connections = self.record_connections()
        started = time.monotonic()
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call(timeout=2)
        elapsed = time.monotonic() - started
        self.assertEqual(caught.exception.code, 'model_timeout')
        self.assertLess(elapsed, 8)
        self.assertGreaterEqual(elapsed, 1.5)
        self.assertEqual(self.read('error.json')['error_class'], 'model_timeout')
        self.assertTrue(connections)
        self.assertIsNone(connections[0].sock, 'the connection must be released')

    def test_impossible_deadline_sends_nothing(self):
        with self.assertRaises(model_call.ModelConfigError):
            self.call(timeout=0)
        self.assertEqual(self.server.requests, [])
        self.assertFalse(self.read('request.json')['request_sent'])

    def test_silent_gap_is_not_a_read_failure_on_a_keep_alive_stream(self):
        # Regression: a short per-read timeout used to fire on a healthy slow stream,
        # and the next read on the same HTTPResponse raised
        # "OSError: cannot read from timed out object", reported as a broken link.
        self.server.push(sse_chunked([data_line({'id': 'x', 'choices': [{'index': 0,
                                                                       'delta': {'content': '{"ok":'}}]}),
                                      ('sleep', 6.0)]
                                     + frames('true,"note":"slow"}')))
        answer, receipt = self.call(timeout=30)
        self.assertEqual(answer, {'ok': True, 'note': 'slow'})
        self.assertEqual(receipt['completion']['finish_reason'], 'stop')

    def test_silent_gap_is_tolerated_when_the_server_closes_the_connection(self):
        # Same gap with "Connection: close": http.client drops connection.sock during
        # getresponse(), so the deadline must be armed on the socket captured earlier.
        self.server.push(sse([data_line({'id': 'x', 'choices': [{'index': 0,
                                                               'delta': {'content': '{"ok":'}}]}),
                              ('sleep', 6.0)] + frames('true,"note":"slow"}')))
        answer, _ = self.call(timeout=30)
        self.assertEqual(answer, {'ok': True, 'note': 'slow'})

    def test_keep_alive_stream_still_honours_the_total_deadline(self):
        def script(handler):
            handler.send_response(200)
            handler.send_header('Content-Type', 'text/event-stream')
            handler.send_header('Transfer-Encoding', 'chunked')
            handler.end_headers()
            for _ in range(5):
                with contextlib.suppress(OSError):
                    handler.wfile.write(b'2\r\n:\n\r\n')   # one SSE keep-alive comment
                    handler.wfile.flush()
                time.sleep(1.0)
            with contextlib.suppress(OSError):
                handler.wfile.write(b'0\r\n\r\n')
                handler.wfile.flush()

        self.server.push(script)
        started = time.monotonic()
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call(timeout=2)
        self.assertEqual(caught.exception.code, 'model_timeout')
        self.assertLess(time.monotonic() - started, 8)
        attempt = self.read('attempts.json')['attempts'][-1]
        self.assertEqual(attempt['error_class'], 'model_timeout')
        self.assertEqual(attempt['detail']['phase'], 'stream_read')

    def test_reader_failure_keeps_the_exception_and_received_bytes(self):
        class _Fake:
            def read1(self, n=-1):
                raise ConnectionResetError(10054, 'reset by peer')

        reader = deepseek_api._Reader(_Fake(), None, time.monotonic() + 30, None)
        with self.assertRaises(deepseek_api.ApiTransportError) as caught:
            reader._fill()
        self.assertEqual(caught.exception.code, 'model_stream_interrupted')
        self.assertIn('ConnectionResetError', str(caught.exception))
        self.assertIn('reset by peer', str(caught.exception))
        self.assertEqual(caught.exception.detail['bytes_received'], 0)
        self.assertEqual(caught.exception.detail['errno'], 10054)

    def test_a_read_timeout_is_a_deadline_verdict_and_is_never_retried(self):
        calls = {'n': 0}

        class _Slow:
            def read1(self, n=-1):
                calls['n'] += 1
                raise TimeoutError('timed out')

        reader = deepseek_api._Reader(_Slow(), None, time.monotonic() + 30, None)
        with self.assertRaises(deepseek_api.ApiTransportError) as caught:
            reader._fill()
        self.assertEqual(caught.exception.code, 'model_timeout')
        self.assertEqual(caught.exception.detail['phase'], 'stream_read')
        self.assertEqual(calls['n'], 1)  # the poisoned reader is never read again

    def test_total_deadline_bounds_a_server_that_never_sends_headers(self):
        def script(handler):
            # Accept the request and then stay silent: the client must not wait for
            # headers beyond the total deadline.
            time.sleep(10)

        self.server.push(script)
        connections = self.record_connections()
        started = time.monotonic()
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call(timeout=2)
        elapsed = time.monotonic() - started
        self.assertEqual(caught.exception.code, 'model_timeout')
        self.assertLess(elapsed, 6)
        self.assertGreaterEqual(elapsed, 1.5)
        self.assertTrue(connections)
        self.assertIsNone(connections[0].sock, 'the connection must be released')

    def test_dns_resolution_is_bounded_by_the_total_deadline(self):
        original = socket.getaddrinfo

        def slow_resolve(host, port, *args, **kwargs):
            time.sleep(10)
            return original(host, port, *args, **kwargs)

        started = time.monotonic()
        with patch.object(socket, 'getaddrinfo', slow_resolve):
            with self.assertRaises(model_call.ModelExecutionError) as caught:
                self.call(timeout=1)
        elapsed = time.monotonic() - started
        self.assertEqual(caught.exception.code, 'model_timeout')
        self.assertEqual(caught.exception.detail.get('phase'), 'dns')
        self.assertLess(elapsed, 5)
        self.assertEqual(self.server.requests, [], 'no request may be sent')

    def test_every_attempt_shares_one_deadline(self):
        # Two retries of a silent stream must not double the budget.
        def silent(handler):
            handler.send_response(200)
            handler.send_header('Content-Type', 'text/event-stream')
            handler.end_headers()
            time.sleep(10)

        for _ in range(3):
            self.server.push(silent)
        started = time.monotonic()
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call(timeout=2, options={'retries': 3})
        elapsed = time.monotonic() - started
        self.assertIn(caught.exception.code, {'model_timeout', 'model_stream_interrupted'})
        self.assertLess(elapsed, 8)
        ledger = self.read('error.json')
        self.assertGreaterEqual(ledger['request_count'], 1)
        self.assertLessEqual(elapsed, 2 + 6)

    def test_cancellation_propagates_and_releases_the_connection(self):
        self.server.push(sse(frames(json.dumps({'ok': True, 'note': 'c'}))))
        connections = self.record_connections()
        original = deepseek_api._Reader.readline
        calls = {'n': 0}

        def interrupt(reader):
            calls['n'] += 1
            if calls['n'] == 2:
                raise KeyboardInterrupt()
            return original(reader)

        with patch.object(deepseek_api._Reader, 'readline', interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.call(timeout=10)
        self.assertTrue(connections)
        self.assertIsNone(connections[0].sock, 'the connection must be released')


class RedactionTests(DeepSeekCase):
    def _assert_no_secret(self):
        for path in self.audit().rglob('*'):
            if path.is_file():
                text = path.read_text(encoding='utf-8', errors='replace')
                self.assertNotIn(SENTINEL_KEY, text, 'credential leaked into ' + path.name)

    def test_credential_never_reaches_audit_or_errors(self):
        self.server.push(single({'error': {'message': 'bad key ' + SENTINEL_KEY}}, status=401))
        with self.assertRaises(model_call.ModelExecutionError) as caught:
            self.call()
        self.assertNotIn(SENTINEL_KEY, str(caught.exception))
        self._assert_no_secret()

    def test_credential_never_reaches_a_success_receipt(self):
        self.server.push(sse(frames(json.dumps({'ok': True, 'note': 'ok'}))))
        _, receipt = self.call()
        self.assertNotIn(SENTINEL_KEY, json.dumps(receipt))
        self._assert_no_secret()

    def test_receipt_contains_no_prompt_text(self):
        self.server.push(sse(frames(json.dumps({'ok': True, 'note': 'p'}))))
        prompt = 'SECRET-PROMPT-BODY-1234'
        _, receipt = model_call.call(prompt, SCHEMA, MODEL, timeout=10, audit_dir=self.audit(),
                                     backend='deepseek_api')
        self.assertNotIn(prompt, json.dumps(receipt))


def minimal_planner_answer(action='read', requested=('tool.py',)):
    """A PLAN_SCHEMA-valid envelope; the planner behaviour under test is routing."""
    plan = {
        'entrypoint': ['python', 'tool.py'], 'script': 'tool.py',
        'base_image': 'python:3.11-slim', 'platform': 'linux/amd64',
        'language': 'python', 'language_version': '3.11',
        'source_files': ['tool.py'], 'dependencies': [],
        'steps': [{'command': 'true', 'purpose': 'no-op', 'evidence': 'test'}],
        'build_layout': {'dependency_files': [], 'prefix_steps': 0, 'reason': 'test'},
        'environment': [], 'resources': [], 'file_io': False,
        'output_contract': 'stdout', 'runtime_network': False, 'network_reason': '',
        'choices': [{'choice': 'base image', 'evidence': 'test', 'certainty': 'declared'}],
        'unresolved': [], 'unverified_behavior': [],
        'acceptance_json': '{"purposes": []}', 'generated_files': [], 'tests': [],
        'resource_assessment': {'status': 'unknown', 'source_path': '', 'source_quote': '',
                                'memory_bytes': 0, 'cpus': 0},
    }
    return {'action': action, 'requested_files': list(requested), 'reason': 'need the source',
            'plan': plan}


class BudgetGuardTests(DeepSeekCase):
    def _source(self):
        root = self.root / 'source'
        root.mkdir(exist_ok=True)
        (root / 'tool.py').write_text('def run(x):\n    return x + 1\n', encoding='utf-8')
        return root

    def test_caller_budget_guard_stops_before_any_request(self):
        opts = planner.options({'api_model': MODEL, 'backend': 'deepseek_api',
                                'api_max_output_tokens': 1024})
        guard_calls = {'n': 0}

        def guard():
            guard_calls['n'] += 1
            raise planner.BudgetExceeded('Explicit model call budget exhausted')

        with self.assertRaises(planner.BudgetExceeded):
            planner.plan(self._source(), {'constraints': []}, self.root / 'plan-audit',
                         opts, None, call_guard=guard)
        self.assertEqual(guard_calls['n'], 1)
        self.assertEqual(self.server.requests, [])

    def test_planner_routes_through_the_configured_api_backend(self):
        import jsonschema
        answer = minimal_planner_answer()
        jsonschema.validate(answer, planner.PLAN_SCHEMA)  # fixture guard against schema drift
        opts = planner.options({'model': 'native-codex-model', 'api_model': MODEL,
                                'backend': 'deepseek_api', 'api_max_output_tokens': 1024,
                                'max_read_rounds': 1})
        self.server.push(sse(frames(json.dumps(answer))))
        with self.assertRaises(planner.PlanningError):
            # One valid "read" step is followed by an exhausted round budget, which
            # is deterministic and needs no second request.
            planner.plan(self._source(), {'constraints': []}, self.root / 'plan-audit-b',
                         opts, None)
        self.assertEqual(len(self.server.requests), 1)
        sent = json.loads(self.server.requests[0]['body'])
        self.assertEqual(sent['model'], MODEL)
        # The native Agent model identity must never be sent to the API provider.
        self.assertNotIn('native-codex-model', self.server.requests[0]['body'].decode())
        self.assertEqual(sent['max_tokens'], 1024)
        audit = self.root / 'plan-audit-b' / 'model-0'
        self.assertEqual(json.loads((audit / 'request.json').read_text(
            encoding='utf-8'))['backend'], 'deepseek_api')
        self.assertTrue((audit / 'attempts.json').is_file())
        self.assertNotIn(SENTINEL_KEY, (audit / 'request.json').read_text(encoding='utf-8'))


class ConfigurationTests(DeepSeekCase):
    def test_options_default_to_the_cli_backend(self):
        self.assertEqual(planner.options({'model': 'm'})['backend'], 'codex_cli')

    def test_backend_model_never_crosses_providers(self):
        deepseek = planner.options({'model': 'native-codex-model', 'api_model': MODEL,
                                    'backend': 'deepseek_api'})
        self.assertEqual(planner.backend_model(deepseek), MODEL)
        cli = planner.options({'model': 'native-codex-model', 'backend': 'codex_cli'})
        self.assertEqual(planner.backend_model(cli), 'native-codex-model')
        # An unset API model stays unset so the provider module reads the operator's
        # own configuration instead of borrowing the Codex model name.
        unset = planner.options({'model': 'native-codex-model', 'backend': 'deepseek_api'})
        self.assertIsNone(planner.backend_model(unset))

    def test_cli_backend_ignores_the_api_model(self):
        opts = planner.options({'model': 'native-codex-model', 'api_model': MODEL})
        self.assertEqual(planner.backend_model(opts), 'native-codex-model')

    def test_invalid_api_model_is_rejected(self):
        with self.assertRaises(planner.PlanningError):
            planner.options({'api_model': 'model with spaces'})

    def test_invalid_backend_is_rejected_before_use(self):
        with self.assertRaises(planner.PlanningError):
            planner.options({'backend': 'ollama'})

    def test_api_parameters_are_validated(self):
        for bad in ({'api_retries': -1}, {'api_retries': 9},
                    {'api_max_output_tokens': 0}, {'api_max_output_tokens': 500000},
                    {'api_stream': 'yes'}):
            with self.assertRaises(planner.PlanningError, msg=repr(bad)):
                planner.options(bad)

    def test_dotenv_file_is_read_without_being_exported(self):
        env_file = self.root / '.env'
        env_file.write_text('# comment\nexport DEEPSEEK_API_KEY="from-file"\n'
                            'DEEPSEEK_MODEL=model-from-file\n'
                            'DEEPSEEK_FILE_ONLY_SENTINEL=value\n', encoding='utf-8')
        values = deepseek_api.read_env_file(env_file)
        self.assertEqual(values['DEEPSEEK_API_KEY'], 'from-file')
        self.assertEqual(values['DEEPSEEK_MODEL'], 'model-from-file')
        # Reading the file must not mutate the process environment.
        self.assertNotIn('DEEPSEEK_FILE_ONLY_SENTINEL', os.environ)
        with patch.object(deepseek_api, 'ENV_FILE', env_file), \
                patch.dict(os.environ, {'DEEPSEEK_API_KEY': '', 'DEEPSEEK_MODEL': ''}):
            settings = deepseek_api.resolve(None, timeout=5, options={})
        self.assertEqual(settings.api_key, 'from-file')
        self.assertEqual(settings.model, 'model-from-file')

    def test_official_endpoint_is_recognised(self):
        self.assertTrue(deepseek_api.is_official('https', 'api.deepseek.com', None))
        self.assertFalse(deepseek_api.is_official('http', 'api.deepseek.com', None))
        self.assertFalse(deepseek_api.is_official('https', 'api.example.com', None))

    def test_credentials_embedded_in_the_url_are_refused(self):
        with patch.dict(os.environ,
                        {'DEEPSEEK_BASE_URL': 'https://user:pw@api.deepseek.com'}):
            with self.assertRaises(model_call.ModelConfigError):
                self.call()
        self.assertEqual(self.server.requests, [])

    def test_default_anthropic_format_url_is_not_the_chat_endpoint(self):
        # The Anthropic-format base URL is documented too, but this backend speaks the
        # OpenAI-compatible format; the configured base URL must be that one.
        with patch.dict(os.environ, {'DEEPSEEK_BASE_URL': self.server.base_url + '/anthropic'}):
            self.server.push(sse(frames(json.dumps({'ok': True, 'note': 'p'}))))
            self.call()
        self.assertEqual(self.server.requests[0]['path'], '/anthropic/chat/completions')


if __name__ == '__main__':
    unittest.main()
