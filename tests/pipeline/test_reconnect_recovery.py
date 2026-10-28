"""Recoverable reconnect notices must not fail an otherwise good turn.

Five behaviours are pinned for both supervisors: recovered success, reconnect
without recovery, terminal failure, missing valid answer, and non-zero exit.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.agent import backend
from creation_pipeline.models import load_config
from creation_pipeline.records import write_json
from creation_pipeline.resources.intake import Sources
from creation_pipeline.runtime import model_call

NOTICE = "Reconnecting... 1/5 (stream disconnected before completion: Transport error: network error: error decoding response body)"


def events(*items):
    return '\n'.join(json.dumps(item) for item in items)


def agent_message(payload):
    return {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(payload)}}


COMPLETED = {'type': 'turn.completed', 'usage': {'input_tokens': 1, 'output_tokens': 1}}


class ClassifierTests(unittest.TestCase):
    def test_notices_and_terminal_errors_are_distinguished(self):
        from creation_pipeline.records import is_recoverable_notice
        self.assertTrue(is_recoverable_notice(NOTICE))
        self.assertTrue(is_recoverable_notice('Falling back from WebSockets to HTTPS transport. timed out'))
        self.assertFalse(is_recoverable_notice('stream disconnected before completion: boom'))
        self.assertFalse(is_recoverable_notice('turn.failed'))
        self.assertFalse(is_recoverable_notice(''))


class AgentTurnTests(unittest.TestCase):
    def run_stage(self, body, exit_code=0):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / 'fake.py'
            fake.write_text('import sys,json\nsys.stdin.read()\n' + body +
                            ('' if exit_code == 0 else f'\nsys.exit({exit_code})\n'), encoding='utf-8')
            (root / 'src.py').write_text('def f():\n    return 1\n', encoding='utf-8')
            write_json(root / 'input.json', {'sources': [{'id': 'c', 'path': 'src.py'}], 'network': False,
                                             'limits': {'model_calls': 4, 'model_timeout': 30}})
            config = load_config(root / 'input.json')
            sources = Sources(config, root / 'cache')
            work = root / 'run'
            work.mkdir()
            session = backend.NativeSession(config, sources, config['limits'].copy(), work)
            with patch('creation_pipeline.agent.backend.codex_command', return_value=[sys.executable, str(fake)]):
                answer = session.stage('test', {}, {})
            session.saved_state = session.state_path.read_text(encoding='utf-8') if session.state_path.exists() else '{}'
            return session, answer

    def body(self, *lines):
        return '\n'.join('print(json.dumps(%r), flush=True)' % (line,) for line in lines)

    def test_recovered_reconnect_with_valid_answer_succeeds(self):
        session, answer = self.run_stage(self.body(
            {'type': 'thread.started', 'thread_id': 's1'}, agent_message({'ok': True}),
            {'type': 'error', 'message': NOTICE}, COMPLETED))
        self.assertEqual(answer, {'ok': True})
        receipt = json.loads(session.saved_state)['receipts'][0]
        self.assertEqual(receipt['status'], 'completed')
        self.assertEqual(len(receipt['stream_notices']), 1)
        self.assertNotIn('error', receipt)

    def test_reconnect_without_recovery_is_a_failure(self):
        with self.assertRaises(ValueError):
            self.run_stage(self.body({'type': 'thread.started', 'thread_id': 's2'},
                                     agent_message({'ok': True}), {'type': 'error', 'message': NOTICE}))

    def test_terminal_error_still_fails_even_with_a_valid_answer(self):
        with self.assertRaises(ValueError):
            self.run_stage(self.body({'type': 'thread.started', 'thread_id': 's3'}, agent_message({'ok': True}),
                                     {'type': 'error', 'message': 'stream disconnected before completion: boom'},
                                     COMPLETED))

    def test_missing_valid_answer_fails(self):
        with self.assertRaises(ValueError):
            self.run_stage(self.body({'type': 'thread.started', 'thread_id': 's4'},
                                     {'type': 'item.completed',
                                      'item': {'type': 'agent_message', 'text': 'not json'}}, COMPLETED))

    def test_non_zero_exit_fails(self):
        with self.assertRaises(ValueError):
            self.run_stage(self.body({'type': 'thread.started', 'thread_id': 's5'}, agent_message({'ok': True}),
                                     COMPLETED), exit_code=3)


class StructuredCallTests(unittest.TestCase):
    def call(self, stdout, returncode=0):
        proc = subprocess.CompletedProcess([], returncode, stdout, '')
        with patch.object(model_call, 'run', return_value=proc), \
                patch.object(model_call, 'codex_command', return_value=['codex']), \
                patch.object(model_call, 'isolated_options', return_value=([], {})):
            return model_call.call('supplied', {}, 'fixed')

    def test_recovered_reconnect_returns_the_answer(self):
        answer, receipt = self.call(events(agent_message({'ok': True}),
                                           {'type': 'error', 'message': NOTICE}, COMPLETED))
        self.assertTrue(answer['ok'])
        self.assertEqual(len(receipt['stream_notices']), 1)

    def test_reconnect_without_completion_fails(self):
        with self.assertRaises(model_call.ModelExecutionError):
            self.call(events(agent_message({'ok': True}), {'type': 'error', 'message': NOTICE}))

    def test_terminal_error_fails(self):
        with self.assertRaises(model_call.ModelExecutionError):
            self.call(events(agent_message({'ok': True}),
                             {'type': 'error', 'message': 'stream disconnected before completion: boom'}, COMPLETED))

    def test_missing_answer_fails(self):
        with self.assertRaises(model_call.ModelOutputInvalid):
            self.call(events(COMPLETED))

    def test_non_zero_exit_fails(self):
        with self.assertRaises(model_call.ModelExecutionError):
            self.call(events(agent_message({'ok': True}), COMPLETED), returncode=2)

    def test_recoverable_error_item_is_not_counted_as_tool_use(self):
        notice_item = {'type': 'item.completed', 'item': {'type': 'error', 'message': NOTICE}}
        answer, _ = self.call(events(notice_item, agent_message({'ok': True}), COMPLETED))
        self.assertTrue(answer['ok'])

    def test_terminal_error_item_still_counts_as_tool_violation(self):
        error_item = {'type': 'item.completed', 'item': {'type': 'error', 'message': 'boom'}}
        with self.assertRaises(ValueError):
            self.call(events(error_item, agent_message({'ok': True}), COMPLETED))

    def test_batch2_replay_is_no_longer_a_failure(self):
        """Replay of the recorded batch-2 discovery event sequence."""
        tape = Path(__file__).resolve().parents[2] / \
            'validation/final-acceptance-run/batch-2/agent-turn-001-events.jsonl'
        lines = [json.loads(line) for line in tape.read_text(encoding='utf-8').splitlines() if line.strip()]
        stdout = '\n'.join(json.dumps({'type': e.get('type'), 'item': e.get('item'),
                                       'message': e.get('message'), 'usage': e.get('usage')})
                           for e in lines)
        # The replayed turn carries tool executions, so the structured path must
        # reject it for that reason alone; the reconnect notice must not be the cause.
        with self.assertRaises(ValueError) as caught:
            self.call(stdout)
        self.assertNotIn('Reconnecting', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
