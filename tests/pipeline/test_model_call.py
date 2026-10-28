"""Model transport mechanisms; Python child processes are not business validation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from creation_pipeline.runtime import model_call


class ModelTransportTests(unittest.TestCase):
    def test_disable_integrations_without_discarding_provider_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'config.toml').write_text('model="configured"\nmodel_reasoning_effort="low"\n'
                'model_provider="custom"\n[mcp_servers.local_tool]\ncommand="unused"\n'
                '[mcp_servers.local_tool.env]\nAPI_KEY="do-not-copy"\n', encoding='utf-8')
            with patch.dict(os.environ, CODEX_HOME=tmp):
                args, settings = model_call.isolated_options()
            self.assertNotIn('--ignore-user-config', args)
            self.assertIn('mcp_servers.local_tool.enabled=false', args)
            self.assertIn('notify=[]', args)  # legacy_notify runs even when hooks are disabled
            self.assertIn('suppress_unstable_features_warning=true',args)
            self.assertEqual(settings['model_provider'], 'custom')
            self.assertNotIn('do-not-copy', str((args, settings)))
            for feature in ('apps', 'plugins', 'hooks', 'multi_agent', 'shell_tool'):
                self.assertIn(feature, args)

    def test_process_records_input_events_exit_and_redacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            code='import sys,json; text=sys.stdin.read(); print(json.dumps({"type":"turn.started"})); print("password=privatevalue",file=sys.stderr)'
            p=model_call.run([sys.executable,'-c',code], 'input', root, 10, root/'audit', {})
            self.assertEqual(p.returncode, 0)
            observation=json.loads((root/'audit/process.json').read_text())
            self.assertEqual(observation['status'], 'exited')
            self.assertTrue(observation['stream_threads_finished'])
            self.assertIn('stdin_sent_seconds',observation)
            self.assertEqual(json.loads((root/'audit/events.json').read_text())[0]['type'],'turn.started')
            self.assertNotIn('privatevalue',(root/'audit/stderr.txt').read_text())

    def test_timeout_keeps_started_events_and_reaps_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            code='import time; print(\'{"type":"turn.started"}\',flush=True); time.sleep(30)'
            with self.assertRaises(model_call.ModelExecutionError):
                model_call.run([sys.executable,'-c',code], '', root, 1, root/'audit', {})
            observation=json.loads((root/'audit/timeout.json').read_text())
            self.assertEqual(observation['status'],'timed_out')
            self.assertIsNotNone(observation['returncode'])
            self.assertTrue(observation['stream_threads_finished'])
            self.assertIn('turn.started',(root/'audit/stdout.txt').read_text())

    def test_start_failure_is_durable_transport_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(model_call.ModelExecutionError):
                model_call.run([str(root / 'missing-executable')], '', root, 5, root / 'audit', {})
            observed = json.loads((root / 'audit/process.json').read_text())
            self.assertEqual(observed['status'], 'start_failed')

    def test_audit_reader_failure_cannot_return_partial_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = Path.open
            def fail_stdout(path, *args, **kwargs):
                if path.name == 'stdout.txt':
                    raise OSError('injected audit write failure')
                return original(path, *args, **kwargs)
            with patch.object(Path, 'open', fail_stdout), self.assertRaises(model_call.ModelExecutionError):
                model_call.run([sys.executable, '-c', 'import sys; sys.stdin.read(); print("ok")'],
                               '', root, 5, root / 'audit', {})
            observed = json.loads((root / 'audit/process.json').read_text())
            self.assertEqual(observed['status'], 'io_failed')
            self.assertTrue(observed['stream_threads_finished'])
            self.assertIn('stdout', [e['channel'] for e in observed['io_errors']])

    def test_parent_exit_cleans_descendants_holding_pipes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = 'import subprocess,sys; sys.stdin.read(); subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"]); print("parent done")'
            result = model_call.run([sys.executable, '-c', code], '', root, 5, root / 'audit', {})
            self.assertEqual(result.returncode, 0)
            observed = json.loads((root / 'audit/process.json').read_text())
            self.assertTrue(observed['stream_threads_finished'])
            self.assertLess(observed['elapsed_seconds'], 5)

    def test_cancellation_is_recorded_and_reaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = subprocess.Popen.wait
            first = True
            def interrupt(proc, *args, **kwargs):
                nonlocal first
                if first:
                    first = False
                    raise KeyboardInterrupt()
                return original(proc, *args, **kwargs)
            with patch.object(subprocess.Popen, 'wait', interrupt), self.assertRaises(KeyboardInterrupt):
                model_call.run([sys.executable, '-c', 'import sys,time; sys.stdin.read(); time.sleep(30)'],
                               '', root, 5, root / 'audit', {})
            observed = json.loads((root / 'audit/process.json').read_text())
            self.assertEqual(observed['status'], 'cancelled')
            self.assertIsNotNone(observed['returncode'])
            self.assertTrue(observed['stream_threads_finished'])

    def test_no_progress_stall_is_classified_and_reaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = ('import sys,time; sys.stdin.read(); '
                    'print(\'{"type":"turn.started"}\',flush=True); time.sleep(30)')
            started = time.monotonic()
            with self.assertRaises(model_call.ModelExecutionError) as caught:
                model_call.run([sys.executable, '-c', code], 'input', root, 60, root / 'audit', {},
                               progress_timeout=1)
            self.assertLess(time.monotonic() - started, 20)
            self.assertEqual(caught.exception.code, 'model_stalled')
            self.assertEqual(caught.exception.kind, 'model_transport')
            self.assertIn('no lifecycle event', str(caught.exception))
            seen = json.loads((root / 'audit/process.json').read_text())
            self.assertEqual(seen['status'], 'stalled')
            self.assertEqual(seen['timeout_location'], 'no_lifecycle_event_or_inbound_activity')
            self.assertGreaterEqual(seen['stall_seconds'], 1)
            self.assertIsNotNone(seen['last_stdout_event_seconds'])
            self.assertTrue(seen['stream_threads_finished'])
            self.assertEqual(seen['io_errors'], [])
            self.assertEqual(json.loads((root / 'audit/stall.json').read_text())['status'], 'stalled')

    def test_stdout_progress_defers_the_stall_watchdog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = ('import sys,time\nsys.stdin.read()\n'
                    'for _ in range(4):\n'
                    ' print(\'{"type":"item.completed","item":{"type":"reasoning"}}\',flush=True)\n'
                    ' time.sleep(0.6)\n')
            result = model_call.run([sys.executable, '-c', code], 'input', root, 30, root / 'audit', {},
                                    progress_timeout=1)
            self.assertEqual(result.returncode, 0)
            seen = json.loads((root / 'audit/process.json').read_text())
            self.assertEqual(seen['status'], 'exited')
            self.assertEqual(seen['progress_timeout_seconds'], 1.0)
            self.assertFalse((root / 'audit/stall.json').exists())

    def test_progress_watchdog_never_extends_the_total_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(model_call.ModelExecutionError) as caught:
                model_call.run([sys.executable, '-c', 'import time; time.sleep(30)'],
                               '', root, 1, root / 'audit', {}, progress_timeout=600)
            seen = json.loads((root / 'audit/process.json').read_text())
            self.assertEqual(seen['status'], 'timed_out')
            self.assertEqual(seen['progress_timeout_seconds'], 1.0)
            self.assertNotEqual(getattr(caught.exception, 'code', None), 'model_stalled')
            self.assertLess(seen['elapsed_seconds'], 5)

    def test_disabled_watchdog_keeps_waiting_for_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = 'import sys,time; sys.stdin.read(); time.sleep(1.2); print(\'{"type":"turn.completed"}\')'
            model_call.run([sys.executable, '-c', code], 'input', root, 30, root / 'audit', {})
            seen = json.loads((root / 'audit/process.json').read_text())
            self.assertEqual(seen['status'], 'exited')
            self.assertIsNone(seen['progress_timeout_seconds'])

    @unittest.skipUnless(os.name == 'nt', 'Windows cumulative process counters')
    def test_process_counters_are_recorded_without_input_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = 'SECRET_SENTINEL_PROMPT'
            model_call.run([sys.executable, '-c', 'import sys; sys.stdin.read(); print("ok")'],
                           marker, root, 30, root / 'audit', {}, progress_timeout=20)
            seen = json.loads((root / 'audit/process.json').read_text())
            counters = seen['process_counters']
            self.assertTrue(counters['available'])
            self.assertGreaterEqual(counters['samples'], 1)
            self.assertIsInstance(counters['read_bytes_growth'], int)
            self.assertTrue(seen['process_counter_timeline'])
            self.assertNotIn(marker, (root / 'audit/process.json').read_text())
            self.assertIn('cpu_seconds', seen['process_counter_timeline'][0])

    def test_process_io_growth_does_not_count_as_progress(self):
        from creation_pipeline.runtime import process_stats
        calls = {'n': 0}
        def latest(_sampler):
            calls['n'] += 1
            return {'read_bytes': calls['n'] * 8192}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(process_stats.Sampler, 'start', new=lambda self: self), \
                    patch.object(process_stats.Sampler, 'latest', new=latest), \
                    patch.object(process_stats.Sampler, 'stop', new=lambda self: {'available': False}), \
                    self.assertRaises(model_call.ModelExecutionError) as caught:
                model_call.run([sys.executable, '-c', 'import time; time.sleep(20)'],
                               '', root, 30, root / 'audit', {}, progress_timeout=1)
            seen = json.loads((root / 'audit/process.json').read_text())
            # I/O growth is recorded as evidence but must not defer the window.
            self.assertEqual(seen['status'], 'stalled')
            self.assertTrue(seen['process_io_growth_seen'])
            self.assertIn('not thereby known', seen['window_meaning'])
            self.assertEqual(getattr(caught.exception, 'code', None), 'model_stalled')

    def test_answer_without_successful_turn_is_transport_failure(self):
        message = {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '{"ok":true}'}}
        for events in ([message], [message, {'type': 'turn.failed'}],
                       [message, {'type': 'turn.completed'}, {'type': 'error', 'message': 'failed'}]):
            proc = subprocess.CompletedProcess([], 0, '\n'.join(json.dumps(e) for e in events), '')
            with patch.object(model_call, 'run', return_value=proc), \
                 patch.object(model_call, 'codex_command', return_value=['codex']), \
                 patch.object(model_call, 'isolated_options', return_value=([], {})), \
                 self.assertRaises(model_call.ModelExecutionError):
                model_call.call('supplied', {}, 'fixed')

    def test_structured_response_and_tool_rejection_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp, patch('creation_pipeline.runtime.model_call.codex_command',return_value=['codex']), \
                patch('creation_pipeline.runtime.model_call.isolated_options',return_value=([],{})):
            response={'type':'item.completed','item':{'type':'agent_message','text':'{"ok":true}'}}
            proc=subprocess.CompletedProcess([],0,json.dumps(response)+'\n'+json.dumps({'type':'turn.completed','usage':{'input_tokens':1}}),'')
            with patch('creation_pipeline.runtime.model_call.run',return_value=proc) as run:
                answer,receipt=model_call.call('supplied',{},'fixed',timeout=17,audit_dir=Path(tmp)/'audit')
                self.assertTrue(answer['ok']); self.assertEqual(receipt['usage']['input_tokens'],1)
                self.assertEqual(run.call_args.args[3],17)
                self.assertEqual(run.call_args.args[-1]['model'],'fixed')
            proc.stdout+='\n'+json.dumps({'type':'item.completed','item':{'type':'command_execution'}})
            with patch('creation_pipeline.runtime.model_call.run',return_value=proc), self.assertRaises(ValueError):
                model_call.call('supplied',{},'fixed')


if __name__=='__main__': unittest.main()
