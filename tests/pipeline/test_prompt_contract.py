"""The prompt must state exactly the contract the validators enforce.

This is the regression guard for the failure mode "the validator requires something
the model was never told": it builds the real strings (POLICY, the patch protocol, the
schema descriptions, the frozen copies) and requires every new field and state to be
stated, while no superseded two-state wording may survive.
"""
import importlib.util
import json
import unittest
from pathlib import Path

from creation_pipeline.runtime import acceptance, planner

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / 'validation/deepseek-api/verify_prompt_contract.py'


def load_audit():
    spec = importlib.util.spec_from_file_location('verify_prompt_contract', SPEC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PromptContractTests(unittest.TestCase):
    def setUp(self):
        self.audit = load_audit()
        self.parts = self.audit.surfaces()

    def test_every_surface_is_consistent_with_the_validators(self):
        problems = self.audit.audit(self.parts)
        self.assertEqual(problems, [], '\n'.join(problems))

    def test_the_description_names_every_state_and_required_field(self):
        description = planner.ACCEPTANCE_SPEC
        for state in acceptance.INPUT_STATES:
            self.assertIn(state, description)
            for field in acceptance.CONTRACT_FIELDS[state]:
                self.assertIn(field, description, state + '.' + field)
        for field in acceptance.CONTRACT_LINKAGE:
            self.assertIn(field, description)

    def test_the_policy_names_the_states_and_points_at_the_description(self):
        self.assertIn(', '.join(acceptance.INPUT_STATES), planner.POLICY)
        self.assertIn('acceptance_json schema description', planner.POLICY)

    def test_the_patch_protocol_states_the_repair_rules(self):
        for locked in (True, False):
            text = planner.patch_protocol(locked)
            self.assertIn('PATCH PROTOCOL', text)
            self.assertIn('/acceptance_json/<pointer>', text)
            self.assertIn('by supplying that recorded evidence', text)
            self.assertIn('no repair may touch a locked acceptance contract', text)
        self.assertIn('LOCKED', planner.patch_protocol(True))
        self.assertIn('rejected candidate', planner.patch_protocol(False))

    def test_no_superseded_two_state_wording_survives(self):
        for where, text in self.parts.items():
            for needle in ('invalid_input (required or',
                           'All listed operations require normal business cases'):
                self.assertNotIn(needle, text, where)

    def test_the_schemas_sent_to_a_provider_carry_the_description(self):
        for schema in (planner.PLAN_SCHEMA, planner.PATCH_SCHEMA):
            serialized = json.dumps(schema, ensure_ascii=False)
            self.assertIn('none_documented', serialized)
            self.assertIn('checked:[{source_path, sha256}]', serialized)

    def test_the_repair_feedback_asks_for_the_missing_evidence(self):
        for text in self.audit.repair_feedback():
            if 'cannot downgrade' in text:
                self.assertIn('evidence', text)
                for field in acceptance.CONTRACT_FIELDS['none_documented']:
                    self.assertIn(field, text)


if __name__ == '__main__':
    unittest.main()
