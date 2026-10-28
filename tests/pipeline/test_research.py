"""Research-resource regressions; no external models or network services."""
import base64
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from creation_pipeline.models import load_config, ModelCallError
from creation_pipeline.resources.intake import Sources, permitted
from creation_pipeline.records import write_json, read_json
from creation_pipeline.resources.workspace import prepare, sync_sources
from creation_pipeline.resources.supplements import supplement
from creation_pipeline.artifacts.delivery import finish, delivered, write_chunk
from creation_pipeline.validation.agent_checks import check
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.validation.checks import static_checks, run_checks
from creation_pipeline.agent.backend import NativeSession
from creation_pipeline.generation.author import author
from creation_pipeline.generation.discovery import normalize, validate_discovery
from tests.pipeline.support import MAIN


class ResearchTests(unittest.TestCase):
    def setUp(self):
        parent = Path(__file__).resolve().parents[2] / ".pipeline/test-tmp"
        parent.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.tmp.name).resolve()
        self.input = self.root / "input.json"
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "api.py").write_text("def add(a,b): return a+b\n", encoding="utf-8")
        self.raw = {"sources": [{"id": "tool", "path": "source"}], "network": False,
                    "adoption": {"enabled": False}}
        self.config = self.load()
        self.sources = Sources(self.config, self.root / "cache")
        self.work = self.root / "run"
        self.work.mkdir()
        prepare(self.sources, self.work)
        self.package = self.work / "bundle/skills/add-numbers"
        self.package.mkdir(parents=True)
        (self.package / "SKILL.md").write_text(MAIN, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def load(self):
        write_json(self.input, self.raw)
        return load_config(self.input)

    def test_production_has_no_implicit_size_count_or_agent_quotas(self):
        for key in ("model_timeout", "total_seconds", "model_calls", "candidate_calls", "agent_events",
                    "max_candidates", "max_builds", "source_bytes", "source_total_bytes", "source_files", "package_bytes"):
            self.assertIsNone(self.config["limits"][key], key)

    def test_development_is_opt_in_and_can_override_preset(self):
        self.raw["execution"] = {"profile": "development"}
        self.raw["limits"] = {"max_builds": 2, "model_calls": None}
        config = self.load()
        self.assertEqual(config["limits"]["max_builds"], 2)
        self.assertIsNone(config["limits"]["model_calls"])

    def test_unknown_api_backends_are_still_rejected_at_configuration(self):
        # codex_cli (default) and the opt-in deepseek_api are the only supported
        # native-stage backends; anything else fails before a call is made.
        for backend in ("chat_completions", "ollama"):
            self.raw["model"] = {"backend": backend, "name": "unused"}
            with self.assertRaisesRegex(ValueError, "must be codex_cli"):
                self.load()
        self.raw["model"] = {"backend": "deepseek_api", "api_model": "deepseek-v4-pro"}
        self.assertEqual(self.load()["model"]["backend"], "deepseek_api")

    def test_api_injection_is_not_a_public_entrypoint(self):
        import inspect
        from creation_pipeline.pipeline import build
        self.assertNotIn("backend", inspect.signature(build).parameters)
        self.assertFalse((Path(__file__).resolve().parents[2] / "creation_pipeline/providers.py").exists())

    def test_large_unknown_and_hidden_research_files_survive(self):
        (self.source / "array.h5").write_bytes(b"\0" * 2_100_000)
        (self.source / ".github").mkdir()
        (self.source / ".github/build.yml").write_text("name: useful instructions\n")
        (self.source / ".env.example").write_text("MODEL_ENDPOINT=\n")
        (self.source / "credential-guide.md").write_text("Use a named environment variable")
        (self.source / "results").mkdir()
        (self.source / "results/example.csv").write_text("id,value\n0,5\n")
        sources = Sources(self.config, self.root / "cache2")
        files = sources.entries["tool"]["files"]
        for file in ("array.h5", ".github/build.yml", ".env.example", "credential-guide.md", "results/example.csv"):
            self.assertIn(file, files)
        sources.verify()

    def test_narrow_exclusions_are_recorded(self):
        (self.source / "__pycache__").mkdir()
        (self.source / "__pycache__/compiled.pyc").write_bytes(b"cache")
        (self.source / ".env").write_text("secret")
        sources = Sources(self.config, self.root / "cache2")
        omitted = sources.entries["tool"]["omitted_preview"]
        self.assertTrue(any(e["path"] == "__pycache__" for e in omitted))
        self.assertNotIn(".env", sources.entries["tool"]["files"])

    def test_reference_storage_avoids_copy_but_detects_changes(self):
        original = self.source / "large.h5"
        original.write_bytes(b"original-data")
        self.raw["sources"] = [{"path": "source/large.h5", "storage": "reference"}]
        config = self.load()
        sources = Sources(config, self.root / "reference-cache")
        self.assertEqual(Path(sources.entries["source1"]["path"]), original)
        original.write_bytes(b"changed-data")
        with self.assertRaisesRegex(ValueError, "changed"):
            sources.verify()

    def test_inventory_pagination_does_not_exclude_other_files(self):
        from creation_pipeline.resources.supplements import inventory
        result = inventory(self.work, source="tool", limit=1)
        self.assertEqual(result["total"], 1)
        self.assertTrue(Path(result["items"][0]["original"]).exists())
        self.assertIn("pagination", result["note"])

    def test_incremental_candidate_has_valid_source_provenance(self):
        from creation_pipeline.generation.candidates import save_candidate
        candidate = {"name": "addition", "capability": "Add", "boundary": "numbers",
            "value": "Index convention", "usage_path": "api.add", "construction": "Use source directly",
            "evidence": [{"id": "e1", "claim": "api.py function add"}], "gaps": [], "blocked": False}
        definition = self.work / "candidate.json"
        write_json(definition, candidate)
        result = save_candidate(self.work, definition)
        self.assertEqual(result["candidate"], "addition")
        self.assertEqual(read_json(self.work / "candidates/addition.json"), candidate)
        candidate["evidence"][0]["id"] = "invented"
        write_json(definition, candidate)
        with self.assertRaises(ValueError):
            save_candidate(self.work, definition)

    def test_only_explicit_saved_candidates_are_selected(self):
        from creation_pipeline.generation.discovery import analyze
        candidate = {"name": "selected", "capability": "Add", "boundary": "numbers",
            "value": "Convention", "usage_path": "api.add", "construction": "Source usage",
            "evidence": [{"id": "e1", "claim": "api.py add"}], "gaps": [], "blocked": False}
        write_json(self.work / "candidates/selected.json", candidate)
        write_json(self.work / "candidates/old-unselected.json", dict(candidate, name="old-unselected"))
        session = NativeSession(self.config, self.sources, copy.deepcopy(self.config["limits"]), self.work)
        result = {"outcome": "candidates", "summary": "Selected from inspected source",
            "candidates": [], "saved_candidates": ["selected"], "omitted": [], "limitations": []}
        with patch.object(session, "stage", return_value=result):
            plan = analyze(session, self.config)
        self.assertEqual([c["name"] for c in plan["candidates"]], ["selected"])

    def test_reviewed_unexecuted_scope_is_retained_in_catalog(self):
        from tests.pipeline.test_discovery import DiscoveryTests, candidate, discovery
        from tests.pipeline.test_components import ARTIFACT
        case = DiscoveryTests()
        case.setUp()
        try:
            case.options["checks"] = []
            case.options["adoption"] = {"enabled": True}
            write_json(case.config, case.options)
            result, _ = case.run_case(discovery(candidate()), copy.deepcopy(ARTIFACT), library_root=case.root / "library")
            self.assertEqual(result["status"], "blocked")
            catalog = read_json(case.root / "library/catalog.json")
            self.assertTrue(catalog["skills"][0]["unverified"])
        finally:
            case.tearDown()

    def test_review_cannot_pass_its_own_blocking_finding(self):
        from creation_pipeline.generation.author import review
        from tests.pipeline.test_discovery import candidate
        session = NativeSession(self.config, self.sources, copy.deepcopy(self.config["limits"]), self.work)
        response = {"status": "pass", "resolution": "none", "findings": [
            {"location": "SKILL.md", "problem": "Wrong interface", "evidence": "api.py",
             "impact": "Cannot call", "action": "Use add", "blocking": True, "category": "file"}]}
        with patch.object(session, "stage", return_value=response):
            report = review(session, candidate(), {"files": []}, [], self.config)
        self.assertEqual(report["status"], "fail")

    def test_credentials_in_direct_files_are_rejected(self):
        (self.package / "SKILL.md").write_text(MAIN + "\napi_key=sk-1234567890123456", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "credential"):
            finish(self.work, self.package, "token")

    def test_discovery_and_review_cannot_finalize_runtime_files(self):
        for phase in ("discovery", "review"):
            write_json(self.work / "active-phase.json", {"phase": phase})
            with self.assertRaisesRegex(ValueError, "author stage"):
                finish(self.work, self.package, "token")
            with self.assertRaisesRegex(ValueError, "must not write"):
                write_chunk(self.package, "SKILL.md", base64.b64encode(b"overwritten").decode())
        write_json(self.work / "active-phase.json", {"phase": "author"})
        finish(self.work, self.package, "token")

    def test_supplement_is_registered_cached_and_survives_new_session(self):
        self.config["network"] = True
        prepare(self.sources, self.work)
        extra = self.root / "supplement.md"
        extra.write_text("A concrete missing API detail", encoding="utf-8")
        with patch("creation_pipeline.resources.acquisition.Acquisition.download", return_value=(extra, {"resolved_url": "https://example.org/supplement.md"})) as fetch:
            first = supplement(self.work, {"url": "https://example.org/supplement.md"}, "Clarify return semantics")
            second = supplement(self.work, {"url": "https://example.org/supplement.md"}, "Same uncertainty")
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(second["status"], "cached")
        original = Sources(self.config, self.root / "cache")
        restored = NativeSession(self.config, original, copy.deepcopy(self.config["limits"]), self.work)
        self.assertIn(first["source"], restored.sources.entries)
        self.assertEqual(len(restored.sources.evidence), 2)

    def test_unavailable_supplement_preserves_existing_sources(self):
        report = supplement(self.work, {"url": "https://example.org/missing"}, "Need missing example")
        self.assertEqual(report["status"], "unavailable")
        sync_sources(self.sources, self.work)
        self.assertIn("tool", self.sources.entries)
        self.assertTrue(self.sources.errors)

    def test_durable_delivery_supports_binary_and_rejects_stale_files(self):
        (self.package / "assets").mkdir()
        (self.package / "assets/example.png").write_bytes(b"\x89PNG\0binary")
        (self.package / "scripts").mkdir()
        (self.package / "scripts/__init__.py").touch()
        finish(self.work, self.package, "candidate-token")
        self.assertEqual(len(delivered(self.work, self.package, "candidate-token")["files"]), 3)
        self.assertTrue(all(r["status"] == "pass" for r in static_checks(self.package)))
        (self.package / "SKILL.md").write_text(MAIN + "changed", encoding="utf-8")
        self.assertIsNone(delivered(self.work, self.package, "candidate-token"))

    def test_writer_small_chunks_and_path_boundaries(self):
        write_chunk(self.package, "references/detail.md", base64.b64encode(b"first\n").decode())
        write_chunk(self.package, "references/detail.md", base64.b64encode(b"second\n").decode(), True)
        self.assertEqual((self.package / "references/detail.md").read_text(), "first\nsecond\n")
        with self.assertRaises(ValueError):
            write_chunk(self.package, "../outside", base64.b64encode(b"bad").decode())

    def test_finalized_files_recover_even_without_final_model_json(self):
        from tests.pipeline.test_discovery import candidate
        session = NativeSession(self.config, self.sources, copy.deepcopy(self.config["limits"]), self.work)
        def incomplete(instructions, context, schema=None):
            finish(self.work, self.package, context["delivery_token"])
            raise ModelCallError("Final response missing after files were saved")
        with patch.object(session, "stage", side_effect=incomplete):
            artifact = author(session, self.config, candidate(), self.package)
        self.assertTrue(artifact["completed"])
        self.assertNotIn("coverage", artifact)

    def test_check_permission_is_respected_by_review_helper(self):
        definition = self.work / "check.json"
        write_json(definition, {"name": "should-not-run", "argv": ["does-not-exist"], "stdout_contains": ["result"]})
        report = check(self.work, self.package, definition)
        self.assertEqual(report["status"], "not_run")
        self.assertTrue((self.work / "agent-checks.jsonl").exists())

    def test_python_blocks_are_not_blindly_executed(self):
        (self.package / "SKILL.md").write_text(MAIN + '\n```python\nraise RuntimeError("illustration")\n```\n', encoding="utf-8")
        reports = run_checks(self.config, {"tests": []}, self.package, self.sources, self.work / "checks", True)
        self.assertFalse(any(r["status"] == "fail" for r in reports))
        self.assertTrue(any(r["status"] == "not_run" for r in reports))

    def test_compact_candidates_allow_mixed_blocked_and_callable(self):
        common = {"name": "capability", "capability": "Addition", "boundary": "numbers",
            "value": "Input convention", "usage_path": "api.add", "construction": "Direct source usage",
            "evidence": [{"id": "e1", "claim": "api.py add implementation"}], "gaps": [], "blocked": False}
        blocked = dict(common, name="missing-capability", blocked=True, gaps=["Method code missing"])
        discovery = normalize({"summary": "Checked source", "candidates": [common, blocked], "omitted": [], "limitations": []})
        validate_discovery(discovery, self.config, self.sources)
        self.assertEqual(discovery["candidates"][0]["readiness"], "callable")
        self.assertEqual(discovery["candidates"][1]["readiness"], "blocked")


if __name__ == "__main__":
    unittest.main()
