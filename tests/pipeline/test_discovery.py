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
from tests.pipeline.support import MAIN, PLAN, ARTIFACT, ReplayStages, response


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
            "adoption": {"enabled": False}, "limits": {"repair_rounds": 1}}
        write_json(self.config, self.options)
        self.state = self.root / "state"

    def tearDown(self):
        self.temp.cleanup()

    def run_case(self, *values, **kwargs):
        backend = ReplayStages([response(v) for v in values])
        self.last_backend = backend
        result = build(self.config, self.state, _session_factory=backend, **kwargs)
        return result, read_json(Path(result["output"]) / "summary.json")

    def test_no_task_and_no_runtime_required(self):
        result, summary = self.run_case(discovery(candidate()), ARTIFACT)
        self.assertEqual(result["status"], "ready", result)
        output = Path(result["output"])
        self.assertEqual((output / "skills/add-numbers/package/SKILL.md").read_text(), MAIN)
        self.assertFalse((self.state / "runs" / result["build_id"]).exists())
        self.assertFalse((self.state / "outputs" / result["build_id"]).exists())
        self.assertEqual(len(self.last_backend.prompts), 3)

    def test_no_candidates_is_normal_completion(self):
        result, _ = self.run_case(discovery())
        self.assertEqual(result["status"], "no_candidates")

    def test_failed_draft_is_archived_and_work_retained(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact["files"][0]["content"] += "\n[missing](references/missing.md)"
        result, _ = self.run_case(discovery(candidate()), artifact, artifact)
        self.assertNotEqual(result["status"], "ready")
        self.assertTrue((Path(result["output"]) / "skills/add-numbers/draft/SKILL.md").exists())
        self.assertTrue((self.state / "runs" / result["build_id"]).exists())

    def test_retired_execution_fields_are_rejected(self):
        for key,value in (("checks", []), ("execute_generated_checks", False), ("environment", {})):
            with self.subTest(key=key):
                write_json(self.config, {**self.options, key: value})
                with self.assertRaisesRegex(ValueError, "retired"):
                    load_config(self.config)

    def test_source_context_cannot_be_forged(self):
        from creation_pipeline.resources.intake import Sources
        sources = Sources(load_config(self.config), self.root / "cache")
        root = Path(sources.entries["tool"]["path"])
        root.write_text("tamper")
        with self.assertRaisesRegex(ValueError, "snapshot"):
            sources.verify()

    def test_cli_failure_stops_before_resource_acquisition(self):
        from creation_pipeline.models import ModelCallError
        with patch("creation_pipeline.pipeline.NativeSession.preflight", side_effect=ModelCallError("connection failed")), patch("creation_pipeline.pipeline.Sources") as acquire:
            result = build(self.config, self.state)
        self.assertEqual(result["status"], "failed")
        acquire.assert_not_called()
