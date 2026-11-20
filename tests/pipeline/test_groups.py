"""Group isolation, ordered dispatch and resumable queue ownership."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from creation_pipeline.models import load_config
from creation_pipeline.pipeline import build
from creation_pipeline.records import lease, read_json, write_json
from creation_pipeline.retention import pin, sweep, DAY
from tests.pipeline import test_discovery as fixtures
from tests.pipeline.support import ARTIFACT, ReplayStages


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.DiscoveryTests()
        self.case.setUp()
        self.options = copy.deepcopy(self.case.options)
        self.options.pop("sources")
        self.options["resource_groups"] = [{"id": name, "sources": [{"id": "tool", "path": "api.py"}]} for name in ("first", "second")]
        write_json(self.case.config, self.options)

    def tearDown(self):
        self.case.tearDown()

    def run_queue(self, values, **kwargs):
        backend = ReplayStages(values)
        result = build(self.case.config, self.case.state, _session_factory=backend, **kwargs)
        return result, backend

    def test_normalization_is_local_to_each_group_and_rejects_bad_lists(self):
        config = load_config(self.case.config)
        self.assertEqual([g["sources"][0]["id"] for g in config["resource_groups"]], ["tool", "tool"])
        self.assertEqual(config["resource_groups"][0]["sources"][0]["path"], str(self.case.source))
        for groups in [[], [{"id": "same", "sources": []}], [self.options["resource_groups"][0]] * 2]:
            write_json(self.case.config, {**self.options, "resource_groups": groups})
            with self.assertRaises(ValueError):
                load_config(self.case.config)
        write_json(self.case.config, {**self.options, "sources": []})
        with self.assertRaises(ValueError):
            load_config(self.case.config)

    def test_two_groups_keep_sessions_and_flat_builds_separate(self):
        result, backend = self.run_queue([fixtures.discovery(fixtures.candidate()), ARTIFACT] * 2)
        self.assertEqual(result["status"], "ready", result)
        self.assertEqual([g["id"] for g in result["groups"]], ["first", "second"])
        self.assertNotEqual(*[g["build_id"] for g in result["groups"]])
        self.assertEqual(result["model_calls"], 8)
        for group in result["groups"]:
            self.assertTrue((self.case.state / "records" / group["build_id"] / "complete.json").exists())
        again = build(state_root=self.case.state, resume_id=result["build_id"], _session_factory=ReplayStages([]))
        self.assertEqual(again["status"], "ready", again)
        self.assertEqual(again["model_calls"], 8)

    def test_group_resource_failure_does_not_block_later_groups_and_can_resume(self):
        self.options["resource_groups"][0]["sources"][0]["path"] = "missing.py"
        write_json(self.case.config, self.options)
        result, _ = self.run_queue([fixtures.discovery(fixtures.candidate()), ARTIFACT])
        self.assertEqual(result["status"], "partial", result)
        self.assertEqual([g["status"] for g in result["groups"]], ["blocked", "ready"])
        (self.case.root / "missing.py").write_text(self.case.source.read_text(), encoding="utf-8")
        fixed = build(state_root=self.case.state, resume_id=result["build_id"],
            _session_factory=ReplayStages([fixtures.discovery(fixtures.candidate()), ARTIFACT]))
        self.assertEqual(fixed["status"], "ready", fixed)
        self.assertEqual(fixed["groups"][1]["build_id"], result["groups"][1]["build_id"])

    def test_backend_failure_stops_dispatch_leaving_later_group_pending(self):
        result, _ = self.run_queue([])
        self.assertEqual(result["status"], "incomplete", result)
        self.assertEqual(result["groups"][1]["status"], "pending")
        self.assertNotIn("build_id", result["groups"][1])

    def test_explicit_call_budget_is_not_reset_between_groups(self):
        self.options["limits"]["model_calls"] = 4
        write_json(self.case.config, self.options)
        result, _ = self.run_queue([fixtures.discovery(fixtures.candidate()), ARTIFACT] * 2)
        self.assertEqual(result["status"], "incomplete", result)
        self.assertEqual(result["groups"][0]["status"], "ready")
        self.assertEqual(result["groups"][1]["status"], "pending")
        self.assertEqual(result["model_calls"], 4)

    def test_completed_queue_needs_no_new_turns_even_at_call_limit(self):
        self.options["limits"]["model_calls"] = 8
        write_json(self.case.config, self.options)
        result, _ = self.run_queue([fixtures.discovery(fixtures.candidate()), ARTIFACT] * 2)
        resumed = build(state_root=self.case.state, resume_id=result["build_id"], _session_factory=ReplayStages([]))
        self.assertEqual(resumed["status"], "ready", resumed)
        self.assertEqual(resumed["model_calls"], 8)

    def test_candidate_call_limit_does_not_stop_other_resource_groups(self):
        self.options["limits"]["candidate_calls"] = 1
        write_json(self.case.config, self.options)
        result, _ = self.run_queue([fixtures.discovery(fixtures.candidate()), ARTIFACT] * 2)
        self.assertEqual([g["status"] for g in result["groups"]], ["incomplete", "incomplete"], result)

    def test_group_discovery_limit_does_not_become_a_queue_wide_stop(self):
        self.options["limits"]["discovery_seconds"] = 1
        write_json(self.case.config, self.options)
        backend = ReplayStages([fixtures.discovery(fixtures.candidate())] * 2)
        original = backend.stage
        def elapsed(session, instructions, context, schema=None):
            result = original(session, instructions, context, schema)
            session.receipts[-1]["elapsed_seconds"] = 1
            return result
        with patch.object(backend, 'stage', side_effect=elapsed):
            result = build(self.case.config, self.case.state, _session_factory=backend)
        self.assertEqual([g["status"] for g in result["groups"]], ["incomplete", "incomplete"], result)

    def test_discover_queue_resumes_saved_final_plans(self):
        result, _ = self.run_queue([fixtures.discovery(fixtures.candidate())] * 2, plan_only=True)
        self.assertEqual(result["status"], "planned", result)
        backend = ReplayStages([ARTIFACT] * 2)
        built = build(state_root=self.case.state, resume_id=result["build_id"], _session_factory=backend)
        self.assertEqual(built["status"], "ready", built)
        self.assertEqual(len(backend.prompts), 4)

    def test_resume_extends_one_global_call_quota_without_repeating_first_group(self):
        self.options["limits"]["model_calls"] = 6
        write_json(self.case.config, self.options)
        result, _ = self.run_queue([fixtures.discovery(fixtures.candidate()), ARTIFACT] * 2)
        self.assertEqual(result["status"], "incomplete", result)
        self.assertEqual(result["model_calls"], 6)
        backend = ReplayStages([ARTIFACT])
        resumed = build(state_root=self.case.state, resume_id=result["build_id"], extra_turns=2,
                        _session_factory=backend)
        self.assertEqual(resumed["status"], "ready", resumed)
        self.assertEqual(resumed["model_calls"], 8)
        self.assertEqual(len(backend.prompts), 2)

    def test_candidate_build_limit_is_shared_and_next_invocation_continues(self):
        self.options["limits"]["max_builds"] = 1
        write_json(self.case.config, self.options)
        result, _ = self.run_queue([fixtures.discovery(fixtures.candidate()), ARTIFACT] * 2)
        self.assertEqual(result["groups"][1]["status"], "pending")
        resumed = build(state_root=self.case.state, resume_id=result["build_id"],
                        _session_factory=ReplayStages([fixtures.discovery(fixtures.candidate()), ARTIFACT]))
        self.assertEqual(resumed["status"], "ready", resumed)

    def test_missing_completed_package_is_not_silently_rebuilt_or_accepted(self):
        result, _ = self.run_queue([fixtures.discovery(fixtures.candidate()), ARTIFACT] * 2)
        package = Path(result["groups"][0]["result"]["output"]) / "skills/add-numbers/package/SKILL.md"
        package.unlink()
        backend = ReplayStages([])
        resumed = build(state_root=self.case.state, resume_id=result["build_id"], _session_factory=backend)
        self.assertEqual(resumed["status"], "incomplete", resumed)
        self.assertFalse(backend.prompts)

    def test_queue_owner_prevents_concurrent_resume(self):
        result, _ = self.run_queue([fixtures.discovery()] * 2)
        with lease(self.case.state, result["build_id"]), self.assertRaises(OSError):
            build(state_root=self.case.state, resume_id=result["build_id"], _session_factory=ReplayStages([]))

    def test_pinned_queue_protects_child_workspaces(self):
        result, _ = self.run_queue([fixtures.discovery(fixtures.candidate())] * 2, plan_only=True)
        pin(self.case.state, result["build_id"], True)
        for group in result["groups"]:
            registration = self.case.state / "retention" / (group["build_id"] + ".json")
            data = read_json(registration)
            data["last_activity"] = 1
            write_json(registration, data)
        report = sweep(self.case.state, clock=40 * DAY)
        self.assertTrue(all(g["build_id"] in report["skipped"] for g in result["groups"]))
        pin(self.case.state, result["build_id"], False)

    def test_failed_archive_is_retried_without_rediscovering(self):
        result, _ = self.run_queue([fixtures.discovery(fixtures.candidate())] * 2, plan_only=True)
        path = Path(result['output'])
        queue = read_json(path)
        child = queue['groups'][0]['result']
        marker = Path(child['output']) / 'complete.json'
        marker.unlink()
        child['archive_complete'] = False
        write_json(path, queue)
        backend = ReplayStages([])
        retried = build(state_root=self.case.state, resume_id=result['build_id'], plan_only=True, _session_factory=backend)
        self.assertEqual(retried['status'], 'planned', retried)
        self.assertTrue(marker.exists())
        self.assertFalse(backend.prompts)

    def test_expired_checkpoint_is_not_rebuilt_under_the_same_child_identity(self):
        from creation_pipeline.retention import remove_registered
        result, _ = self.run_queue([fixtures.discovery(fixtures.candidate())] * 2, plan_only=True)
        bid = result['groups'][0]['build_id']
        archived = self.case.state / 'records' / bid / 'summary.json'
        before = archived.read_bytes()
        remove_registered(self.case.state, 'runs/' + bid)
        backend = ReplayStages([])
        resumed = build(state_root=self.case.state, resume_id=result['build_id'], _session_factory=backend)
        self.assertEqual(resumed['status'], 'incomplete', resumed)
        self.assertFalse(backend.prompts)
        self.assertEqual(archived.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
