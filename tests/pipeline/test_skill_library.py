import copy
from pathlib import Path
import unittest
from tests.pipeline.test_discovery import discovery, candidate
from tests.pipeline import test_discovery as fixtures
from tests.pipeline.support import ARTIFACT
from creation_pipeline.records import write_json, read_json
from creation_pipeline.validation.acceptance import certify, require_ready


class SkillLibraryTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.DiscoveryTests()
        self.case.setUp()
        self.case.options["adoption"] = {"enabled": True}
        write_json(self.case.config, self.case.options)
        self.library = self.case.root / "skills"

    def tearDown(self):
        self.case.tearDown()

    def test_flat_pure_package_and_compact_record(self):
        result, _ = self.case.run_case(discovery(candidate()), ARTIFACT, library_root=self.library)
        self.assertEqual(result["status"], "ready", result)
        self.assertEqual([p.name for p in (self.library / "add-numbers").iterdir()], ["SKILL.md"])
        record = Path(result["output"]) / "skills/add-numbers"
        self.assertTrue((record / "basis.json").exists())
        self.assertFalse((record / "draft").exists())
        self.assertFalse((record / "package").exists())

    def test_idempotent_adoption_and_name_conflict_preserve_new_package(self):
        first, _ = self.case.run_case(discovery(candidate()), ARTIFACT, library_root=self.library)
        second, _ = self.case.run_case(discovery(candidate()), ARTIFACT, library_root=self.library)
        self.assertEqual(second["adoption"][0]["status"], "already_present")
        changed = copy.deepcopy(ARTIFACT)
        changed["files"][0]["content"] += "\nNew note.\n"
        third, _ = self.case.run_case(discovery(candidate()), changed, library_root=self.library)
        self.assertEqual(third["adoption"][0]["status"], "conflict")
        self.assertTrue((Path(third["output"]) / "skills/add-numbers/package/SKILL.md").exists())

    def test_partial_batch_adopts_successful_skill(self):
        result, _ = self.case.run_case(discovery(candidate(), candidate("blocked-skill", readiness="blocked", gaps=["missing code"])), ARTIFACT, library_root=self.library)
        self.assertEqual(result["status"], "partial", result)
        self.assertTrue((self.library / "add-numbers/SKILL.md").exists())

    def test_tampered_receipt_cannot_approve(self):
        record = certify({"name": "x", "status": "ready", "files": [], "basis": ["basis"],
                          "checks": [{"name": "content_review", "status": "pass", "required": True}]})
        require_ready(record)
        record["basis"] = ["changed"]
        with self.assertRaises(ValueError):
            require_ready(record)

    def test_no_adopt_archive_can_be_checked_and_installed_flat(self):
        from creation_pipeline.artifacts.package import archive_packages, install
        result, _ = self.case.run_case(discovery(candidate()), ARTIFACT, no_adopt=True)
        summary, packages = archive_packages(result["output"])
        self.assertEqual(len(packages), 1)
        require_ready(packages[0][0])
        installed = install(result["output"], self.library)
        self.assertTrue((self.library / "add-numbers/SKILL.md").exists())
