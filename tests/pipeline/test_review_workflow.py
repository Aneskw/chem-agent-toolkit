"""Regression coverage for independent source review, not execution approval."""
import copy
import json
from pathlib import Path
import unittest
from tests.pipeline.test_discovery import discovery, candidate
from tests.pipeline import test_discovery as fixtures
from tests.pipeline.support import ARTIFACT
from creation_pipeline.records import read_json


def finding(problem="Wrong argument"):
    return {"location": "SKILL.md#usage", "problem": problem, "evidence": "api.py add definition",
            "impact": "Incorrect invocation", "action": "Use documented arguments", "blocking": True, "category": "file"}


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.DiscoveryTests()
        self.case.setUp()

    def tearDown(self):
        self.case.tearDown()

    def test_one_review_per_delivery_and_author_repairs(self):
        fixed = copy.deepcopy(ARTIFACT)
        fixed["files"][0]["content"] += "\nSupported clarification.\n"
        result, _ = self.case.run_case(discovery(candidate()), ARTIFACT,
            {"status": "fail", "resolution": "revise_files", "findings": [finding()]}, fixed)
        self.assertEqual(result["status"], "ready", result)
        self.assertEqual(len(self.case.last_backend.prompts), 5)
        self.assertIn("feedback", self.case.last_backend.prompts[3])

    def test_review_record_error_goes_back_to_reviewer(self):
        result, _ = self.case.run_case(discovery(candidate()), ARTIFACT,
            {"status": "pass", "resolution": "none", "findings": "bad format"},
            {"status": "pass", "resolution": "none", "findings": []})
        self.assertEqual(result["status"], "ready", result)
        self.assertEqual(len(self.case.last_backend.prompts), 4)
        self.assertIn("record_format_error", self.case.last_backend.prompts[-1])
        self.assertIn('"_phase": "review"', self.case.last_backend.prompts[-1])

    def test_nonblocking_concision_suggestion_does_not_fail(self):
        f = finding("Repeated explanation")
        f.update(blocking=False, category="concision")
        result, _ = self.case.run_case(discovery(candidate()), ARTIFACT,
            {"status": "pass", "resolution": "none", "findings": [f]})
        self.assertEqual(result["status"], "ready", result)

    def test_usage_assessment_is_retained_outside_runtime_package(self):
        assessment = "Numeric inputs reach a sum through add; text rejection is the useful convention and no in-scope gap remains."
        result, _ = self.case.run_case(discovery(candidate()), ARTIFACT,
            {"status": "pass", "resolution": "none", "usage_assessment": assessment, "findings": []})
        record = read_json(Path(result["output"]) / "skills/add-numbers/review.json")
        review = next(check for check in record["checks"] if check["name"] == "content_review")
        self.assertEqual(review["usage_assessment"], assessment)
        package = Path(result["output"]) / "skills/add-numbers/package/SKILL.md"
        self.assertNotIn(assessment, package.read_text(encoding="utf-8"))

    def test_empty_usage_assessment_returns_to_reviewer_not_writer(self):
        result, _ = self.case.run_case(discovery(candidate()), ARTIFACT,
            {"status": "pass", "resolution": "none", "usage_assessment": "  ", "findings": []},
            {"status": "pass", "resolution": "none", "usage_assessment": "Numeric inputs reach a sum; the call preserves the input convention.", "findings": []})
        self.assertEqual(result["status"], "ready", result)
        self.assertEqual(len(self.case.last_backend.prompts), 4)
        correction = json.loads(self.case.last_backend.prompts[-1].rsplit("\n", 1)[1])
        self.assertEqual(correction["_phase"], "review")
        self.assertIn("usage_assessment", correction["record_format_error"])

    def test_inline_diagnostic_reaches_reviewer_and_refreshes_after_repair(self):
        broken = copy.deepcopy(ARTIFACT)
        broken["files"][0]["content"] += "\n```python\nanswer =\n```\n"
        repaired = copy.deepcopy(ARTIFACT)
        repaired["files"][0]["content"] += "\n```python\nanswer = 2 + 3\n```\n"
        result, _ = self.case.run_case(discovery(candidate()), broken,
            {"status": "fail", "resolution": "revise_files",
             "findings": [finding("Incomplete assignment in promised Python example")]}, repaired)
        self.assertEqual(result["status"], "ready", result)
        self.assertEqual(len(self.case.last_backend.prompts), 5)
        first = json.loads(self.case.last_backend.prompts[2].rsplit("\n", 1)[1])
        second = json.loads(self.case.last_backend.prompts[4].rsplit("\n", 1)[1])
        self.assertEqual(first["inline_python_diagnostics"]["blocks_checked"], 2)
        self.assertEqual(len(first["inline_python_diagnostics"]["issues"]), 1)
        self.assertTrue(all(c["status"] == "pass" for c in first["checks"]))
        self.assertEqual(second["inline_python_diagnostics"]["issues"], [])

    def test_multi_file_package_is_not_executed(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact["files"] += [{"path": "scripts/helper.py", "purpose": "Support", "content":
            "raise RuntimeError('must never execute')\n"}, {"path": "assets/input.json", "purpose": "Input", "content": "{}"}]
        artifact["files"][0]["content"] += "\n[Helper](scripts/helper.py)\n[Input](assets/input.json)\n"
        result, _ = self.case.run_case(discovery(candidate()), artifact)
        self.assertEqual(result["status"], "ready", result)

    def test_cli_and_http_examples_do_not_require_python(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact["files"][0]["content"] = artifact["files"][0]["content"].split("```python")[0] + "```sh\nobabel input.sdf -O output.mol\n```\n```http\nPOST /predict\n```\n"
        result, _ = self.case.run_case(discovery(candidate()), artifact)
        self.assertEqual(result["status"], "ready", result)

    def test_review_has_no_execution_contract(self):
        result, _ = self.case.run_case(discovery(candidate()), ARTIFACT)
        review = read_json(Path(result["output"]) / "skills/add-numbers/review.json")
        self.assertEqual(review["acceptance_scope"], "source_and_content_review_only")
        self.assertNotIn("verification", review)

    def test_unchanged_author_does_not_repeat_review(self):
        result, _ = self.case.run_case(discovery(candidate()), ARTIFACT,
            {"status": "fail", "resolution": "revise_files", "findings": [finding()]}, ARTIFACT)
        self.assertEqual(result["status"], "incomplete", result)
        self.assertEqual(len(self.case.last_backend.prompts), 4)

    def test_bad_author_metadata_is_corrected_by_author(self):
        bad = copy.deepcopy(ARTIFACT)
        bad["basis"] = []
        result, _ = self.case.run_case(discovery(candidate()), bad, ARTIFACT)
        self.assertEqual(result["status"], "ready", result)
        self.assertEqual(len(self.case.last_backend.prompts), 4)
        self.assertIn("author_delivery", self.case.last_backend.prompts[2])

    def test_reviewer_gets_promise_and_sources_not_authors_value_verdict(self):
        plan = candidate(rationale="AUTHOR-ONLY-BENEFIT-VERDICT")
        result, _ = self.case.run_case(discovery(plan), ARTIFACT)
        self.assertEqual(result["status"], "ready", result)
        writer, reviewer = self.case.last_backend.prompts[1:3]
        self.assertIn("AUTHOR-ONLY-BENEFIT-VERDICT", writer)
        self.assertNotIn("AUTHOR-ONLY-BENEFIT-VERDICT", reviewer)
        self.assertIn("Numeric addition", reviewer)
        self.assertIn('"resource_index"', reviewer)
        self.assertIn('"basis"', reviewer)

    def test_source_rebuttal_can_be_reviewed_without_rewriting_correct_files(self):
        rebuttal = copy.deepcopy(ARTIFACT)
        rebuttal["basis"].append({"location": "SKILL.md#usage", "claim": "The add definition already accepts both supplied arguments; the review premise is incorrect",
            "source": "e1", "locator": "def add(a,b)", "origin": "upstream"})
        result, _ = self.case.run_case(discovery(candidate()), ARTIFACT,
            {"status": "fail", "resolution": "revise_files", "findings": [finding()]}, rebuttal)
        self.assertEqual(result["status"], "ready", result)
        self.assertEqual(len(self.case.last_backend.prompts), 5)
