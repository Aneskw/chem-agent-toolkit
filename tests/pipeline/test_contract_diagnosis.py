"""Deterministic/fault-injection mechanisms, not model or Docker business proof."""
import copy
import json
import unittest
from unittest.mock import patch

from creation_pipeline.runtime.acceptance import consistency, ContractConflict, contracts
from creation_pipeline.runtime.diagnosis import apply_proposal, check_citations
from creation_pipeline.runtime.service import automatic_correction
from creation_pipeline.runtime.local import LocalExecutor
from creation_pipeline.artifacts import store
from tests.pipeline import test_runtime_build as fixtures


class ConsistencyTests(unittest.TestCase):
    def case(self, exact='{"answer": 2.0}', allowed=None):
        return {'name': 'arbitrary', 'stdout_equals': exact, 'acceptance': {'assertion':
            {'kind': 'json', 'path': ['answer'], 'allowed_values': [2] if allowed is None else allowed}}}

    def test_strict_type_conflict_is_located_without_coercion(self):
        result = consistency([self.case()])
        self.assertEqual(result[0]['case'], 'arbitrary')
        self.assertEqual(result[0]['field'], ['answer'])
        self.assertEqual(result[0]['assertions'], ['stdout_equals', 'acceptance.assertion'])

    def test_integer_and_float_consistency_and_distinct_calls(self):
        self.assertEqual(consistency([self.case('{"answer":2}', [2]), self.case(allowed=[2.0])]), [])
        self.assertTrue(consistency([self.case('{"answer":2}', [2.0])]))

    def test_files_and_stderr_are_distinct_channels(self):
        case = self.case(); case['output_file'] = 'value.json'
        self.assertEqual(consistency([case]), [])
        case['capture_stdout'] = True
        self.assertTrue(consistency([case]))
        case = self.case(); case['acceptance']['assertion'] = {'kind': 'stderr_contains', 'value': 'different'}
        self.assertEqual(consistency([case]), [])

    def test_jsonl_uses_bound_record_and_path(self):
        case = self.case('{"answer":2}\n{"answer":2.0}', [2])
        case['acceptance']['assertion'].update(kind='jsonl', record_index=0)
        self.assertEqual(consistency([case]), [])
        case['acceptance']['assertion']['record_index'] = 1
        self.assertTrue(consistency([case]))
        case['relation'] = {'runs': []}
        self.assertEqual(consistency([case]), [])

    def test_exact_text_conflict_and_missing_field(self):
        c = self.case('{"other":2}')
        self.assertTrue(consistency([c]))
        c['acceptance']['assertion'] = {'kind': 'stdout_equals', 'value': 'other'}
        self.assertTrue(consistency([c]))

    def test_proposal_rejects_widening_negative_and_stale_edits(self):
        c = self.case()
        plan = {'tests': [{'name': 'arbitrary', 'case_json': json.dumps(c)}]}
        edit = {'case': 'arbitrary', 'field': 'acceptance.assertion.allowed_values',
                'previous_json': '[2]', 'proposed_json': '[2.0]'}
        decision = {'edits': [edit]}
        changed = apply_proposal(plan, decision)
        self.assertEqual(json.loads(plan['tests'][0]['case_json'])['acceptance']['assertion']['allowed_values'], [2])
        self.assertIs(type(json.loads(changed['tests'][0]['case_json'])['acceptance']['assertion']['allowed_values'][0]), float)
        for proposed in ('[2,2.0]', '[2]', '[]'):
            with self.assertRaises(ValueError):
                apply_proposal(plan, {'edits': [dict(edit, proposed_json=proposed)]})
        c['acceptance']['purpose'] = 'input_rejection'
        with self.assertRaises(ValueError):
            apply_proposal({'tests': [{'name': 'arbitrary', 'case_json': json.dumps(c)}]}, decision)
        with self.assertRaises(ValueError):
            apply_proposal(plan, {'edits': []})


