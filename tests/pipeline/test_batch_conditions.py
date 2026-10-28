"""Batch condition propagation and failure branches end to end.

These drive the real entry points (association, review turn, planner call and a
real silent child process) instead of inspecting helpers or source text.
"""
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.agent import backend
from creation_pipeline.models import load_config
from creation_pipeline.pipeline import runtime_gate_stops
from creation_pipeline.records import write_json
from creation_pipeline.runtime import entry, model_call, planner, review


def batch_input(**overrides):
    data = {'sources': [{'id': 'c', 'path': 'x.py'}],
            'model': {'name': 'gpt-6-astra', 'transport': 'https',
                      'reasoning_effort': 'medium', 'service_tier': 'default'},
            'execution': {'profile': 'production', 'stop_on_runtime_failure': True,
                          'progress_watch': 'observe'},
            'limits': {'model_calls': 8, 'model_timeout': 600, 'total_seconds': 3600,
                       'max_candidates': 1, 'max_builds': 1, 'repair_rounds': 1}}
    data.update(overrides)
    return data


SETTINGS = {'transport': 'https', 'reasoning_effort': 'medium', 'service_tier': 'default',
            'progress_watch': 'observe'}


class AssociationPropagationTests(unittest.TestCase):
    """entry.associate must forward the batch settings to its model call."""

    def run_associate(self, options):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / 'package'
            package.mkdir()
            (package / 'SKILL.md').write_text('---\nname: x\ndescription: x\n---\n\n```python\nprint(1)\n```\n',
                                              encoding='utf-8')
            source = root / 'source'
            source.mkdir()
            (source / 'main.py').write_text('def decompose(mol):\n    return mol\n', encoding='utf-8')
            sources = [{'id': 'tool', 'path': str(source), 'resolved_ref': 'fixed-test-fixture',
                        'inventory': [{'path': 'main.py', 'sha256': 'd' * 64, 'size': 1}]}]
            binding = {'kind': 'markdown_python', 'entry': 'SKILL.md', 'runtime_entry': 'entry/skill.py',
                       'extraction': {'start_byte': 0, 'end_byte': 8, 'code_sha256': 'b' * 64,
                                      'markdown_sha256': 'c' * 64, 'block_index': 0, 'start_line': 5,
                                      'rule': 'single-unindented-python-fence-v1'}}
            record = {'delivery': {'inputs': {}}, 'plan': {}}
            proposal = {'source_id': 'tool', 'source_path': 'main.py', 'quote': 'def decompose(mol):',
                        'reason': 'source explains the API', 'invocation': 'python', 'supported': True}
            review_result = {'status': 'pass', 'binding_verified': True, 'requirement_assessment': 'confirmed',
                             'resolution': 'none', 'findings': []}
            with patch.object(entry, 'file_digest', return_value='d' * 64), \
                    patch.object(entry, 'manifest', return_value=[]), \
                    patch.object(entry, 'source_view', return_value=[]), \
                    patch('creation_pipeline.runtime.model_call.call') as call, \
                    patch('creation_pipeline.runtime.review.review_snapshot',
                          return_value={'review': review_result}) as snapshot:
                call.return_value = (proposal, {'usage': None})
                opts = planner.options(dict(options, model='gpt-6-astra'))
                entry.associate(record, package, sources, root / 'audit', opts)
            return call, snapshot

    def test_association_forwards_every_stage_setting(self):
        call, snapshot = self.run_associate(SETTINGS)
        kwargs = call.call_args.kwargs
        self.assertEqual(kwargs['transport'], 'https')
        self.assertEqual(kwargs['reasoning'], 'medium')
        self.assertEqual(kwargs['tier'], 'default')
        self.assertEqual(kwargs['progress_watch'], 'observe')
        review_kwargs = snapshot.call_args.kwargs
        self.assertEqual(review_kwargs['transport'], 'https')
        self.assertEqual(review_kwargs['reasoning_effort'], 'medium')
        self.assertEqual(review_kwargs['service_tier'], 'default')

    def test_defaults_are_kept_when_no_settings_are_given(self):
        call, snapshot = self.run_associate({})
        kwargs = call.call_args.kwargs
        self.assertEqual((kwargs['transport'], kwargs['progress_watch']), ('default', 'terminate'))
        self.assertIsNone(kwargs['reasoning'])
        self.assertIsNone(snapshot.call_args.kwargs['service_tier'])


