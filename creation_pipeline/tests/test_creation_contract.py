import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from creation_schema import normalize_response, validate
from render_drafts_v03 import render


def cited(text="Supported procedural evidence"):
    return {
        "text": text,
        "citations": [{
            "source_id": "s1",
            "start": 1,
            "end": 1,
            "quote": "Supported procedural evidence",
        }],
    }


def bundle():
    return {
        "paper_id": "paper-1",
        "primary_role": "paper",
        "source_type": "paper",
        "repo_files": [],
        "sources": [{
            "id": "s1",
            "role": "paper",
            "url": "https://example.org/paper.pdf",
            "path": "paper.pdf",
            "sha256": "abc",
            "lines": ["Supported procedural evidence for the method."],
        }],
    }


def candidate():
    return {
        "name": "example-procedure",
        "description": "Apply a supported example procedure.",
        "kind": "method_procedure",
        "operation": "Apply the example method under its documented conditions.",
        "invoke_when": [cited("Use for documented example tasks.")],
        "do_not_invoke_when": [cited("Do not use outside the documented scope.")],
        "preconditions": [cited("Require the documented input state.")],
        "inputs": [cited("A documented input.")],
        "outputs": [cited("A documented output.")],
        "steps": [cited("Perform the first step."), cited("Perform the second step.")],
        "decision_points": [],
        "verification_checks": [cited("Check the documented result.")],
        "success_criteria": [cited("The documented result is accepted.")],
        "stop_conditions": [],
        "requirements": [],
        "unknowns": ["Implementation command is not supplied."],
    }


class CreationContractTests(unittest.TestCase):
    def test_method_contract_validates_and_renders(self):
        response = {
            "contract_version": "1.1",
            "schema_version": 3,
            "paper_id": "paper-1",
            "candidates": [candidate()],
            "no_skill_reason": "",
        }
        checks = validate(response, bundle())
        self.assertEqual(checks[0]["state"], "draft_unexecuted")
        text = render(candidate(), bundle(), checks[0])
        self.assertIn("## Applicability", text)
        self.assertIn("Verification checks:", text)
        self.assertIn("## Success Criteria", text)
        self.assertIn("Check the documented result.", text)

    def test_method_requires_operational_signal(self):
        item = candidate()
        item["verification_checks"] = []
        response = {
            "contract_version": "1.1",
            "schema_version": 3,
            "paper_id": "paper-1",
            "candidates": [item],
            "no_skill_reason": "",
        }
        with self.assertRaisesRegex(ValueError, "decision point, verification check, or stop condition"):
            validate(response, bundle())

    def test_new_contract_fields_require_real_citations(self):
        item = candidate()
        item["success_criteria"][0]["citations"][0]["quote"] = "This quote is not in the source text"
        response = {
            "contract_version": "1.1",
            "schema_version": 3,
            "paper_id": "paper-1",
            "candidates": [item],
            "no_skill_reason": "",
        }
        with self.assertRaisesRegex(ValueError, "Citation quote not found"):
            validate(response, bundle())

    def test_success_criteria_is_required(self):
        item = candidate()
        item.pop("success_criteria")
        response = {
            "contract_version": "1.1",
            "schema_version": 3,
            "paper_id": "paper-1",
            "candidates": [item],
            "no_skill_reason": "",
        }
        with self.assertRaisesRegex(ValueError, "missing=.*success_criteria"):
            validate(response, bundle())

    def test_legacy_response_is_upgraded_for_replay(self):
        item = candidate()
        for field in (
            "invoke_when", "do_not_invoke_when", "preconditions", "decision_points",
            "verification_checks", "stop_conditions",
        ):
            item.pop(field)
        item["steps"] = item["steps"][:1]
        upgraded, legacy = normalize_response({
            "schema_version": 1,
            "paper_id": "paper-1",
            "candidates": [item],
            "no_skill_reason": "",
        })
        self.assertTrue(legacy)
        self.assertEqual(upgraded["contract_version"], "1.1")
        self.assertEqual(upgraded["schema_version"], 3)
        self.assertEqual(len(upgraded["candidates"][0]["invoke_when"]), 1)
        self.assertTrue(upgraded["candidates"][0]["success_criteria"])
        self.assertEqual(validate(upgraded, bundle(), enforce_contract=False)[0]["state"], "draft_unexecuted")

    def test_v2_response_is_upgraded_for_replay(self):
        item = candidate()
        item.pop("success_criteria")
        upgraded, legacy = normalize_response({
            "contract_version": "1.0",
            "schema_version": 2,
            "paper_id": "paper-1",
            "candidates": [item],
            "no_skill_reason": "",
        })
        self.assertTrue(legacy)
        self.assertEqual(upgraded["schema_version"], 3)
        self.assertEqual(
            upgraded["candidates"][0]["success_criteria"],
            upgraded["candidates"][0]["verification_checks"],
        )


if __name__ == "__main__":
    unittest.main()
