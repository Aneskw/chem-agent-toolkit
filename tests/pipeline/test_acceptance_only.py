"""Acceptance-only model doubles exercise production material/budget/merge gates."""
import copy
import json
import time
import unittest
from unittest.mock import patch

from creation_pipeline.runtime import planner, shared_tool
from creation_pipeline.runtime.preparation import propose, bind, RuntimeBlocked
from tests.pipeline import test_shared_tool as fixtures
from tests.pipeline.test_runtime_build import plan


class AcceptanceOnlyTests(unittest.TestCase):
    def test_shell_command_is_rejected_as_executable_without_rewriting_probe(self):
        value = {'tests': [{'name': 'rdkit-probe', 'case_json': json.dumps({
            'entrypoint': 'python -c "import rdkit"', 'args': [], 'stdout_contains': 'rdkit_ok'})}]}
        before = copy.deepcopy(value)
        with self.assertRaisesRegex(planner.PlanningError, r'tests\[rdkit-probe\].*expected one executable token'):
            planner.validate_acceptance_entrypoints(value)
        self.assertEqual(value, before)
        value['tests'][0]['case_json'] = json.dumps({'entrypoint': 'python',
            'args': ['-c', 'import rdkit; print("rdkit_ok")'], 'stdout_contains': 'rdkit_ok'})
        planner.validate_acceptance_entrypoints(value)

    def test_relation_shell_command_is_rejected_as_executable(self):
        value = {'tests': [{'name': 'relation-probe', 'case_json': json.dumps({
            'relation': {'runs': [{'entrypoint': 'python -c code'}]}})}]}
        with self.assertRaisesRegex(planner.PlanningError, r'relation.runs\[0\].entrypoint'):
            planner.validate_acceptance_entrypoints(value)

    setUp = fixtures.SharedToolTests.setUp
    tearDown = fixtures.SharedToolTests.tearDown
    request = fixtures.SharedToolTests.request

    def run_plan(self, answer, observed_tool_identity=None, **options):
        self.request()
        base = shared_tool.environment_plan(plan())
        before = copy.deepcopy(base)
        tickets = []
        def guard():
            ticket = {}; tickets.append(ticket); return ticket
        with patch.object(planner.model_call, 'call', return_value=(answer, {'status': 'completed', 'model': 'unchanged-model'})) as model:
            result = planner.plan(self.root/'handoff', {'script': 'package/main.py'}, self.root/'audit',
                                  planner.options(dict(backend='deepseek_api', api_model='unchanged-model', **options)),
                                  time.monotonic()+30, call_guard=guard, acceptance_base=base,
                                  observed_tool_identity=observed_tool_identity)
        self.assertEqual(base, before)
        self.assertEqual(shared_tool.environment_plan(result[0]), before)
        self.assertEqual(tickets[0]['phase'], 'runtime_acceptance_planning')
        self.assertEqual(model.call_args.kwargs['backend'], 'deepseek_api')
        self.assertEqual(model.call_args.args[2], 'unchanged-model')
        self.assertIs(model.call_args.args[1], planner.ACCEPTANCE_ONLY_SCHEMA)
        return result

    def answer(self):
        return {'action': 'plan', 'requested_files': [], 'reason': 'fresh current contract',
                'plan': {k: copy.deepcopy(plan()[k]) for k in shared_tool.ACCEPTANCE}}

    def test_only_acceptance_is_generated_with_original_backend_and_receipts(self):
        value = self.answer(); value['plan']['tests'][1]['name'] = 'new-current'
        result = self.run_plan(value)
        self.assertEqual(result[0]['tests'][1]['name'], 'new-current')
        audit = self.root/'audit'
        self.assertTrue((audit/'acceptance_plan.json').exists())
        self.assertFalse((audit/'environment_plan.json').exists())
        sent = json.loads((audit/'prompt-provenance-0.json').read_text())
        self.assertEqual(sent['base_kind'], 'acceptance_only')
        prompt = (audit/'prompt-0.txt').read_text()
        self.assertIn('bound_environment', prompt)
        self.assertNotIn('Choose an appropriate', prompt)

    def test_observed_executable_facts_are_context_not_historical_acceptance(self):
        facts={'abi':'shared_tool_image_v2','artifact_id':'a'*64,'executable':{
            'path':'/usr/bin/obabel','version_output':'Open Babel 3.1.1 -- Jan 4 2023','sha256':'b'*64}}
        self.run_plan(self.answer(),observed_tool_identity=facts)
        material=json.loads((self.root/'audit/prompt-0.txt').read_text().split('\nINPUT\n',1)[1])
        self.assertEqual(material['observed_tool_identity'],facts)
        self.assertIsNone(material['previous_plan'])
        self.assertFalse(set(material['bound_environment']) & shared_tool.ACCEPTANCE)

    def test_model_cannot_change_environment_or_entrypoint(self):
        for field, value in [('base_image', 'other:latest'), ('entrypoint', ['echo']), ('steps', []), ('source_files', []),
                             ('observed_tool_identity', {'executable': 'model-declared'})]:
            with self.subTest(field=field):
                answer = self.answer(); answer['plan'][field] = value
                if (self.root/'handoff').exists():
                    # Each isolated fixture iteration retains its own audit files.
                    import shutil
                    shutil.rmtree(self.root/'handoff')
                with self.assertRaisesRegex(planner.PlanningError, 'Acceptance-only schema error'):
                    self.run_plan(answer)

    def test_historical_acceptance_cannot_enter_bound_base(self):
        with self.assertRaisesRegex(planner.PlanningError, 'historical acceptance'):
            planner.plan(self.root, {}, self.root/'audit', planner.options({}), None, acceptance_base=plan())

    def test_existing_guard_denies_before_any_model_call(self):
        self.request()
        def deny():
            raise RuntimeBlocked('explicit_budget', 'Existing run budget exhausted')
        with patch.object(planner.model_call, 'call', side_effect=AssertionError('No paid probe')):
            with self.assertRaisesRegex(RuntimeBlocked, 'Existing run budget'):
                planner.plan(self.root/'handoff', {}, self.root/'audit', planner.options({}), None,
                             call_guard=deny, acceptance_base=shared_tool.environment_plan(plan()))

    def test_deadline_denies_before_admission(self):
        self.request()
        with patch.object(planner.model_call, 'call', side_effect=AssertionError('No model')):
            with self.assertRaises(planner.BudgetExceeded):
                planner.plan(self.root/'handoff', {}, self.root/'audit', planner.options({}), time.monotonic()-1,
                             call_guard=lambda: self.fail('must not admit'), acceptance_base=shared_tool.environment_plan(plan()))

    def test_invalid_current_assertions_still_fail_before_freeze(self):
        self.request()
        answer = self.answer()
        case = json.loads(answer['plan']['tests'][1]['case_json']); case['acceptance']['assertion']['source_quote'] = 'invented source'
        answer['plan']['tests'][1]['case_json'] = json.dumps(case)
        with patch.object(planner.model_call, 'call', return_value=(answer, {})) as model:
            with self.assertRaises(RuntimeBlocked):
                propose(self.root/'handoff', bind(self.package, self.sources), self.root/'audit',
                        planner.options({'max_attempts': 1}), acceptance_base=shared_tool.environment_plan(plan()))
        self.assertEqual(model.call_count, 1)

    def test_material_read_rounds_consume_same_guard_budget(self):
        self.request()
        (self.root/'handoff/sources/tool/extra.txt').write_text('x'*12000)
        answer = self.answer(); answer.update(action='read', requested_files=['sources/tool/extra.txt'])
        tickets = []
        def guard():
            if tickets:
                raise RuntimeBlocked('explicit_budget', 'one admitted call only')
            ticket = {}; tickets.append(ticket); return ticket
        with patch.object(planner.model_call, 'call', return_value=(answer, {})) as model:
            with self.assertRaisesRegex(RuntimeBlocked, 'one admitted call only'):
                planner.plan(self.root/'handoff', {}, self.root/'audit', planner.options({'context_chars': 20000}),
                             time.monotonic()+30, call_guard=guard, acceptance_base=shared_tool.environment_plan(plan()))
        self.assertEqual(model.call_count, 1)
        self.assertEqual(tickets[0]['phase'], 'runtime_acceptance_planning')

    def test_provider_failure_cannot_fall_back_to_cached_tests_or_environment_planner(self):
        self.request()
        with patch.object(planner.model_call, 'call', side_effect=OSError('provider unavailable')) as model:
            with self.assertRaises(planner.ModelUnavailable):
                propose(self.root/'handoff', bind(self.package, self.sources), self.root/'audit', planner.options({}),
                        acceptance_base=shared_tool.environment_plan(plan()))
        self.assertEqual(model.call_count, 1)
        self.assertIs(model.call_args.args[1], planner.ACCEPTANCE_ONLY_SCHEMA)


if __name__ == '__main__':
    unittest.main()
