"""Patch encoding for the plan fields whose schema type is JSON text.

Only ``acceptance_json`` and ``tests[].case_json`` are JSON text. The patch validator
encodes a structured value for exactly those, in every shape a pointer can address
(single field, one test, a whole ``/tests`` array, append), and keeps every other
field strict.
"""
import copy
import json
import unittest

from creation_pipeline.runtime import planner
from tests.pipeline.test_runtime_build import plan

CASE = {'args': ['CCCOCCC'], 'stdout_equals': '[]'}


def answer(path, value_json, op='replace'):
    return {'action': 'patch', 'requested_files': [], 'reason': 'encoding',
            'operations': [{'op': op, 'path': path, 'value_json': value_json}]}


def patch(base, path, value_json, op='replace', locked=False):
    return planner.patch_plan(base, answer(path, value_json, op), locked)


class TextFieldEncodingTests(unittest.TestCase):
    def setUp(self):
        self.base = plan()

    def test_incomplete_resource_replacement_names_schema_object_and_keeps_base(self):
        before = copy.deepcopy(self.base)
        with self.assertRaises(planner.PlanningError) as caught:
            patch(self.base, '/resource_assessment', json.dumps({'status': 'unknown'}))
        self.assertIn('/plan/resource_assessment', str(caught.exception))
        self.assertIn("'source_path' is a required property", str(caught.exception))
        self.assertEqual(self.base, before)

    def test_case_json_accepts_the_object_form_and_stores_text(self):
        applied = patch(self.base, '/tests/0/case_json', json.dumps(CASE))
        stored = applied['tests'][0]['case_json']
        self.assertIsInstance(stored, str)
        self.assertEqual(json.loads(stored), CASE)
        planner.check_case(json.loads(stored))

    def test_case_json_accepts_the_double_encoded_text_form(self):
        applied = patch(self.base, '/tests/0/case_json', json.dumps(json.dumps(CASE)))
        self.assertEqual(json.loads(applied['tests'][0]['case_json']), CASE)

    def test_acceptance_json_object_form_is_encoded(self):
        policy = dict(json.loads(self.base['acceptance_json']), note='example')
        applied = patch(self.base, '/acceptance_json', json.dumps(policy))
        self.assertIsInstance(applied['acceptance_json'], str)
        self.assertEqual(json.loads(applied['acceptance_json']), policy)

    def test_a_whole_tests_array_is_encoded_element_by_element(self):
        tests = copy.deepcopy(self.base['tests'])
        for test in tests:
            test['case_json'] = {'args': ['x']}
        applied = patch(self.base, '/tests', json.dumps(tests))
        for test in applied['tests']:
            self.assertIsInstance(test['case_json'], str)
            self.assertEqual(json.loads(test['case_json']), {'args': ['x']})
        planner.check_case(json.loads(applied['tests'][0]['case_json']))

    def test_one_replaced_test_object_is_encoded(self):
        test = copy.deepcopy(self.base['tests'][0])
        test['case_json'] = dict(CASE)
        applied = patch(self.base, '/tests/0', json.dumps(test))
        self.assertIsInstance(applied['tests'][0]['case_json'], str)
        self.assertEqual(json.loads(applied['tests'][0]['case_json']), CASE)

    def test_an_appended_test_is_encoded(self):
        test = copy.deepcopy(self.base['tests'][0])
        test['name'] = 'appended-case'
        test['case_json'] = dict(CASE)
        applied = patch(self.base, '/tests/-', json.dumps(test), op='add')
        self.assertEqual(applied['tests'][-1]['name'], 'appended-case')
        self.assertEqual(json.loads(applied['tests'][-1]['case_json']), CASE)

    def test_text_values_are_kept_unchanged(self):
        applied = patch(self.base, '/tests/0/case_json', json.dumps(CASE))
        again = patch(applied, '/tests/0/case_json',
                      json.dumps(applied['tests'][0]['case_json']))
        self.assertEqual(again['tests'][0]['case_json'], applied['tests'][0]['case_json'])

    def test_invalid_json_text_for_a_text_field_is_an_invalid_patch(self):
        with self.assertRaises(planner.PlanningError) as caught:
            patch(self.base, '/tests/0/case_json', json.dumps('not json'))
        self.assertIn('must hold JSON text', str(caught.exception))

    def test_a_non_text_field_still_rejects_structured_values(self):
        for path, value in (('/output_contract', {'a': 1}),
                            ('/tests/0/name', {'n': 'x'}),
                            ('/tests/0/layer', ['environment'])):
            with self.assertRaises(planner.PlanningError, msg=path) as caught:
                patch(self.base, path, json.dumps(value))
            self.assertIn('is not of type', str(caught.exception), path)

    def test_locked_repairs_still_cannot_touch_tests_or_acceptance(self):
        for path in ('/tests', '/acceptance_json', '/tests/0/case_json',
                     '/acceptance_json/purposes/0', '/tests/0/case_json/args/0'):
            with self.assertRaises(planner.PlanningError, msg=path) as caught:
                patch(self.base, path, json.dumps('report'), locked=True)
            self.assertIn('locked', str(caught.exception).lower())

    def test_a_pre_lock_repair_may_withdraw_its_own_draft_test(self):
        # A rejected candidate is not accepted evidence: the model may take back a
        # promise instead of stretching it, and the withdrawal is recorded.
        tests = copy.deepcopy(self.base['tests'])[1:]
        withdrawn = self.base['tests'][0]['name']
        applied = patch(self.base, '/tests', json.dumps(tests))
        self.assertEqual([t['name'] for t in applied['tests']], [t['name'] for t in tests])
        self.assertEqual(planner.scope_delta(self.base, applied), {'tests': [withdrawn]})

    def test_a_pre_lock_repair_cannot_withdraw_or_change_an_external_case(self):
        tests = copy.deepcopy(self.base['tests'])
        required = tests[1]['name']
        with self.assertRaises(planner.PlanningError) as caught:
            planner.patch_plan(self.base, answer('/tests', json.dumps(tests[:1])), False, [required])
        self.assertIn('cannot remove required cases: ' + required, str(caught.exception))
        changed = copy.deepcopy(tests)
        changed[1]['basis'] = 'rewritten to fit the observed output'
        with self.assertRaises(planner.PlanningError) as caught:
            planner.patch_plan(self.base, answer('/tests', json.dumps(changed)), False, [required])
        self.assertIn('cannot change required cases: ' + required, str(caught.exception))

    def test_a_locked_repair_still_cannot_withdraw_a_promised_test(self):
        tests = copy.deepcopy(self.base['tests'])[1:]
        with self.assertRaises(planner.PlanningError) as caught:
            patch(self.base, '/tests', json.dumps(tests), locked=True)
        self.assertIn('locked', str(caught.exception).lower())

    def test_a_removal_needs_no_value_and_add_replace_do(self):
        removed = {'action': 'patch', 'requested_files': [], 'reason': 'drop',
                   'operations': [{'op': 'remove', 'path': '/tests/1'}]}
        applied = planner.patch_plan(self.base, removed, False)
        self.assertEqual([t['name'] for t in applied['tests']], ['environment'])
        for operation in ({'op': 'replace', 'path': '/output_contract'},
                          {'op': 'add', 'path': '/unresolved/-'}):
            answer = {'action': 'patch', 'requested_files': [], 'reason': 'x', 'operations': [operation]}
            with self.assertRaises(planner.PlanningError, msg=operation['op']) as caught:
                planner.patch_plan(self.base, answer, False)
            self.assertIn('value_json is required for op=' + operation['op'], str(caught.exception))

    def test_the_patched_plan_must_still_satisfy_the_plan_schema(self):
        applied = patch(self.base, '/tests/0/case_json', json.dumps(CASE))
        self.assertIn('tests', applied)
        # A missing required plan field is still rejected, coercion or not.
        bad = copy.deepcopy(self.base)
        bad.pop('base_image')
        with self.assertRaises(planner.PlanningError):
            patch(bad, '/tests/0/case_json', json.dumps(CASE))


