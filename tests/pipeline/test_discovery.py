"""Deterministic protocol fixtures test mechanics, not autonomous model quality."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.generation.discovery import ordered
from creation_pipeline.models import load_config
from creation_pipeline.artifacts.package import install, manifest, verify_bundle
from creation_pipeline.pipeline import ROOT, build
from creation_pipeline.records import read_json, write_json
from tests.pipeline.support import MAIN, PLAN, ARTIFACT, ReplayStages, response, isolated_check_regression


def candidate(name="add-numbers", **updates):
    value = dict(copy.deepcopy(PLAN), name=name, kind="skill", implementation="upstream",
                rationale="Preserve numeric input conventions", upstream_behavior="Adds two numbers",
                selected=True, priority=1, needs=[], method_evidence=[{"id": "e1", "claim": "source method"}])
    value.update(updates)
    return value


def discovery(*entities):
    return {"summary": "Read adder implementation and identified supported operations",
            "candidates": list(entities), "omitted": [], "limitations": []}


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / ".pipeline/test-tmp"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        self.source = self.root / "api.py"
        self.source.write_text('def add(a,b):\n    """add(2,3) == 5; reject text inputs."""\n    return a+b\n', encoding="utf-8")
        self.config = self.root / "config.json"
        self.options = {"sources": [{"id": "tool", "path": "api.py"}], "network": False,
            "adoption": {"enabled": False}, "prompt": "Keep the existing interface; no scientific claims", "limits": {"repair_rounds": 1},
            "checks": [{"candidate": "add-numbers", "name": "result", "argv": ["{python}", "-c", "print(2 + 3)"], "stdout_contains": ["5"]}]}
        write_json(self.config, self.options)
        self.state = self.root / "state"

    def tearDown(self):
        self.temp.cleanup()

    def run_case(self, *values, **kwargs):
        backend = ReplayStages([response(v) for v in values])
        self.last_backend = backend
        kwargs.setdefault("library_root", self.root / "library")
        result = build(self.config, self.state, _session_factory=backend, **kwargs)
        return result, read_json(Path(result["output"]) / "summary.json")

    def test_no_task_needed_and_verbatim_single_file(self):
        result, summary = self.run_case(discovery(candidate()), ARTIFACT)
        self.assertEqual(result["status"], "blocked", summary)
        output = Path(result["output"])
        self.assertEqual((output / "bundle/skills/add-numbers/SKILL.md").read_text(encoding="utf-8"), MAIN)
        self.assertTrue(summary["replay"])
        self.assertTrue((self.state / "runs" / result["build_id"]).exists())  # runtime continuation retained
        verify_bundle(output)

    def test_zero_candidates_is_successful_analysis(self):
        result, _ = self.run_case(discovery())
        self.assertEqual(result["status"], "no_candidates")

    def test_plan_resume_avoids_discovery_and_keeps_snapshot(self):
        result, _ = self.run_case(discovery(candidate()), plan_only=True)
        self.source.write_text("original input changed", encoding="utf-8")
        continued = build(state_root=self.state, plan_path=Path(result["output"]) / "plan.json",
                          _session_factory=ReplayStages([response(ARTIFACT)]))
        self.assertEqual(continued["status"], "blocked", continued)
        # No second discovery turn; author, review and runtime planning remain.
        self.assertEqual(continued["model_calls"], 3)

    def test_snapshot_mutation_rejected_before_model_call(self):
        result, _ = self.run_case(discovery(candidate()), plan_only=True)
        plan_path = Path(result["output"]) / "plan.json"
        plan = read_json(plan_path)
        Path(plan["sources"][0]["path"]).write_text("tampered", encoding="utf-8")
        result = build(state_root=self.state, plan_path=plan_path, _session_factory=ReplayStages([]))
        self.assertEqual(result["status"], "failed")
        self.assertIn("snapshot", str(result["errors"]))

    def test_edit_selection_is_supported(self):
        result, _ = self.run_case(discovery(candidate()), plan_only=True)
        path = Path(result["output"]) / "plan.json"
        doc = read_json(path)
        doc["discovery"]["candidates"][0]["selected"] = False
        write_json(path, doc)
        result = build(state_root=self.state, plan_path=path, _session_factory=ReplayStages([]))
        self.assertEqual(result["status"], "no_candidates")

    def test_source_context_edit_rejected(self):
        result, _ = self.run_case(discovery(candidate()), plan_only=True)
        path = Path(result["output"]) / "plan.json"
        doc = read_json(path)
        doc["config"]["execute_generated_checks"] = True
        write_json(path, doc)
        result = build(state_root=self.state, plan_path=path, _session_factory=ReplayStages([]))
        self.assertEqual(result["status"], "failed")

    def test_independent_candidate_survives_failure(self):
        bad = candidate("bad", readiness="blocked", gaps=["missing weights"])
        result, summary = self.run_case(discovery(bad, candidate()), ARTIFACT)
        self.assertEqual(result["status"], "blocked", summary)
        self.assertEqual(summary["counts"], {"blocked": 2})

    def test_content_review_without_execution_preserves_unverified_scope(self):
        self.options["checks"] = []
        write_json(self.config, self.options)
        result, _ = self.run_case(discovery(candidate()), ARTIFACT)
        self.assertEqual(result["status"], "blocked")
        record = read_json(Path(result["output"]) / "records/add-numbers.json")
        self.assertTrue(any(r["status"] == "not_run" for r in record["checks"]))

    def test_install_complete_bundle_and_detect_mutation(self):
        from tests.pipeline.test_delivery_protocol import configure_text, text_artifact
        configure_text(self)
        result, _ = self.run_case(discovery(candidate()), text_artifact())
        installed = install(result["output"], self.root / "installed")
        self.assertTrue((Path(installed["skills"]) / "add-numbers/SKILL.md").exists())
        with self.assertRaises(ValueError):
            install(result["output"], self.root / "installed")
        (Path(result["output"]) / "bundle/skills/add-numbers/SKILL.md").write_text("bad", encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_bundle(result["output"])

    def test_ready_resume_reuses_files_without_model_calls(self):
        from tests.pipeline.test_delivery_protocol import configure_text, text_artifact
        configure_text(self)
        result, _ = self.run_case(discovery(candidate()), text_artifact())
        again = build(state_root=self.state, plan_path=Path(result["output"]) / "plan.json", _session_factory=ReplayStages([]))
        self.assertEqual(again["status"], "ready", again)
        self.assertEqual(again["model_calls"], 0)

    def test_generated_checks_require_opt_in(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact["tests"] = [{"name": "grounded", "argv": ["{python}", "-c", "print(2 + 3)"],
            "expected_exit": 0, "stdout_contains": ["5"], "evidence": "e1", "purpose": "upstream example", "kind": "positive"}]
        self.options["checks"] = []
        write_json(self.config, self.options)
        result, _ = self.run_case(discovery(candidate()), artifact)
        self.assertEqual(result["status"], "blocked")
        record = read_json(Path(result["output"]) / "records/add-numbers.json")
        self.assertTrue(any(r["status"] == "not_run" for r in record["checks"]))
        result, _ = self.run_case(discovery(candidate()), artifact, execute_generated=True)
        self.assertEqual(result["status"], "blocked")

    def test_user_guidance_reaches_author(self):
        backend = ReplayStages([response(discovery(candidate())), response(ARTIFACT)])
        result = build(self.config, self.state, _session_factory=backend)
        prompts = backend.prompts
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(all(self.options["prompt"] in p for p in prompts))

    def test_shared_dependencies_rejected(self):
        with self.assertRaises(ValueError):
            ordered(discovery(candidate(needs=["shared"])))

    def test_independent_tool_rejected(self):
        with self.assertRaises(ValueError):
            ordered(discovery(candidate(kind="tool")))

    def test_duplicate_candidate_and_false_evidence_rejected(self):
        for plan in (discovery(candidate(), candidate()), discovery(candidate(evidence=[{"id": "fake", "claim": "x"}]))):
            result, _ = self.run_case(plan, plan)
            self.assertEqual(result["status"], "failed")

    def test_coverage_is_not_required(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact.pop("coverage", None)
        result, _ = self.run_case(discovery(candidate()), artifact)
        self.assertEqual(result["status"], "blocked")

    def test_file_defect_repaired_without_weakening_checks(self):
        wrong = copy.deepcopy(ARTIFACT)
        wrong["files"][0]["content"] = wrong["files"][0]["content"].replace("name: add-numbers", "name: incorrect-name")
        result, _ = self.run_case(discovery(candidate()), wrong, ARTIFACT)
        self.assertEqual(result["status"], "blocked")
        record = read_json(Path(result["output"]) / "records/add-numbers.json")
        self.assertEqual(record["repair_rounds"], 1)
        self.assertEqual(record["test_definitions"]["configured"][0]["stdout_contains"], ["5"])

    @isolated_check_regression
    def test_execution_mutation_of_bundle_is_rejected(self):
        self.options["limits"]["repair_rounds"] = 0
        self.options["checks"][0]["argv"] = ["{python}", "-c", "from pathlib import Path; import sys; Path(sys.argv[1],'SKILL.md').write_text('mutated'); print(5)", "{package}"]
        write_json(self.config, self.options)
        result, _ = self.run_case(discovery(candidate()), ARTIFACT)
        self.assertEqual(result["status"], "failed")

    def test_no_arbitrary_negative_case_quota(self):
        result, _ = self.run_case(discovery(candidate(intent="extension", added_behavior="Additional acceptance rule")),
            ARTIFACT, {"status": "pass", "resolution": "none", "findings": []})
        self.assertEqual(result["status"], "blocked")

    def test_missing_review_evidence_does_not_trigger_rewriting(self):
        result, _ = self.run_case(discovery(candidate(intent="extension", added_behavior="Additional rule")),
            ARTIFACT, {"status": "fail", "resolution": "supply_evidence", "findings": ["Missing boundary execution"]})
        self.assertEqual(result["status"], "draft")
        record = read_json(Path(result["output"]) / "records/add-numbers.json")
        self.assertEqual(record["repair_rounds"], 0)

    def test_explicit_intent_is_respected_but_auto_can_choose(self):
        self.options["intent"] = "extension"
        write_json(self.config, self.options)
        result, _ = self.run_case(discovery(candidate()), discovery(candidate()))
        self.assertEqual(result["status"], "failed")

    def test_budget_defers_extra_candidates(self):
        self.options["limits"]["max_builds"] = 1
        write_json(self.config, self.options)
        result, record = self.run_case(discovery(candidate(), candidate("another")), ARTIFACT)
        self.assertEqual(len(record["entities"]), 1)
        self.assertEqual(record["deferred"], ["another"])

    def test_missing_source_is_blocked(self):
        self.options["sources"][0]["path"] = "missing"
        write_json(self.config, self.options)
        result, _ = self.run_case()
        self.assertEqual(result["status"], "blocked")

    def test_unselected_candidate_does_not_need_complete_build_files(self):
        excluded = candidate('not-chosen', selected=False, files=[], evidence=[])
        result, _ = self.run_case(discovery(candidate(), excluded), ARTIFACT)
        self.assertEqual(result['status'], 'blocked')

    def test_invalid_discovery_repaired_without_reacquiring_sources(self):
        result, _ = self.run_case(discovery(candidate(), candidate()), discovery(candidate()), ARTIFACT)
        self.assertEqual(result['status'], 'blocked')
        # Two discovery turns, author, review and the runtime planning turn are
        # all counted; runtime planning is a model call too.
        self.assertEqual(result['model_calls'], 5)

    @isolated_check_regression
    def test_dropping_failed_generated_oracle_cannot_become_ready(self):
        self.options['checks'] = []
        write_json(self.config, self.options)
        artifact = copy.deepcopy(ARTIFACT)
        test = {'name': 'grounded', 'argv': ['{python}', '-c', 'print(2 + 3)'], 'expected_exit': 0,
                'stdout_contains': ['99'], 'evidence': 'e1', 'purpose': 'upstream example', 'kind': 'positive'}
        artifact['tests'] = [test]
        replacement = copy.deepcopy(artifact)
        replacement['tests'] = [dict(test, name='different', stdout_contains=['5'])]
        result, _ = self.run_case(discovery(candidate()), artifact, replacement, execute_generated=True)
        self.assertEqual(result['status'], 'draft')
        record = read_json(Path(result['output']) / 'records/add-numbers.json')
        self.assertEqual(len(record['repair_history']), 1)
        self.assertTrue(any(c['name'] == 'changed_failed_oracles' for c in record['checks']))

    def test_author_prompt_update_reuses_discovery_but_rebuilds_files(self):
        result, _ = self.run_case(discovery(candidate()), plan_only=True)
        from creation_pipeline.generation.discovery import specifications
        changed = specifications()
        changed['creation_pipeline/generation/prompts/author.md'] = 'new-author-prompt'
        with patch('creation_pipeline.pipeline.specifications', return_value=changed):
            again = build(state_root=self.state, plan_path=Path(result['output']) / 'plan.json',
                          _session_factory=ReplayStages([response(ARTIFACT)]))
        self.assertEqual(again['status'], 'blocked')
        summary = read_json(Path(again['output']) / 'summary.json')
        self.assertEqual(summary['revalidated_prompts'], ['creation_pipeline/generation/prompts/author.md'])

    def test_discovery_rule_change_requires_rediscovery(self):
        result, _ = self.run_case(discovery(candidate()), plan_only=True)
        from creation_pipeline.generation.discovery import specifications
        changed = specifications()
        changed['creation_pipeline/generation/prompts/analyze.md'] = 'new-discovery-policy'
        with patch('creation_pipeline.pipeline.specifications', return_value=changed):
            again = build(state_root=self.state, plan_path=Path(result['output']) / 'plan.json', _session_factory=ReplayStages([]))
        self.assertEqual(again['status'], 'failed')

    def test_backend_failure_is_not_retried_as_file_repair(self):
        backend = ReplayStages([response(discovery(candidate()))])
        original = backend.stage
        calls = []
        def fail_author(session, prompt, *args, **kwargs):
            calls.append(prompt)
            if len(calls) > 1:
                raise __import__("creation_pipeline.models", fromlist=["ModelCallError"]).ModelCallError('model service unavailable')
            return original(session, prompt, *args, **kwargs)
        backend.stage = fail_author
        result = build(self.config, self.state, _session_factory=backend)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(len(calls), 2)
        record = read_json(Path(result['output']) / 'records/add-numbers.json')
        self.assertIn('no file-repair retry', record['stopped_reason'])


if __name__ == '__main__':
    unittest.main()
