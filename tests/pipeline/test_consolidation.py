"""Candidate-set accounting and recovery before any package is authored."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from creation_pipeline.generation.discovery import analyze, normalize, validate_mapping
from creation_pipeline.models import ModelCallError, BlockedError
from creation_pipeline.pipeline import build
from creation_pipeline.records import read_json, write_json
from tests.pipeline import test_discovery as fixtures
from tests.pipeline.support import ARTIFACT, ReplayStages


def final(draft, candidates=None, mapping=None):
    result = copy.deepcopy(draft)
    result["outcome"] = "candidates" if result["candidates"] else "no_suitable_candidates"
    if candidates is not None:
        result["candidates"] = candidates
    result["mapping"] = mapping if mapping is not None else [
        {"from": [c["name"]], "to": [c["name"]], "reason": "Distinct task"} for c in draft["candidates"]]
    return result


class ConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.DiscoveryTests()
        self.case.setUp()

    def tearDown(self):
        self.case.tearDown()

    def test_merge_accounting_and_support_files_reach_author(self):
        draft = fixtures.discovery(fixtures.candidate("raw-addition"), fixtures.candidate("prepared-addition"))
        packaged = final(draft, [fixtures.candidate()], [{"from": ["raw-addition", "prepared-addition"],
            "to": ["add-numbers"], "reason": "Common core with raw/prepared modes"}])
        artifact = copy.deepcopy(ARTIFACT)
        artifact["files"].append({"path": "references/prepared.md", "purpose": "Prepared mode", "content": "Use prepared numeric inputs."})
        artifact["files"][0]["content"] += "\n[Prepared mode](references/prepared.md)\n"
        result, record = self.case.run_case(draft, packaged, artifact)
        self.assertEqual(result["status"], "ready", result)
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(len(record["packaging"]["draft"]["candidates"]), 2)
        self.assertEqual(record["discovery"]["mapping"], packaged["mapping"])
        self.assertTrue((Path(result["output"]) / "skills/add-numbers/package/references/prepared.md").exists())

    def test_mapping_rejects_loss_duplicates_unknown_and_unexplained_omission(self):
        draft = fixtures.discovery(fixtures.candidate())
        cases = [[], [{"from": ["missing"], "to": ["add-numbers"], "reason": "x"}],
                 [{"from": ["add-numbers", "add-numbers"], "to": ["add-numbers"], "reason": "x"}],
                 [{"from": ["add-numbers"], "to": [], "reason": "unsupported"}]]
        for mapping in cases:
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                validate_mapping(draft, final(draft, mapping=mapping))

    def test_explicit_gap_can_be_retained_without_a_false_supported_mode(self):
        draft = fixtures.discovery(fixtures.candidate())
        result = final(draft, [], [{"from": ["add-numbers"], "to": [], "reason": "Missing required method"}])
        result["omitted"] = [{"capability": "add-numbers", "reason": "Missing required method"}]
        validate_mapping(draft, result)

    def test_interrupted_consolidation_resumes_saved_draft(self):
        backend = ReplayStages([fixtures.discovery(fixtures.candidate())])
        original = backend.stage
        def interrupt(session, instructions, context, schema=None):
            if context.get("_discovery_step") == "consolidate":
                raise ModelCallError("Transport unavailable")
            return original(session, instructions, context, schema)
        with patch.object(backend, "stage", side_effect=interrupt):
            result = build(self.case.config, self.case.state, _session_factory=backend)
        self.assertEqual(result["dispatch_stopped"], "backend")
        self.assertTrue((self.case.state / "runs" / result["build_id"] / "discovery-state.json").exists())
        resumed = ReplayStages([ARTIFACT])
        result = build(state_root=self.case.state, resume_id=result["build_id"], _session_factory=resumed)
        self.assertEqual(result["status"], "ready", result)
        self.assertIn('"_discovery_step": "consolidate"', resumed.prompts[0])
        self.assertFalse(any('"_discovery_step": "explore"' in p for p in resumed.prompts))

    def test_discover_then_resume_does_not_repeat_discovery(self):
        result = build(self.case.config, self.case.state, plan_only=True,
                       _session_factory=ReplayStages([fixtures.discovery(fixtures.candidate())]))
        self.assertEqual(result["status"], "planned", result)
        resumed = ReplayStages([ARTIFACT])
        result = build(state_root=self.case.state, resume_id=result["build_id"], _session_factory=resumed)
        self.assertEqual(result["status"], "ready", result)
        self.assertTrue(all('"_discovery_step"' not in p for p in resumed.prompts))

    def test_additional_candidate_cannot_bypass_reconciliation(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact["additional_candidates"] = [fixtures.candidate("another-mode")]
        draft = fixtures.discovery(fixtures.candidate(), fixtures.candidate("another-mode"))
        merged = final(draft, [fixtures.candidate()], [{"from": ["add-numbers", "another-mode"],
            "to": ["add-numbers"], "reason": "Already covered by numeric input mode"}])
        result, record = self.case.run_case(fixtures.discovery(fixtures.candidate()), artifact, merged)
        self.assertEqual(result["status"], "ready", result)
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(len(record["discovery"]["reconciliations"]), 1)

    def test_missing_mode_returns_to_author_before_approval(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact["additional_candidates"] = [fixtures.candidate("prepared-mode")]
        draft = fixtures.discovery(fixtures.candidate(), fixtures.candidate("prepared-mode"))
        broader = fixtures.candidate(scope="Numeric addition with raw and prepared inputs")
        merged = final(draft, [broader], [{"from": ["add-numbers", "prepared-mode"],
                       "to": ["add-numbers"], "reason": "Add the missing prepared input mode"}])
        revised = copy.deepcopy(ARTIFACT)
        revised["files"][0]["content"] += "\nPrepared inputs use the same numeric interface.\n"
        result, _ = self.case.run_case(fixtures.discovery(fixtures.candidate()), artifact, merged, revised)
        self.assertEqual(result["status"], "ready", result)
        prompts = self.case.last_backend.prompts
        self.assertIn("package_scope", prompts[-2])
        self.assertIn('"_phase": "review"', prompts[-1])

    def test_resume_freezes_approved_peers_before_an_earlier_new_candidate(self):
        options = copy.deepcopy(self.case.options)
        options["limits"]["max_builds"] = 2
        write_json(self.case.config, options)
        first, second, third = fixtures.candidate(), fixtures.candidate("second"), fixtures.candidate("third", priority=0)
        second_artifact = copy.deepcopy(ARTIFACT)
        second_artifact["files"][0]["content"] = second_artifact["files"][0]["content"].replace('name: add-numbers', 'name: second')
        second_artifact["additional_candidates"] = [third]
        updated_second = dict(second, priority=2)
        draft = fixtures.discovery(first, second, third)
        rearranged = final(draft, [third, first, updated_second])
        result, _ = self.case.run_case(fixtures.discovery(first, second), ARTIFACT, second_artifact, rearranged)
        self.assertEqual(result["status"], "partial", result)
        third_artifact = copy.deepcopy(ARTIFACT)
        third_artifact["files"][0]["content"] = third_artifact["files"][0]["content"].replace('name: add-numbers', 'name: third')
        third_artifact["additional_candidates"] = [fixtures.candidate("fourth")]
        captured = []
        def observe(session, config, entity, proposals):
            captured.extend(c["name"] for c in config["_approved_plans"])
            raise BlockedError("Fixture stops after checking frozen peers")
        with patch('creation_pipeline.pipeline.reconcile', side_effect=observe):
            build(state_root=self.case.state, resume_id=result["build_id"], _session_factory=ReplayStages([third_artifact]))
        self.assertEqual(set(captured), {"add-numbers", "second"})

    def test_repeated_resource_handoff_error_is_not_a_backend_failure(self):
        from creation_pipeline.agent.backend import NativeSession
        from creation_pipeline.models import IncompleteError
        from creation_pipeline.resources.supplements import SourceHandoffError
        from creation_pipeline.resources.intake import Sources
        from creation_pipeline.models import load_config
        config = load_config(self.case.config)
        sources = Sources(config, self.case.state / "cache")
        session = NativeSession(config, sources, copy.deepcopy(config["limits"]), self.case.root / "handoff")
        with patch.object(session, '_stage_once', side_effect=SourceHandoffError('Missing saved source')):
            with self.assertRaises(IncompleteError):
                session.stage('source handoff', {}, {})

    def test_infrastructure_revision_reuses_approved_content_in_partial_build(self):
        from creation_pipeline.pipeline import hash_object
        options = copy.deepcopy(self.case.options)
        options['limits']['max_builds'] = 1
        write_json(self.case.config, options)
        result, _ = self.case.run_case(fixtures.discovery(fixtures.candidate(), fixtures.candidate('second')), ARTIFACT)
        self.assertEqual(result['status'], 'partial', result)
        second = copy.deepcopy(ARTIFACT)
        second['files'][0]['content'] = second['files'][0]['content'].replace('name: add-numbers', 'name: second')
        def changed_implementation(value):
            if isinstance(value, dict) and value and all(k.startswith('creation_pipeline/') for k in value):
                return 'different-infrastructure-revision'
            return hash_object(value)
        backend = ReplayStages([second])
        with patch('creation_pipeline.pipeline.hash_object', side_effect=changed_implementation):
            resumed = build(state_root=self.case.state, resume_id=result['build_id'], _session_factory=backend)
        self.assertEqual(resumed['status'], 'ready', resumed)
        self.assertEqual(len(backend.prompts), 2)
        self.assertTrue(all('"name": "second"' in p for p in backend.prompts))


if __name__ == "__main__":
    unittest.main()
