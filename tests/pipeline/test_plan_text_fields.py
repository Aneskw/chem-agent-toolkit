"""A full plan accepts the same JSON-text encodings as a patch.

``acceptance_json`` and ``tests[].case_json`` are text fields. The patch protocol has
always accepted the object/array form and encoded it; a full plan did not, so the same
content was a schema error in the plan path and valid in the patch path (run 12 died
on exactly that). Only the encoding is normalized: the semantic gates still judge the
content, including an invalid ``invalid_input`` state.
"""
import copy
import json
import unittest

from creation_pipeline.runtime import planner
from tests.pipeline.test_runtime_build import plan

POLICY = {'invalid_input': 'not_applicable', 'scope': 'fixed report',
          'purposes': ['report'], 'source_path': 'sources/tool/main.py',
          'source_quote': 'print("ok")'}


class FullPlanEncodingTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan()

    def test_the_object_form_is_encoded_for_a_full_plan(self):
        p = copy.deepcopy(self.plan)
        p['acceptance_json'] = dict(POLICY)
        normalized = planner.normalize_text_fields(p)
        self.assertIsInstance(normalized['acceptance_json'], str)
        self.assertEqual(json.loads(normalized['acceptance_json']), POLICY)

    def test_case_json_objects_are_encoded_for_a_full_plan(self):
        p = copy.deepcopy(self.plan)
        p['tests'][0]['case_json'] = {'args': ['x'], 'expected_exit': 0}
        normalized = planner.normalize_text_fields(p)
        self.assertIsInstance(normalized['tests'][0]['case_json'], str)
        self.assertEqual(json.loads(normalized['tests'][0]['case_json']),
                         {'args': ['x'], 'expected_exit': 0})

    def test_text_fields_are_left_untouched(self):
        p = copy.deepcopy(self.plan)
        before = p['tests'][0]['case_json']
        planner.normalize_text_fields(p)
        self.assertEqual(p['tests'][0]['case_json'], before)

    def test_a_non_json_text_field_is_still_an_error(self):
        p = copy.deepcopy(self.plan)
        p['acceptance_json'] = 'not json'
        with self.assertRaises(planner.PlanningError) as caught:
            planner.normalize_text_fields(p)
        self.assertIn('must hold JSON text', str(caught.exception))

    def test_an_invalid_state_is_still_rejected_semantically(self):
        # The encoding fix must not accept a boolean state: the policy gate decides.
        import tempfile
        from pathlib import Path
        from creation_pipeline.runtime.acceptance import contracts
        bad = dict(POLICY, invalid_input=True)
        root = Path(tempfile.mkdtemp())
        (root / 'sources/tool').mkdir(parents=True)
        (root / 'sources/tool/main.py').write_text('# quote\nprint("ok")\n', encoding='utf-8')
        index = {'files': {'sources/tool/main.py': {'sha256': '0' * 64}},
                 'read_files': ['sources/tool/main.py']}
        with self.assertRaises(ValueError) as caught:
            contracts({'acceptance_json': json.dumps(bad)}, [], index, root)
        self.assertIn('quotation', str(caught.exception))

    def test_a_declared_contract_needs_a_valid_state(self):
        import tempfile
        from pathlib import Path
        from creation_pipeline.runtime.acceptance import contracts
        bad = dict(POLICY, invalid_input='probably',
                   input_contract={'status': 'probably', 'reason': 'r'})
        root = Path(tempfile.mkdtemp())
        (root / 'sources/tool').mkdir(parents=True)
        (root / 'sources/tool/main.py').write_text('# quote\nprint("ok")\n', encoding='utf-8')
        index = {'files': {'sources/tool/main.py': {'sha256': '0' * 64}},
                 'read_files': ['sources/tool/main.py']}
        with self.assertRaises(ValueError) as caught:
            contracts({'acceptance_json': json.dumps(bad)}, [], index, root)
        self.assertIn('none_documented', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
