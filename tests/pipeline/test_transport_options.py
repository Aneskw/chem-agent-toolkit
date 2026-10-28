import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.agent.command import transport_args
from creation_pipeline.models import load_config
from creation_pipeline.runtime import model_call, planner


class TransportOptionTests(unittest.TestCase):
    def test_default_transport_adds_nothing(self):
        self.assertEqual(transport_args('default'), [])
        with self.assertRaises(ValueError):
            transport_args('websocket-only')

    def test_https_transport_pins_the_responses_provider(self):
        args = transport_args('https')
        self.assertIn('model_provider=planner_https', args)
        self.assertIn('model_providers.planner_https.supports_websockets=false', args)

    def test_isolated_options_carry_the_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'config.toml').write_text('model="m"\n', encoding='utf-8')
            with patch.dict('os.environ', {'CODEX_HOME': tmp}):
                plain, _ = model_call.isolated_options('default')
                https, _ = model_call.isolated_options('https')
        self.assertNotIn('model_provider=planner_https', plain)
        self.assertIn('model_provider=planner_https', https)

    def test_planner_options_expose_transport_and_progress_mode(self):
        defaults = planner.options({})
        self.assertEqual((defaults['transport'], defaults['progress_watch']), ('default', 'terminate'))
        chosen = planner.options({'transport': 'https', 'progress_watch': 'observe'})
        self.assertEqual((chosen['transport'], chosen['progress_watch']), ('https', 'observe'))
        for bad in ({'transport': 'ws'}, {'progress_watch': 'warn'}):
            with self.assertRaises(planner.PlanningError):
                planner.options(bad)

    def test_plan_forwards_transport_and_observe_only_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, 'source')
            source.mkdir()
            Path(source, 'main.py').write_text('print(1)\n', encoding='utf-8')
            with patch.object(planner.model_call, 'call', return_value=({'action': 'plan', 'plan': {}}, {})) as call:
                planner.plan(source, {}, Path(tmp, 'audit'),
                             planner.options({'transport': 'https', 'progress_watch': 'observe'}), None)
        self.assertEqual(call.call_args.kwargs['transport'], 'https')
        self.assertEqual(call.call_args.kwargs['progress_watch'], 'observe')

    def test_config_accepts_and_validates_model_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'input.json')
            base = {'sources': [{'id': 'c', 'path': 'x.py'}], 'model': {'name': 'm', 'transport': 'https'},
                    'limits': {'model_calls': 8}}
            path.write_text(json.dumps(base), encoding='utf-8')
            self.assertEqual(load_config(path)['model']['transport'], 'https')
            base['model']['transport'] = 'grpc'
            path.write_text(json.dumps(base), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'model.transport'):
                load_config(path)


class ObserveOnlyProgressTests(unittest.TestCase):
    def test_observe_mode_records_silence_without_stopping(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = ('import sys,time\nsys.stdin.read()\n'
                    'time.sleep(2.0)\n'
                    'print(\'{"type":"turn.completed"}\',flush=True)\n')
            proc = model_call.run([sys.executable, '-c', code], 'in', root, 30, root / 'audit', {},
                                  progress_timeout=0.5, progress_watch='observe')
            self.assertEqual(proc.returncode, 0)
            seen = json.loads((root / 'audit/process.json').read_text(encoding='utf-8'))
            self.assertEqual(seen['status'], 'exited')
            self.assertTrue(seen['progress_limit_exceeded'])
            self.assertGreater(seen['progress_observed_silence_seconds'], 0.5)
            self.assertFalse((root / 'audit/stall.json').exists())

    def test_terminate_mode_is_still_the_default(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(model_call.ModelExecutionError):
                model_call.run([sys.executable, '-c', 'import time; time.sleep(20)'],
                               '', root, 30, root / 'audit', {}, progress_timeout=0.5)
            seen = json.loads((root / 'audit/process.json').read_text(encoding='utf-8'))
            self.assertEqual(seen['status'], 'stalled')
            self.assertTrue((root / 'audit/stall.json').exists())


if __name__ == '__main__':
    unittest.main()