class DiagnosisTests(unittest.TestCase):
    setUp = fixtures.RuntimeBuildTests.setUp
    tearDown = fixtures.RuntimeBuildTests.tearDown
    prepared = fixtures.RuntimeBuildTests.prepared

    def test_missing_or_invented_source_cannot_authorize_correction(self):
        with self.assertRaises(ValueError):
            check_citations([], self.sources)
        with self.assertRaises(ValueError):
            check_citations([{'source_id': 'tool', 'path': 'main.py', 'quote': 'imagined output'}], self.sources)

    def test_unknown_diagnosis_stops_and_is_durable_without_author_or_execute(self):
        self.prepared()
        answer = {'attribution': 'unknown', 'reason': 'Ambiguous source', 'why_not_source_change': '',
                  'unchanged_scope': 'all', 'citations': [], 'edits': []}
        with patch('creation_pipeline.runtime.diagnosis.model_call.call', return_value=(answer, {})) as model, \
             patch('creation_pipeline.runtime.service.execute_prepared', side_effect=AssertionError('No execution')), \
             patch('creation_pipeline.pipeline._candidate', side_effect=AssertionError('No author')):
            first = automatic_correction(self.root/'output', self.record, {}, {}, LocalExecutor())
            second = automatic_correction(self.root/'output', self.record, {}, {}, LocalExecutor())
        self.assertEqual(model.call_count, 1)
        self.assertEqual(first['status'], 'review_required')
        self.assertIn('already attempted', second['reason'])
        store.adopt(self.root/'output', [self.record], {'batch': {}, 'revision_parents': {}}, self.root/'lib')
        entry = store.get(self.root/'lib', 'probe', include_candidates=True)
        self.assertEqual(entry['zone'], 'candidates')
        self.assertTrue((self.root/'lib'/entry['runtime_diagnosis']['path']/'outcome.json').exists())

    def test_content_diagnosis_cannot_modify_correct_contract(self):
        self.prepared()
        before = copy.deepcopy(self.record['delivery'])
        answer = {'attribution': 'content', 'reason': 'Source/call mismatch', 'why_not_source_change': '',
            'unchanged_scope': 'all', 'citations': [{'source_id': 'tool', 'path': 'main.py', 'quote': 'print("ok")'}], 'edits': []}
        with patch('creation_pipeline.runtime.diagnosis.model_call.call', return_value=(answer, {})), \
             patch('creation_pipeline.runtime.service.approve_correction', side_effect=AssertionError('Not a contract error')):
            result = automatic_correction(self.root/'output', self.record, {}, {}, LocalExecutor())
        self.assertEqual(result['attribution'], 'content')
        self.assertEqual(result['next_action'], 'author_repair_and_independent_review')
        self.assertEqual(self.record['delivery'], before)

    def test_independent_rejection_preserves_revision_and_prevents_execution(self):
        self.prepared()
        before = copy.deepcopy(self.record['delivery'])
        correction = {'attribution': 'contract', 'reason': 'Claimed correction',
            'citations': [{'source_id': 'tool', 'path': 'main.py', 'quote': 'print("ok")'}]}
        with patch('creation_pipeline.runtime.diagnosis.diagnose', return_value=(correction,
                   before['inputs']['environment']['payload']['plan'], self.root/'review-work')), \
             patch('creation_pipeline.runtime.review.review_snapshot', return_value={'review': {
                 'status': 'fail', 'oracle_changes_verified': False, 'requirement_assessment': 'confirmed'}}), \
             patch('creation_pipeline.runtime.service.execute_prepared', side_effect=AssertionError('No execution')):
            result = automatic_correction(self.root/'output', self.record, {}, {}, LocalExecutor())
        self.assertEqual(result['status'], 'review_required')
        self.assertIn('did not confirm', result['reason'])
        self.assertEqual(self.record['delivery'], before)

    def test_remove_patch_value_is_unused_but_invalid_path_and_test_edits_rejected(self):
        from creation_pipeline.runtime.planner import patch_plan, PlanningError
        from tests.pipeline.test_runtime_build import plan
        p = plan(); p['steps'] = [{'command': 'exit 37', 'purpose': 'injected', 'evidence': 'fixture'}]
        answer = {'action': 'patch', 'requested_files': [], 'reason': 'remove fault',
                  'operations': [{'op': 'remove', 'path': '/steps/0', 'value_json': ''}]}
        self.assertEqual(patch_plan(p, answer, True)['steps'], [])
        for path in ('/steps/0/', '/tests/0'):
            bad = copy.deepcopy(answer); bad['operations'][0]['path'] = path
            with self.assertRaises(PlanningError):
                patch_plan(p, bad, True)

    def test_patch_structured_value_for_a_json_text_field_is_encoded(self):
        """JSON-text plan fields accept the object form; other fields stay strict.

        Before this guard an object written into acceptance_json reached json.loads()
        as a dict and the TypeError escaped the whole build instead of asking for a
        repair. The value is now encoded, and a wrong type elsewhere is still an
        invalid patch.
        """
        from creation_pipeline.runtime import planner
        from tests.pipeline.test_runtime_build import plan
        base = plan()
        policy = dict(json.loads(base['acceptance_json']), note='example')
        for path, payload in (('/acceptance_json', policy),
                              ('/tests/0/case_json', {'args': ['x']})):
            answer = {'action': 'patch', 'requested_files': [], 'reason': 'structured',
                      'operations': [{'op': 'replace', 'path': path,
                                      'value_json': json.dumps(payload)}]}
            applied = planner.patch_plan(base, answer, False)
            stored = (applied['acceptance_json'] if path == '/acceptance_json'
                      else applied['tests'][0]['case_json'])
            self.assertIsInstance(stored, str, path)
            self.assertEqual(json.loads(stored), payload)
        with self.assertRaises(planner.PlanningError) as caught:
            planner.patch_plan(base, {'action': 'patch', 'requested_files': [], 'reason': 'bad type',
                                      'operations': [{'op': 'replace', 'path': '/output_contract',
                                                      'value_json': '{"a": 1}'}]}, False)
        self.assertIn('is not of type', str(caught.exception))
        text = {'action': 'patch', 'requested_files': [], 'reason': 'text',
                'operations': [{'op': 'replace', 'path': '/output_contract',
                                'value_json': '"stdout"'}]}
        self.assertEqual(planner.patch_plan(base, text, False)['output_contract'], 'stdout')

    def test_patch_feedback_is_specific_and_repeated_error_stops(self):
        from creation_pipeline.runtime import planner
        from tests.pipeline.test_runtime_build import plan
        p = plan(); p['steps'] = [{'command': 'exit 37', 'purpose': 'injected', 'evidence': 'fixture'}]
        answer = {'action': 'patch', 'requested_files': [], 'reason': 'remove fault',
                  'operations': [{'op': 'remove', 'path': '/steps/0/', 'value_json': ''}]}
        with patch.object(planner.model_call, 'call', return_value=(answer, {})) as model:
            with self.assertRaisesRegex(planner.PlanningError, 'No progress'):
                planner.plan(self.source, {'script': 'main.py'}, self.root/'patch-audit', planner.options({}), None, previous=p)
        self.assertEqual(model.call_count, 2)
        self.assertIn('patch_error', model.call_args.args[0])
        self.assertTrue((self.root/'patch-audit/patch-rejection-0.json').exists())

    def test_explicit_diagnosis_budget_blocks_before_model(self):
        self.prepared()
        with patch('creation_pipeline.runtime.diagnosis.model_call.call', side_effect=AssertionError('Budget forbids model')):
            result = automatic_correction(self.root/'output', self.record, {'options': {'context_chars': 1}}, {}, LocalExecutor())
        self.assertEqual(result['status'], 'review_required')
        self.assertIn('context limit', result['reason'])

    def test_production_infinite_deadline_does_not_create_a_quota_or_overflow(self):
        self.prepared()
        answer = {'attribution': 'unknown', 'reason': 'Source ambiguous', 'why_not_source_change': '',
                  'unchanged_scope': 'all', 'citations': [], 'edits': []}
        calls = []
        with patch('creation_pipeline.runtime.diagnosis.model_call.call', return_value=(answer, {})):
            result = automatic_correction(self.root/'output', self.record, {}, {},
                                          LocalExecutor(deadline=float('inf')), lambda: calls.append('model'))
        self.assertEqual(calls, ['model'])
        self.assertEqual(result['reason'], 'Source ambiguous')

    def test_author_repair_history_carries_diagnosis_into_library(self):
        from creation_pipeline.artifacts.package import manifest
        self.prepared()
        output = self.root/'output'
        (output/'attempt').mkdir(); (output/'attempt/log.txt').write_text('injected historical attempt')
        (output/'diagnosis').mkdir(); (output/'diagnosis/decision.json').write_text('{"attribution":"content"}')
        prior = {k: copy.deepcopy(self.record[k]) for k in ('delivery', 'durable_evidence')}
        prior['runtime'] = {'path': 'attempt', 'files': manifest(output/'attempt')}
        prior['runtime_diagnosis'] = {'path': 'diagnosis', 'files': manifest(output/'diagnosis')}
        self.record['runtime_history_records'] = [prior]
        # This double tests reference transfer, not execution validity (covered separately).
        with patch('creation_pipeline.runtime.service.verify_attempt', return_value={}):
            store.adopt(output, [self.record], {'batch': {}}, self.root/'lib')
        entry = store.get(self.root/'lib', 'probe', include_candidates=True)
        ref = entry['history'][0]['runtime_diagnosis']
        self.assertEqual(manifest(self.root/'lib'/ref['path']), ref['files'])
        self.assertFalse(entry['current_qualification']['accepted'])


if __name__ == '__main__':
    unittest.main()
