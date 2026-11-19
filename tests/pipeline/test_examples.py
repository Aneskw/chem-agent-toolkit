"""Portable configurations and traceable, curated workflow examples."""
import contextlib
import io
import json
import re
import unittest
from unittest.mock import patch

from creation_pipeline.paths import ROOT
from creation_pipeline.models import load_config
from creation_pipeline.cli import main


class ExampleTests(unittest.TestCase):
    def batches(self):
        batches = sorted(p.parent for p in (ROOT / "examples").glob("*/input.json"))
        self.assertTrue(batches, "At least one reusable configuration must be published")
        return batches

    def test_inputs_are_reusable_without_local_machine_paths(self):
        for batch in self.batches():
            config = load_config(batch / "input.json")
            self.assertTrue(config["sources"])
            for path in batch.rglob("*.json"):
                text = path.read_text(encoding="utf-8")
                json.loads(text)
                self.assertIsNone(re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/", text), str(path))

    def test_example_preflight_does_not_start_a_build(self):
        for batch in self.batches():
            output = io.StringIO()
            with patch("creation_pipeline.cli.build") as build, contextlib.redirect_stdout(output):
                self.assertEqual(main(["build", str(batch / "input.json"), "--preflight"]), 0)
            build.assert_not_called()
            result = json.loads(output.getvalue())
            self.assertEqual(result["status"], "configuration_valid")
            self.assertEqual(result["model_calls"], 0)
            self.assertEqual(result["source_availability"], "not_checked")

    def test_edbo_example_uses_unlimited_production_defaults(self):
        config = load_config(ROOT / "examples/edbo-reaction-optimization/input.json")
        self.assertEqual(config["execution"]["profile"], "production")
        for key in ("max_candidates", "max_builds", "model_calls", "repair_rounds"):
            self.assertIsNone(config["limits"][key])

    def test_recorded_edbo_workflow_has_resolvable_evidence_and_packages(self):
        batch = ROOT / "examples/edbo-reaction-optimization"

        def read(path):
            return json.loads((batch / path).read_text(encoding="utf-8"))

        summary = read("summary.json")
        recorded = load_config(batch / "recorded-input.json")
        for key, value in summary["development_limits"].items():
            self.assertEqual(recorded["limits"][key], value)
        locators = {item["id"]: item for item in read("sources.json")["locators"]}
        candidates = {item["name"] for item in read("discovery.json")["candidates"]}
        packages = read("skills.json")
        self.assertEqual({item["name"] for item in packages}, set(summary["accepted"]))
        self.assertTrue(set(summary["accepted"] + summary["deferred"]) <= candidates)
        for item in packages:
            package = (batch / item["path"]).resolve()
            self.assertTrue(package.is_relative_to(ROOT / "skills"))
            self.assertTrue((package / "SKILL.md").is_file())
            review = read(f"records/{item['name']}/review.json")
            self.assertEqual(review["status"], "ready")
            # Recorded evidence must agree internally; maintained package bytes may change.
            self.assertEqual(review["files"], item["files"])
            for entry in read(f"records/{item['name']}/basis.json"):
                locator = locators[entry["source"]]
                self.assertTrue(locator["url"].startswith("https://"))
                self.assertEqual(entry["sha256"], locator["sha256"])
