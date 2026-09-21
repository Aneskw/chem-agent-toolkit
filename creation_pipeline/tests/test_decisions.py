import copy
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "core"))
from creation_schema import validate
from decision_library import build_library
from render_drafts_v03 import render
from repair_citation_spans import repair
from validate_skill_format import validate as format_check


def fixture():
    quote = "Sum precursor costs when a reaction requires all precursors."
    citation = {"source_id": "p", "start": 1, "end": 1, "quote": quote}

    def claim(text):
        return {"text": text, "citations": [copy.deepcopy(citation)]}

    candidate = {
        "name": "sum-route-costs",
        "description": "Compare route costs.",
        "kind": "method_procedure",
        "operation": "Compare complete route costs.",
        "invoke_when": [claim("Comparing reaction branches in an AND tree.")],
        "do_not_invoke_when": [claim("A branch represents mutually exclusive alternatives.")],
        "preconditions": [claim("All precursor cost estimates are available.")],
        "inputs": [claim("Candidate precursor costs.")],
        "outputs": [claim("A route cost comparison.")],
        "steps": [claim("Collect every required precursor cost."), claim("Sum the costs.")],
        "decision_points": [{
            "condition": claim("The reaction requires all listed precursors."),
            "if_true": claim("Sum every precursor cost."),
            "if_false": claim("Compare alternatives separately."),
        }],
        "verification_checks": [claim("Check that every obligation was included.")],
        "stop_conditions": [claim("Stop if a required cost is unavailable.")],
        "requirements": [],
        "unknowns": [],
    }
    bundle = {
        "paper_id": "test",
        "primary_role": "paper",
        "repo_files": [],
        "sources": [{
            "id": "p", "role": "paper", "lines": [quote],
            "url": "https://example.org/paper", "path": "paper.pdf", "sha256": "a" * 64,
        }],
    }
    response = {
        "contract_version": "1.0", "schema_version": 2, "paper_id": "test",
        "candidates": [candidate], "no_skill_reason": "",
    }
    return response, bundle


class DecisionTests(unittest.TestCase):
    def test_method_without_operational_signal_rejected(self):
        response, bundle = fixture()
        candidate = response["candidates"][0]
        candidate["decision_points"] = []
        candidate["verification_checks"] = []
        candidate["stop_conditions"] = []
        with self.assertRaisesRegex(ValueError, "decision point"):
            validate(response, bundle)

    def test_fabricated_quote_is_rejected(self):
        response, bundle = fixture()
        response["candidates"][0]["decision_points"][0]["condition"]["citations"][0]["quote"] = "Invented chemistry result"
        with self.assertRaisesRegex(ValueError, "quote not found"):
            validate(response, bundle)

    def test_dedup_preserves_scope_and_citations(self):
        response, _ = fixture()
        other = copy.deepcopy(response)
        other["paper_id"] = "second"
        report = build_library([response, other])
        self.assertEqual(report["unique_rules"], 1)
        self.assertEqual(len(report["rules"][0]["origins"]), 2)
        other["candidates"][0]["do_not_invoke_when"][0]["text"] = "Do not use for DAGs."
        report = build_library([response, other])
        self.assertEqual(report["unique_rules"], 2)
        self.assertEqual(report["related"][0]["action"], "retain_scoped_variants")

    def test_render_matches_format(self):
        response, bundle = fixture()
        candidate = response["candidates"][0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / candidate["name"] / "SKILL.md"
            path.parent.mkdir()
            path.write_text(render(candidate, bundle, validate(response, bundle)[0]))
            self.assertEqual(format_check(path), [])
            self.assertIn("license: undetermined", path.read_text())
            self.assertIn("If true", path.read_text())

    def test_all_contract_claims_participate_in_citation_repair(self):
        response, bundle = fixture()
        bundle["sources"][0]["lines"] = ["Heading", bundle["sources"][0]["lines"][0]]
        revised, changes = repair(response, bundle)
        self.assertTrue(changes)
        validate(revised, bundle)


if __name__ == "__main__":
    unittest.main()
