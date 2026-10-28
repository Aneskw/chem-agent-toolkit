"""The policy's executable examples must parse, and must agree with the real validators.

The examples are rendered by ``planner.json_text`` (json.dumps) instead of being
hand-written, because hand-written multi-level escaping produced examples that were
themselves invalid JSON. These tests fail if an example drifts from the gate.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from creation_pipeline.runtime import planner
from creation_pipeline.runtime.acceptance import contracts
from tests.pipeline.test_runtime_build import plan

EX = planner.FIXTURE_EXAMPLES
CASE_SCHEMA = planner.PLAN_SCHEMA['properties']['plan']['properties']['tests']['items']['properties']['case_json']
ASSERTIONS = ('stdout_equals', 'stdout_contains', 'expected_json_lines', 'relation')


class PolicyExampleTests(unittest.TestCase):
    def test_every_example_is_rendered_verbatim_into_the_policy(self):
        for name, example in EX.items():
            self.assertIn(planner.json_text(example), planner.POLICY, name)

    def test_every_rendered_example_is_valid_json(self):
        for name, example in EX.items():
            with self.subTest(name):
                self.assertEqual(json.loads(planner.json_text(example)), example)

    def test_case_json_accepts_both_encodings(self):
        # The plan schema accepts text or the object; the object is normalised into
        # text before the plan checks, and the text form decodes to the same case.
        wrong = EX['case_json_object']
        right = EX['case_json_text']
        for value, name in ((wrong, 'object'), (right, 'text')):
            jsonschema.validate(value, {'type': 'object', 'properties': {'case_json': CASE_SCHEMA},
                                        'required': ['case_json']})
        normalised = planner.normalize_text_fields(
            {'acceptance_json': {'purposes': ['report']},
             'tests': [copy.deepcopy(wrong)]})
        self.assertEqual(json.loads(normalised['tests'][0]['case_json']),
                         {'args': ['CCCOCCC'], 'stdout_equals': '[]'})
        self.assertIsInstance(normalised['acceptance_json'], str)
        planner.check_case(json.loads(right['case_json']))

    def test_the_nested_json_text_decodes_twice(self):
        right = EX['case_json_text']
        self.assertEqual(json.loads(json.loads(planner.json_text(right))['case_json']),
                         {'args': ['CCCOCCC'], 'stdout_equals': '[]'})

    def test_capture_stdout_examples_match_the_fixture_gate(self):
        for name in ('capture_stdout_no_file', 'capture_stdout_string'):
            with self.assertRaises(planner.PlanningError, msg=name):
                planner.check_case(dict(EX[name]))
        planner.check_case(dict(EX['capture_stdout_ok']))

    def test_exit_code_only_case_carries_no_assertion(self):
        case = EX['behavior_exit_only']
        self.assertFalse(any(key in case for key in ASSERTIONS))
        self.assertIsNone(case.get('entrypoint'))
        # That is exactly the condition validate_plan rejects for a supported
        # behavior oracle; the example shows what it looks like.

    def _index_and_source(self, text='SMILES'):
        directory = tempfile.mkdtemp(prefix='policy-example-')
        path = Path(directory) / 'doc.txt'
        path.write_text(text, encoding='utf-8', newline='\n')
        index = {'files': {'doc.txt': {'size': path.stat().st_size}},
                 'read_files': ['doc.txt']}
        return index, Path(directory)

    def _policy_plan(self, selector):
        policy = {
            'invalid_input': 'not_applicable', 'scope': 'demo CLI', 'purposes': ['computation'],
            'source_path': 'doc.txt', 'source_quote': 'SMILES',
            'checks': [{'id': 'c1', 'channel': 'args', 'key': 0, 'pattern': 'SMILES',
                        'mode': 'full_text', 'source_path': 'doc.txt', 'source_quote': 'SMILES'}],
            'operations': [{'id': 'cli', 'selector': {'args': [selector]}, 'checks': ['c1'],
                            'purposes': ['computation'], 'require_persistence': False,
                            'source_path': 'doc.txt', 'source_quote': 'SMILES'}],
        }
        return {'acceptance_json': json.dumps(policy)}

    def test_selector_examples_are_checked_by_the_real_acceptance_gate(self):
        index, source = self._index_and_source()
        good = EX['selector_literal']['args'][0]
        bad = EX['selector_regex']['args'][0]
        contracts(self._policy_plan(good), [], index, source)
        with self.assertRaises(ValueError) as caught:
            contracts(self._policy_plan(bad), [], index, source)
        self.assertIn('literal documented invocation token', str(caught.exception))

    def test_patch_examples_go_through_the_real_patch_validator(self):
        base = plan()
        def patch(example):
            return {'action': 'patch', 'requested_files': [], 'reason': 'example',
                    'operations': [dict(example)]}
        with self.assertRaises(planner.PlanningError):
            planner.patch_plan(base, patch(EX['patch_bare_word']), False)
        applied = planner.patch_plan(base, patch(EX['patch_text_value']), False)
        self.assertEqual(applied['output_contract'], 'stdout')
        applied = planner.patch_plan(base, patch(EX['patch_case_text']), False)
        case = json.loads(applied['tests'][0]['case_json'])
        self.assertEqual(case, {'args': ['CCCOCCC'], 'stdout_equals': '[]'})
        planner.check_case(case)

    def test_no_hand_written_double_quotes_remain(self):
        # The regression that motivated the rewrite produced these shapes. A correct
        # example legitimately starts with '{"case_json": "{', so only the
        # unambiguously broken forms are asserted absent.
        for artefact in ('""stdout""', 'value_json:"', '{path:"', 'selector:{', '[{choice: x}]'):
            self.assertNotIn(artefact, planner.POLICY)


if __name__ == '__main__':
    unittest.main()
