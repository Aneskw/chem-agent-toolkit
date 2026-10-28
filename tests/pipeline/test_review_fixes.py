"""Regression tests for the acceptance-review fixes; no model or Docker calls."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.agent import backend
from creation_pipeline.artifacts import store
from creation_pipeline.records import redact, write_json
from creation_pipeline.runtime import entry, planner


class RedactionTests(unittest.TestCase):
    def test_quoted_authorization_cookie_query_and_jwt_are_redacted(self):
        samples = [
            'authorization="Bearer abcdefghijklmnop"',
            'Authorization: Bearer abcdefghijklmnop',
            'cookie="session=abcdefghijklmnop"',
            'GET https://host/backend?token=abcdefghijklmnop&x=1',
            'trace eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop',
            'summary sk-ABCDEFGHIJKLMNOPQRST',
        ]
        for sample in samples:
            cleaned = redact(sample)
            self.assertIn('[REDACTED]', cleaned, sample)
            self.assertNotIn('abcdefghijklmnop', cleaned, sample)
            self.assertNotIn('ABCDEFGHIJKLMNOPQRST', cleaned, sample)

    def test_ordinary_text_is_unchanged(self):
        text = 'plan accepted; elapsed 149.8s; tokens 24991'
        self.assertEqual(redact(text), text)


class EntrySelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.package = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, text):
        path = self.package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def test_markdown_block_alone_is_the_entry(self):
        self.write('SKILL.md', '---\nname: x\ndescription: x\n---\n\n```python\nprint(1)\n```\n')
        binding = entry.preflight(self.package)
        self.assertEqual(binding['kind'], 'markdown_python')
        self.assertEqual(binding['runtime_entry'], 'entry/skill.py')

    def test_single_script_alone_is_the_entry(self):
        self.write('SKILL.md', '---\nname: x\ndescription: x\n---\n\nNo runnable block here.\n')
        self.write('run.py', 'print(1)\n')
        binding = entry.preflight(self.package)
        self.assertEqual(binding['kind'], 'script')
        self.assertEqual(binding['entry'], 'run.py')

    def test_block_and_script_together_are_ambiguous_not_preferred(self):
        self.write('SKILL.md', '---\nname: x\ndescription: x\n---\n\n```python\nprint(1)\n```\n')
        self.write('run.py', 'print(2)\n')
        with self.assertRaises(entry.EntryError) as caught:
            entry.preflight(self.package)
        self.assertEqual(caught.exception.code, 'entry_ambiguous')
        self.assertEqual(caught.exception.kind, 'unresolved_input')

    def test_two_scripts_are_ambiguous(self):
        self.write('SKILL.md', '---\nname: x\ndescription: x\n---\n\nNo block.\n')
        self.write('a.py', 'print(1)\n')
        self.write('b.sh', 'echo 1\n')
        with self.assertRaises(entry.EntryError) as caught:
            entry.preflight(self.package)
        self.assertEqual(caught.exception.code, 'entry_ambiguous')

    def test_script_wins_only_when_the_block_is_unusable_and_the_reason_is_kept(self):
        self.write('SKILL.md', '---\nname: x\ndescription: x\n---\n\n```python\nprint(undefined_name)\n```\n')
        self.write('run.py', 'print(1)\n')
        binding = entry.preflight(self.package)
        self.assertEqual(binding['kind'], 'script')
        self.assertEqual(binding['markdown_candidate_rejected']['code'], 'entry_context_missing')

    def test_no_script_and_unsupported_block_keeps_the_contract_verdict(self):
        self.write('SKILL.md', '---\nname: x\ndescription: x\n---\n\n```bash\necho 1\n```\n')
        with self.assertRaises(entry.EntryError) as caught:
            entry.preflight(self.package)
        self.assertEqual(caught.exception.code, 'entry_unsupported')
        self.assertEqual(caught.exception.kind, 'unsupported_contract')


class PinBaseImageTests(unittest.TestCase):
    def test_the_pin_flag_is_now_supported_and_still_typed(self):
        # Pinning used to be refused as unimplemented. It is implemented now:
        # tests/pipeline/test_pin_base_image.py covers resolution, rendering, freezing
        # and the execution probe. Only the flag's type is still enforced here.
        self.assertFalse(planner.options({})['pin_base_image'])
        self.assertTrue(planner.options({'pin_base_image': True})['pin_base_image'])
        with self.assertRaisesRegex(planner.PlanningError, 'pin_base_image'):
            planner.options({'pin_base_image': 'yes'})


class AgentStallClassificationTests(unittest.TestCase):
    def test_stall_is_a_transport_fault_not_a_budget_stop(self):
        from creation_pipeline.models import BudgetError, ModelCallError
        self.assertTrue(issubclass(backend.AgentStalled, TimeoutError))
        self.assertFalse(issubclass(backend.AgentStalled, BudgetError))
        stalled = ModelCallError('no output')
        stalled.code, stalled.kind = backend.AgentStalled.code, backend.AgentStalled.kind
        self.assertEqual((stalled.code, stalled.kind), ('model_stalled', 'model_transport'))

    def test_mcp_isolation_refusal_is_typed(self):
        from creation_pipeline.runtime import model_call
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'config.toml').write_text('[mcp_servers."bad name"]\ncommand="x"\n', encoding='utf-8')
            with patch.dict('os.environ', {'CODEX_HOME': tmp}), \
                    self.assertRaises(model_call.ModelConfigError) as caught:
                model_call.isolated_options()
            self.assertEqual(caught.exception.code, 'model_config_invalid')


class TransientHostDeferralTests(unittest.TestCase):
    def entry(self):
        return {'name': 'probe', 'path': 'accepted/probe', 'zone': 'accepted',
                'revision_id': 'rev-1', 'freeze_sha256': 'f' * 64, 'evidence': 'evidence/probe',
                'runtime': {'path': 'runtime/probe'},
                'delivery': {'inputs': {'requirement': {'status': 'required'}}},
                'current_qualification': {'accepted': True, 'reason': 'ok'}}

    def reconcile(self, valid, unavailable, initial):
        value = {'skills': [dict(self.entry(), **initial)]}
        committed = {}
        with patch.object(store, 'check', return_value=None), \
                patch.object(store, 'qualification', return_value=valid), \
                patch.object(store, 'host_unavailable', return_value=unavailable), \
                patch.object(store, 'commit', side_effect=lambda root, v, p: committed.update(v['skills'][0])):
            store.reconcile(Path('.'), value)
        return value['skills'][0], committed

    def test_host_outage_keeps_acceptance_and_records_a_deferral(self):
        entry, committed = self.reconcile((False, 'Current acceptance verification failed'), True, {})
        self.assertEqual(entry['zone'], 'accepted')
        self.assertEqual(entry['path'], 'accepted/probe')
        self.assertNotIn('runtime_invalidated', entry)
        self.assertTrue(entry['current_qualification']['deferred'])
        self.assertFalse(entry['current_qualification']['accepted'])
        self.assertTrue(committed, 'the deferral must be persisted')

    def test_drift_still_demotes_when_the_host_is_available(self):
        entry, _ = self.reconcile((False, 'Current acceptance verification failed'), False, {})
        self.assertEqual(entry['zone'], 'candidates')
        self.assertIn('runtime_invalidated', entry)

    def test_returning_host_clears_the_deferral(self):
        initial = {'current_qualification': {'accepted': False, 'deferred': True, 'reason': 'deferred'}}
        entry, committed = self.reconcile((True, 'Content review and current Docker business evidence passed'),
                                          False, initial)
        self.assertEqual(entry['zone'], 'accepted')
        self.assertTrue(entry['current_qualification']['accepted'])
        self.assertNotIn('deferred', entry['current_qualification'])
        self.assertEqual(entry['current_host']['status'], 'available')
        self.assertTrue(committed)


if __name__ == '__main__':
    unittest.main()
