"""Supplement policy, registration and native CLI wiring without live searches."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.pipeline import test_native as native
from creation_pipeline.models import load_config
from creation_pipeline.records import read_json, write_json
from creation_pipeline.resources.policy import search_mode, instructions
from creation_pipeline.resources.supplements import register, restore
from creation_pipeline.resources.workspace import prepare
from creation_pipeline.agent.backend import NativeSession


class ResearchAccessTests(unittest.TestCase):
    def setUp(self):
        self.case = native.NativeTests()
        self.case.setUp()

    def tearDown(self):
        self.case.tearDown()

    def definition(self, **updates):
        c = self.case
        saved = c.work / "retrieved.md"
        saved.write_text("Official source excerpt: addition returns the numeric sum.", encoding="utf-8")
        data = {"path": str(saved), "url": "https://example.org/official/api", "reason": "Confirm returned value",
                "related_to": list(c.sources.entries), "version": "fixed-version", "representation": "excerpt"}
        data.update(updates)
        path = c.work / "register.json"
        write_json(path, data)
        return path

    def prepare(self, network=True):
        self.case.config["network"] = network
        prepare(self.case.sources, self.case.work)

    def test_modes_are_explicit_and_network_overrides_search(self):
        self.assertEqual(search_mode({"network": True, "research_access": "supplement"}), "live")
        self.assertEqual(search_mode({"network": True, "research_access": "known_only"}), "disabled")
        self.assertEqual(search_mode({"network": False, "research_access": "supplement"}), "disabled")
        self.assertEqual(search_mode({"network": True}), "disabled")  # Legacy session safety.

    def test_policy_anchors_to_input_and_separates_execution_permission(self):
        text = instructions({"network": True, "research_access": "supplement"})
        self.assertIn("never independently justify an unrelated candidate", text)
        self.assertIn("Networking does not authorize installation", text)
        self.assertIn("Search snippets are navigation", text)

    def test_configuration_default_and_invalid_policy(self):
        data = read_json(self.case.root / "input.json")
        self.assertEqual(load_config(self.case.root / "input.json")["research_access"], "supplement")
        data["research_access"] = "unrestricted"
        write_json(self.case.root / "input.json", data)
        with self.assertRaises(ValueError):
            load_config(self.case.root / "input.json")

    def test_saved_native_resource_is_snapshotted_and_locators_stay_stable(self):
        self.prepare()
        before = copy.deepcopy(self.case.sources.evidence)
        definition = self.definition()
        result = register(self.case.work, definition)
        self.assertEqual(result["status"], "registered")
        sources = restore(self.case.work)
        self.assertEqual(sources.evidence[:len(before)], before)
        entry = sources.entries[result["source"]]
        self.assertTrue(entry["supplemental"])
        self.assertEqual(entry["related_to"], list(self.case.sources.entries))
        Path(read_json(definition)["path"]).unlink()
        sources.verify()
        fresh = NativeSession(self.case.config, sources, self.case.config["limits"].copy(), self.case.work)
        self.assertIn(result["source"], fresh.sources.entries)

    def test_duplicate_registration_is_reused(self):
        self.prepare()
        definition = self.definition()
        first = register(self.case.work, definition)
        again = register(self.case.work, definition)
        self.assertEqual(first["source"], again["source"])
        self.assertEqual(len(restore(self.case.work).entries), len(self.case.sources.entries) + 1)

    def test_missing_or_supplemental_anchor_is_rejected(self):
        self.prepare()
        for related in ([], ["made-up"]):
            with self.subTest(related=related), self.assertRaises(ValueError):
                register(self.case.work, self.definition(related_to=related))
        first = register(self.case.work, self.definition())
        with self.assertRaises(ValueError):
            register(self.case.work, self.definition(related_to=[first["source"]]))

    def test_registration_cannot_escape_workspace(self):
        self.prepare()
        with self.assertRaises(ValueError):
            register(self.case.work, self.definition(path=str(self.case.root / "input.json")))

    def test_url_without_saved_material_is_not_evidence(self):
        self.prepare()
        with self.assertRaises(ValueError):
            register(self.case.work, self.definition(path=str(self.case.work / "missing.md")))

    def test_network_false_blocks_remote_registration(self):
        self.prepare(network=False)
        with self.assertRaisesRegex(ValueError, "network=false"):
            register(self.case.work, self.definition())

    def test_actual_cli_arguments_follow_policy_including_resume(self):
        c = self.case
        c.config.update(network=True, research_access="supplement")
        session = c.session()
        with patch("creation_pipeline.agent.backend.codex_command", return_value=[sys.executable, str(c.fake)]):
            session.stage("test", {}, {})
            session.stage("test", {}, {})
        argv = read_json(c.root / "argv.json")
        self.assertIn('web_search="live"', argv)
        self.assertIn("sandbox_workspace_write.network_access=true", argv)
        self.assertEqual(session.receipts[0]["search_events"], 0)
        self.assertEqual(session.receipts[0]["search_mode"], "live")
        self.assertIn("Scoped supplemental research", (c.work / "agent-turns/002-discovery/prompt.txt").read_text())

    def test_offline_cli_disables_both_paths(self):
        c = self.case
        c.config.update(network=False, research_access="supplement")
        with patch("creation_pipeline.agent.backend.codex_command", return_value=[sys.executable, str(c.fake)]):
            c.session().stage("test", {}, {})
        argv = read_json(c.root / "argv.json")
        self.assertIn('web_search="disabled"', argv)
        self.assertIn("sandbox_workspace_write.network_access=false", argv)