class NestedTextPatchTests(unittest.TestCase):
    """A pointer may continue inside the decoded JSON document of a text field."""

    def setUp(self):
        self.base = plan()

    def policy(self, plan_):
        return json.loads(plan_['acceptance_json'])

    def test_check_objects_are_rejected_before_scope_audit(self):
        policy = dict(self.policy(self.base), checks=[{'id': 'nonempty'}],
                      operations=[{'id': 'direct-smiles', 'checks': ['nonempty'], 'purposes': ['report']}])
        seeded = patch(self.base, '/acceptance_json', json.dumps(policy))
        with self.assertRaises(planner.PlanningError) as caught:
            patch(seeded, '/acceptance_json/operations/0/checks', json.dumps([{'id': 'nonempty'}]))
        for expected in ('Operation direct-smiles', 'acceptance_json.checks', 'strings'):
            self.assertIn(expected, str(caught.exception))
        # Invalid proposed data never mutates the base used by the next repair.
        self.assertEqual(self.policy(seeded)['operations'][0]['checks'], ['nonempty'])

    def test_unhashable_nested_contract_fields_are_clean_patch_rejections(self):
        for field, value in (('purposes', [{}]), ('checks', [{'id': {}}]),
                             ('operations', [{'id': {}, 'checks': []}]),
                             ('input_contract', {'status': {}}), ('invalid_input', {})):
            with self.subTest(field=field):
                policy = dict(self.policy(self.base), **{field: value})
                with self.assertRaises(planner.PlanningError):
                    patch(self.base, '/acceptance_json', json.dumps(policy))

    def test_one_policy_purpose_is_edited_without_resending_the_policy(self):
        applied = patch(self.base, '/acceptance_json/purposes/0', json.dumps('operation'))
        policy = self.policy(applied)
        self.assertEqual(policy['purposes'], ['operation'])
        # Everything else in the document is untouched.
        self.assertEqual(policy['scope'], self.policy(self.base)['scope'])
        self.assertIsInstance(applied['acceptance_json'], str)
        self.assertEqual(applied['acceptance_json'],
                         planner.json_text(dict(self.policy(self.base), purposes=['operation'])))

    def test_one_check_and_one_selector_edit_inside_an_operation(self):
        policy = dict(self.policy(self.base),
                      checks=[{'id': 'c1', 'description': 'report', 'source_path': 'x', 'source_quote': 'q'},
                              {'id': 'c2', 'description': 'other', 'source_path': 'x', 'source_quote': 'q'}],
                      operations=[{'id': 'o1', 'purposes': ['report'], 'checks': ['c1', 'c2']}])
        seeded = patch(self.base, '/acceptance_json', json.dumps(policy))
        edited = patch(seeded, '/acceptance_json/operations/0/checks/0', json.dumps('c2'))
        self.assertEqual(self.policy(edited)['operations'][0]['checks'], ['c2', 'c2'])
        self.assertEqual(self.policy(edited)['checks'], policy['checks'])

    def test_one_fixture_expectation_is_edited_without_resending_the_fixture(self):
        applied = patch(self.base, '/tests/1/case_json/stdout_equals', json.dumps('[]'))
        case = json.loads(applied['tests'][1]['case_json'])
        self.assertEqual(case['stdout_equals'], '[]')
        self.assertEqual(case['expected_exit'], 0)
        self.assertIn('acceptance', case)
        planner.check_case(case)

    def test_one_fixture_argument_is_edited_by_index(self):
        applied = patch(self.base, '/tests/1/case_json/args/-', json.dumps('extra'), op='add')
        self.assertEqual(json.loads(applied['tests'][1]['case_json'])['args'], ['extra'])
        applied = patch(applied, '/tests/1/case_json/args/0', json.dumps('replaced'))
        self.assertEqual(json.loads(applied['tests'][1]['case_json'])['args'], ['replaced'])

    def test_a_nested_key_can_be_added_and_removed(self):
        added = patch(self.base, '/tests/1/case_json/stdout_contains', json.dumps(['ok']), op='add')
        self.assertEqual(json.loads(added['tests'][1]['case_json'])['stdout_contains'], ['ok'])
        removed = patch(added, '/tests/1/case_json/stdout_contains', '', op='remove')
        self.assertNotIn('stdout_contains', json.loads(removed['tests'][1]['case_json']))

    def test_an_out_of_range_nested_pointer_is_an_invalid_patch(self):
        with self.assertRaises(planner.PlanningError) as caught:
            patch(self.base, '/tests/0/case_json/args/9', json.dumps('x'))
        self.assertIn('Invalid plan patch', str(caught.exception))
        with self.assertRaises(planner.PlanningError):
            patch(self.base, '/tests/9/case_json/args', json.dumps(['x']))

    def test_a_nested_pointer_into_a_scalar_is_an_invalid_patch(self):
        with self.assertRaises(planner.PlanningError) as caught:
            patch(self.base, '/tests/0/basis/x', json.dumps('x'))
        self.assertIn('Invalid plan patch', str(caught.exception))

    def test_a_nested_edit_is_all_or_nothing(self):
        before = copy.deepcopy(self.base)
        answer_ = {'action': 'patch', 'requested_files': [], 'reason': 'batch', 'operations': [
            {'op': 'replace', 'path': '/tests/0/case_json/stdout_equals', 'value_json': json.dumps('new')},
            {'op': 'replace', 'path': '/tests/0/case_json/args/7', 'value_json': json.dumps('x')}]}
        with self.assertRaises(planner.PlanningError):
            planner.patch_plan(self.base, answer_, False)
        # Neither the source plan nor the first edit leaks out of the failed patch.
        self.assertEqual(self.base, before)
        self.assertEqual(json.loads(before['tests'][0]['case_json'])['args'], ['--version'])

    def test_the_input_plan_is_never_mutated_by_a_successful_patch(self):
        before = copy.deepcopy(self.base)
        patch(self.base, '/tests/0/case_json/args/0', json.dumps('--help'))
        patch(self.base, '/acceptance_json/purposes/0', json.dumps('operation'))
        self.assertEqual(self.base, before)


if __name__ == '__main__':
    unittest.main()