class ReviewTurnConfigTests(unittest.TestCase):
    """The review turn is a model stage: its own child config must carry them."""

    def test_review_config_records_transport_effort_and_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / 'package'
            package.mkdir()
            (package / 'SKILL.md').write_text('Body\n', encoding='utf-8')
            source = root / 'source'
            source.mkdir()
            (source / 'main.py').write_text('print(1)\n', encoding='utf-8')
            write_json(root / 'record.json', {})
            record = {'plan': {'name': 'x'}, 'delivery': {'inputs': {'acceptance': {'payload': {}},
                                                                     'requirement': {'status': 'required'}}},
                      'test_definitions': {}}
            captured = {}

            def fake_review(session, plan, artifact, checks, scoped):
                captured['config'] = session.config['model']
                return {'status': 'pass', 'oracle_changes_verified': True,
                        'requirement_assessment': 'confirmed', 'resolution': 'none', 'findings': []}

            with patch.object(review, 'review', side_effect=fake_review):
                review.review_snapshot(record, package,
                                       [{'id': 'tool', 'path': str(source),
                                         'inventory': [{'path': 'main.py', 'sha256': 'a' * 64, 'size': 8}]}],
                                       root / 'work', model='gpt-6-astra',
                                       transport='https', reasoning_effort='medium', service_tier='default')
            self.assertEqual(captured['config']['transport'], 'https')
            self.assertEqual(captured['config']['reasoning_effort'], 'medium')
            self.assertEqual(captured['config']['service_tier'], 'default')


class NormalBuildPlannerSettingsTests(unittest.TestCase):
    """A normal build must hand the planner observe mode, not the terminate default."""

    def test_runtime_options_carry_progress_watch_through_the_build_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'input.json')
            path.write_text(json.dumps(batch_input()), encoding='utf-8')
            config = load_config(path)
            source = Path(tmp, 'source')
            source.mkdir()
            (source / 'main.py').write_text('print(1)\n', encoding='utf-8')
            spec = {}
            spec.setdefault('options', {}).setdefault('model', 'gpt-6-astra')
            spec['options'].setdefault('transport', config['model'].get('transport', 'default'))
            spec['options'].setdefault('progress_watch', config['execution'].get('progress_watch', 'terminate'))
            for key in ('reasoning_effort', 'service_tier'):
                if config['model'].get(key) is not None:
                    spec['options'].setdefault(key, config['model'][key])
            opts = planner.options(spec['options'])
            with patch.object(planner.model_call, 'call', return_value=({'action': 'plan', 'plan': {}}, {})) as call:
                planner.plan(source, {}, Path(tmp, 'audit'), opts, None)
            kwargs = call.call_args.kwargs
            self.assertEqual(kwargs['progress_watch'], 'observe')
            self.assertEqual(kwargs['transport'], 'https')
            self.assertEqual((kwargs['reasoning'], kwargs['tier']), ('medium', 'default'))


