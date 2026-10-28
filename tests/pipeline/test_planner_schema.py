"""Field documentation must not mutate shared schema primitives."""
import copy
import json
from pathlib import Path
import unittest

import jsonschema

from creation_pipeline.runtime import planner


def annotations(value, path=''):
    result = {}
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'description' and isinstance(child, str):
                result[path + '/description'] = child
            else:
                result.update(annotations(child, path + '/' + key))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            result.update(annotations(child, path + '/' + str(i)))
    return result


def strip_descriptions(value):
    """Remove documentation only; every structural key stays exactly as it is."""
    if isinstance(value, dict):
        return {key: strip_descriptions(child) for key, child in value.items() if key != 'description'}
    if isinstance(value, list):
        return [strip_descriptions(child) for child in value]
    return value


class PlannerSchemaTests(unittest.TestCase):
    def test_acceptance_documentation_is_only_on_intended_nodes(self):
        self.assertEqual(annotations(planner.PLAN_SCHEMA), {
            '/properties/plan/properties/acceptance_json/description': planner.ACCEPTANCE_SPEC})
        self.assertEqual(annotations(planner.PATCH_SCHEMA), {'/description': planner.ACCEPTANCE_SPEC})
        self.assertEqual(planner.S, {'type': 'string'})

    def test_acceptance_node_is_independent(self):
        schema = copy.deepcopy(planner.PLAN_SCHEMA)
        target = schema['properties']['plan']['properties']['acceptance_json']
        target['description'] = 'changed only here'
        self.assertNotIn('description', schema['properties']['requested_files']['items'])
        self.assertNotIn('description', schema['properties']['plan']['properties']['base_image'])

    def test_exact_baseline_except_misdirected_annotations(self):
        """The schema shape is frozen; the documentation and one operation rule are not.

        The baseline is the pre-fix snapshot: it still carries the acceptance text on
        every field that shared ``S``. Only the intended node keeps that
        documentation, so every baseline description is normalized away before the
        exact shape comparison, and the intended node's *content* is asserted to be
        the current ``ACCEPTANCE_SPEC`` by the test above. Pinning the old text here
        would let the model be sent a contract the validators no longer accept.

        ``value_json`` and the two JSON-text field types are deliberate structural
        changes: a ``remove`` operation has no value, and the model follows a schema
        type over prose, so the plan fields accept the object encoding the validator
        already normalises. Both changes are asserted here and normalised on the
        baseline copy before the exact comparison.
        """
        root = Path(__file__).resolve().parents[2] / 'validation/planner-schema-isolation/before'
        for name, current, intended in [
            ('plan', planner.PLAN_SCHEMA, '/properties/plan/properties/acceptance_json/description'),
            ('patch', planner.PATCH_SCHEMA, '/description')]:
            baseline = json.loads((root / (name + '.json')).read_text(encoding='utf-8'))
            self.assertIn(intended, annotations(baseline))
            if name == 'patch':
                required = baseline['properties']['operations']['items']['required']
                self.assertIn('value_json', required)
                self.assertEqual(required, ['op', 'path', 'value_json'])
                baseline['properties']['operations']['items']['required'] = ['op', 'path']
            else:
                plan_props = baseline['properties']['plan']['properties']
                self.assertEqual(plan_props['acceptance_json']['type'], 'string')
                self.assertEqual(plan_props['tests']['items']['properties']['case_json']['type'], 'string')
                plan_props['acceptance_json']['type'] = ['string', 'object']
                plan_props['tests']['items']['properties']['case_json']['type'] = ['string', 'object']
            # Documentation is compared by the test above, not pinned to a snapshot.
            self.assertEqual(strip_descriptions(current), strip_descriptions(baseline))

    def test_a_removal_is_not_forced_to_carry_a_value(self):
        operations = planner.PATCH_SCHEMA['properties']['operations']['items']
        self.assertEqual(operations['required'], ['op', 'path'])
        self.assertIn('value_json', operations['properties'])
        answer = {'action': 'patch', 'requested_files': [], 'reason': 'drop a step',
                  'operations': [{'op': 'remove', 'path': '/steps/0'}]}
        jsonschema.validate(answer, planner.PATCH_SCHEMA)
