"""The acceptance path builds prompts/schemas from current code and records them.

The small frozen fixture is an offline diagnostic, not what a formal batch sends. This
guard proves the three claims independently:

* production never reads a frozen copy,
* the round prompt/schema come from the live module objects, including the current
  acceptance description,
* the bytes a round would send are identified, and the saved RECAP case reproduces its
  recorded round-0 prompt through the real ``planner.plan`` path (aborted before the
  model call, so no request is made).
"""
import importlib.util
import json
import unittest
from pathlib import Path

from creation_pipeline.runtime import planner

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / 'validation/deepseek-api/verify_acceptance_prompt.py'


def load_verifier():
    spec = importlib.util.spec_from_file_location('verify_acceptance_prompt', SPEC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PromptProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verify = load_verifier()

    def test_production_never_reads_a_frozen_copy(self):
        self.assertEqual(self.verify.production_references(), [])

    def test_the_round_schema_and_policy_are_the_live_objects(self):
        self.assertIs(planner.schema_for('none'), planner.PLAN_SCHEMA)
        self.assertIs(planner.schema_for('rejected_candidate'), planner.PATCH_SCHEMA)
        self.assertIs(planner.schema_for('accepted_plan'), planner.PATCH_SCHEMA)
        self.assertEqual(planner.policy_for('none'), planner.POLICY)
        for kind in ('rejected_candidate', 'accepted_plan'):
            self.assertIn('PATCH PROTOCOL', planner.policy_for(kind))
        node = planner.PLAN_SCHEMA['properties']['plan']['properties']['acceptance_json']
        self.assertEqual(node['description'], planner.ACCEPTANCE_SPEC)
        self.assertEqual(planner.PATCH_SCHEMA['description'], planner.ACCEPTANCE_SPEC)
        self.assertEqual(self.verify.identity_problems(), [])

    def test_the_recorded_provenance_matches_the_current_code(self):
        problems = self.verify.check(verbose=False)
        self.assertEqual(problems, [], '\n'.join(problems))
        recorded = json.loads((ROOT / 'validation/deepseek-api/prompt-provenance.json')
                              .read_text(encoding='utf-8'))
        self.assertEqual(recorded['code']['policy_sha256'],
                         self.verify.sha256(planner.POLICY))
        self.assertEqual(recorded['code']['acceptance_spec_sha256'],
                         self.verify.sha256(planner.ACCEPTANCE_SPEC))
        self.assertEqual(recorded['rounds']['none']['prompt_sha256'],
                         planner.provenance(self.verify.fixture_material(), 'none')['prompt_sha256'])

    def test_the_saved_case_round_zero_reproduces_through_the_real_planner(self):
        saved = self.verify.saved_case_prompt()
        self.assertEqual(saved['status'], 'built', saved)
        self.assertTrue(saved['written_prompt_matches_provenance'])
        sent = saved['provenance']
        # The prompt and schema actually built for the saved case are the live ones.
        self.assertEqual(sent['schema_sha256'],
                         self.verify.sha256(planner.canonical_schema(planner.PLAN_SCHEMA)))
        self.assertEqual(sent['policy_sha256'], self.verify.sha256(planner.POLICY))
        recorded = json.loads((ROOT / 'validation/deepseek-api/prompt-provenance.json')
                              .read_text(encoding='utf-8'))
        self.assertEqual(recorded['frozen_fixture']['prompt_sha256'] != sent['prompt_sha256'], True,
                         'the frozen fixture must not be the acceptance prompt')

    def test_the_deepseek_request_body_carries_the_current_description(self):
        """The provider puts the schema in the system message, not the prompt."""
        from creation_pipeline.runtime import deepseek_api
        settings = deepseek_api.Settings(
            api_key='not-a-real-key', scheme='https', host='api.deepseek.com', port=None,
            prefix='/v1', endpoint_kind='official', model='deepseek-flash',
            max_output_tokens=1024, stream=True, retries=0, connect_retries=0, timeout=600,
            reasoning_effort=None, thinking=None, effort_sent=None, effort_note=None,
            service_tier=None, progress_timeout=None)
        material = self.verify.fixture_material()
        prompt = planner.build_prompt(material, 'none')
        body, messages, recorded = deepseek_api.build_body(settings, prompt, planner.PLAN_SCHEMA)
        self.assertEqual(messages[1]['content'], prompt)
        system = messages[0]['content']
        embedded = json.loads(system.split('JSON Schema:\n', 1)[1])
        description = embedded['properties']['plan']['properties']['acceptance_json']['description']
        self.assertEqual(description, planner.ACCEPTANCE_SPEC)
        self.assertIn('none_documented', description)
        self.assertIn('checked:[{source_path, sha256}]', description)
        self.assertEqual(recorded['structured_output_mode'].startswith('json_object'), True)
        # The same canonical schema identity the planner records and the receipt stores.
        self.assertEqual(
            self.verify.sha256(json.dumps(planner.PLAN_SCHEMA, ensure_ascii=False, sort_keys=True)),
            planner.provenance(material, 'none')['schema_sha256'])


if __name__ == '__main__':
    unittest.main()