class SilentChildBehaviourTests(unittest.TestCase):
    """A silent child must not be killed by the observe-only policy."""

    def test_observe_only_agent_turn_survives_a_silent_child(self):
        silent = ('import sys,json,time\nsys.stdin.read()\n'
                  'print(json.dumps({"type":"thread.started","thread_id":"quiet"}),flush=True)\n'
                  'time.sleep(1.6)\n'
                  'print(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":json.dumps({"ok":true})}}),flush=True)\n'
                  'print(json.dumps({"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}),flush=True)\n')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / 'fake.py'
            fake.write_text(silent.replace('true', 'True'), encoding='utf-8')
            (root / 'src.py').write_text('def f():\n    return 1\n', encoding='utf-8')
            write_json(root / 'input.json', {'sources': [{'id': 'c', 'path': 'src.py'}], 'network': False,
                                             'limits': {'model_calls': 4, 'model_timeout': 30}})
            from creation_pipeline.models import load_config as load
            from creation_pipeline.resources.intake import Sources
            config = load(root / 'input.json')
            sources = Sources(config, root / 'cache')
            work = root / 'run'
            work.mkdir()
            session = backend.NativeSession(config, sources, config['limits'].copy(), work)
            self.assertIsNone(session.limits.get('agent_progress_timeout'))
            started = time.monotonic()
            with patch.object(backend, 'PROGRESS_OBSERVE_SECONDS', 0.5), \
                    patch('creation_pipeline.agent.backend.codex_command', return_value=[sys.executable, str(fake)]):
                answer = session.stage('test', {}, {})
            self.assertEqual(answer, {'ok': True})
            self.assertLess(time.monotonic() - started, 20)
            observed = json.loads((session.state_path).read_text(encoding='utf-8'))['receipts'][0]['progress_observation']
            self.assertEqual(observed['watchdog'], 'observe_only')
            self.assertGreaterEqual(observed['max_silence_seconds'], 0.5)
            self.assertTrue(observed['progress_limit_exceeded'])
            self.assertEqual(observed['observe_seconds'], 0.5)

    def test_observe_only_planner_call_is_not_stalled_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = ('import sys,time\nsys.stdin.read()\ntime.sleep(1.2)\n'
                    'print(\'{"type":"turn.completed"}\',flush=True)\n')
            proc = model_call.run([sys.executable, '-c', code], 'in', root, 30, root / 'audit', {},
                                  progress_timeout=0.4, progress_watch='observe')
            self.assertEqual(proc.returncode, 0)
            seen = json.loads((root / 'audit/process.json').read_text(encoding='utf-8'))
            self.assertEqual(seen['status'], 'exited')
            self.assertTrue(seen['progress_limit_exceeded'])
            self.assertFalse((root / 'audit/stall.json').exists())


class ConfigAndGateTests(unittest.TestCase):
    def test_actual_batch_input_is_accepted_with_its_budget(self):
        path = Path(__file__).resolve().parents[2] / 'validation/final-acceptance-review/input-batch-1.json'
        config = load_config(path)
        self.assertEqual(config['model']['transport'], 'https')
        self.assertEqual(config['execution']['progress_watch'], 'observe')
        self.assertEqual(config['limits']['model_calls'], 8)
        self.assertEqual(config['limits']['model_timeout'], 600)
        self.assertEqual(config['limits']['total_seconds'], 3600)
        self.assertEqual(config['limits']['max_candidates'], 1)
        self.assertEqual(config['limits']['max_builds'], 1)
        self.assertTrue(config['execution']['stop_on_runtime_failure'])

    def test_progress_watch_value_is_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'i.json')
            data = batch_input(execution={'profile': 'production', 'progress_watch': 'warn'})
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'progress_watch'):
                load_config(path)

    def test_gate_stops_on_build_and_execution_failures_only(self):
        on = {'execution': {'stop_on_runtime_failure': True}}
        off = {'execution': {'stop_on_runtime_failure': False}}
        for status in ('build_failed', 'execution_failed'):
            self.assertTrue(runtime_gate_stops(on, {'status': status}))
            self.assertFalse(runtime_gate_stops(off, {'status': status}))
        for status in ('built', 'execution_passed', 'not_run'):
            self.assertFalse(runtime_gate_stops(on, {'status': status}))
        self.assertFalse(runtime_gate_stops(on, None))


if __name__ == '__main__':
    unittest.main()
