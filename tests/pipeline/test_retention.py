"""Lifecycle checks use a controlled clock, never delete user source files."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from creation_pipeline.retention import DAY, lease, mark, pin, sweep, archive, register_cache
from creation_pipeline.records import write_json, read_json
from creation_pipeline.agent.metrics import summarize_usage


class RetentionTests(unittest.TestCase):
    def setUp(self):
        parent = Path(__file__).resolve().parents[2] / ".pipeline/test-tmp"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name).resolve()
        self.state = self.root / "state"

    def tearDown(self):
        self.temp.cleanup()

    def batch(self, bid="batch"):
        work = self.state / "runs" / bid
        work.mkdir(parents=True)
        write_json(work / "workspace.json", {"build_id": bid, "workspace": str(work.resolve())})
        write_json(self.state / "records" / bid / "complete.json", {"build_id": bid})
        mark(self.state, bid, last_activity=time.time() - 8 * DAY, cache=[])
        return work

    def test_expired_workspace_removed_but_compact_records_and_user_source_remain(self):
        work = self.batch()
        original = self.root / "paper.pdf"
        original.write_bytes(b"original")
        draft = self.state / "records/batch/skills/a/draft/SKILL.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("latest")
        self.assertTrue(sweep(self.state, dry_run=True)["removed"])
        self.assertTrue(work.exists())
        sweep(self.state)
        self.assertFalse(work.exists())
        self.assertTrue(original.exists())
        self.assertEqual(draft.read_text(), "latest")

    def test_active_and_pinned_batches_are_skipped(self):
        work = self.batch()
        with lease(self.state, "batch"):
            self.assertIn("batch", sweep(self.state)["skipped"])
        pin(self.state, "batch", True)
        mark(self.state, "batch", last_activity=time.time() - 90 * DAY)
        self.assertIn("batch", sweep(self.state)["skipped"])
        self.assertTrue(work.exists())
        pin(self.state, "batch", False)
        sweep(self.state)
        self.assertTrue(work.exists())

    def test_unregistered_and_unarchived_workspaces_are_not_removed(self):
        historic = self.state / "runs/historical"
        historic.mkdir(parents=True)
        self.batch()
        (self.state / "records/batch/complete.json").unlink()
        report = sweep(self.state)
        self.assertTrue(historic.exists())
        self.assertTrue((self.state / "runs/batch").exists())
        self.assertTrue(report["warnings"])

    def test_cache_age_and_pin_dependencies(self):
        self.batch()
        cache = self.state / "cache/snapshots/hash"
        cache.mkdir(parents=True)
        (cache / "input.md").write_text("resource")
        used = register_cache(self.state, [{"path": str(cache)}])
        self.assertEqual(used, ["snapshots/hash"])
        write_json(self.state / "retention-cache.json", {"snapshots/hash": time.time() - 31 * DAY})
        mark(self.state, "batch", cache=used, pinned=True)
        sweep(self.state)
        self.assertTrue(cache.exists())
        pin(self.state, "batch", False)
        sweep(self.state)
        self.assertFalse(cache.exists())

    def test_archive_failure_has_no_completion_marker(self):
        self.batch()
        summary = {"build_id": "batch", "entities": []}
        with patch("creation_pipeline.retention.write_json", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                archive(self.state, self.state / "outputs/batch", summary, {}, [])
        self.assertFalse((self.state / "records/batch/complete.json").exists())
        sweep(self.state)
        self.assertTrue((self.state / "runs/batch").exists())

    def test_interrupted_direct_draft_survives_archive(self):
        work = self.batch()
        draft = work / "bundle/skills/a/SKILL.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("partial skill")
        dest = archive(self.state, self.state / "outputs/batch", {"build_id": "batch", "entities": []}, {}, [])
        self.assertEqual((dest / "skills/a/draft/SKILL.md").read_text(), "partial skill")

    def test_escaping_registry_path_is_rejected(self):
        write_json(self.state / "retention/unsafe.json", {"build_id": "../outside", "last_activity": 0})
        with self.assertRaises(ValueError):
            sweep(self.state)

    def test_linked_workspace_is_not_deleted(self):
        work = self.batch()
        from creation_pipeline import records
        original = records.has_link
        with patch("creation_pipeline.records.has_link", side_effect=lambda p: Path(p) == work or original(p)):
            report = sweep(self.state)
        self.assertTrue(work.exists())
        self.assertTrue(report["warnings"])

    def test_age_boundary_and_active_cache_protection(self):
        work = self.batch()
        stamp = time.time()
        mark(self.state, "batch", last_activity=stamp)
        sweep(self.state, clock=stamp + 7 * DAY - 1)
        self.assertTrue(work.exists())
        cache = self.state / "cache/snapshots/new"
        cache.mkdir(parents=True)
        write_json(self.state / "retention-cache.json", {"snapshots/new": 0})
        with lease(self.state, "batch"):
            sweep(self.state, clock=stamp + 100 * DAY)
        self.assertTrue(cache.exists())
        sweep(self.state, clock=stamp + 7 * DAY)
        self.assertFalse(work.exists())


class UsageTests(unittest.TestCase):
    def test_cumulative_sessions_and_unknown_are_not_summed_twice(self):
        def r(sid, n, **kwargs):
            return {"session_id": sid, "usage_mode": "session_cumulative", "usage": {"input_tokens": n}, **kwargs}
        result = summarize_usage([r("a", 10), r("a", 30), r("b", 5), {"usage": None}])
        self.assertEqual(result["reported_totals"]["input_tokens"], 35)
        self.assertEqual(result["usage_unknown_calls"], 1)

    def test_incremental_and_counter_reset(self):
        result = summarize_usage([
            {"session_id": "a", "usage_mode": "session_cumulative", "usage": {"input_tokens": n}}
            for n in (10, 2, 5)] + [{"usage_mode": "incremental", "usage": {"input_tokens": 3}}])
        self.assertEqual(result["reported_totals"]["input_tokens"], 18)


class HistoricalCacheTests(unittest.TestCase):
    setUp = RetentionTests.setUp
    tearDown = RetentionTests.tearDown
    def test_preexisting_cache_not_enrolled_in_deletion(self):
        from creation_pipeline.retention import initialize
        cache = self.state / "cache/snapshots/historical"
        cache.mkdir(parents=True)
        initialize(self.state)
        register_cache(self.state, [{"path": str(cache)}])
        self.assertNotIn("snapshots/historical", read_json(self.state / "retention-cache.json"))
        sweep(self.state, clock=time.time()+100*DAY)
        self.assertTrue(cache.exists())
