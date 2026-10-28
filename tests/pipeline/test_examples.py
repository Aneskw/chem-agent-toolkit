"""Curated records must point to real pure packages without local-machine paths."""
import json
import re
import unittest
from pathlib import Path

from creation_pipeline.paths import ROOT
from creation_pipeline.models import load_config
from creation_pipeline.artifacts.package import manifest


class ExampleTests(unittest.TestCase):
    def batches(self):
        batches = sorted(p.parent for p in (ROOT / "examples").glob("*/input.json"))
        self.assertTrue(batches, "At least one complete curated batch must be published")
        return batches

    def test_inputs_are_reusable_without_local_machine_paths(self):
        for batch in self.batches():
            config = load_config(batch / "input.json")
            self.assertTrue(config["sources"])
            for path in batch.rglob("*.json"):
                text = path.read_text(encoding="utf-8")
                json.loads(text)
                self.assertIsNone(re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/", text), str(path))

    def test_recorded_packages_match_the_single_authoritative_skill(self):
        for batch in self.batches():
            skills = json.loads((batch / "skills.json").read_text(encoding="utf-8"))
            self.assertTrue(skills)
            self.assertFalse((batch / "skills").exists(), "Do not duplicate runtime packages in examples")
            for item in skills:
                package = (batch / item["path"]).resolve()
                self.assertTrue(package.is_relative_to(ROOT / "skills"))
                self.assertEqual(manifest(package), item["files"])
                self.assertTrue((batch / "records" / item["name"] / "basis.json").is_file())
                review = json.loads((batch / "records" / item["name"] / "review.json").read_text(encoding="utf-8"))
                self.assertEqual(review["status"], "ready")
                self.assertTrue(any(c["name"] == "content_review" and c["status"] == "pass" for c in review["checks"]))

    def test_basis_references_have_portable_source_locators(self):
        for batch in self.batches():
            sources = json.loads((batch / "sources.json").read_text(encoding="utf-8"))
            locators = {item["id"]: item for item in sources["locators"]}
            for path in (batch / "records").glob("*/basis.json"):
                for item in json.loads(path.read_text(encoding="utf-8")):
                    self.assertIn(item["source"], locators)
                    self.assertTrue(locators[item["source"]]["url"].startswith("https://"))
