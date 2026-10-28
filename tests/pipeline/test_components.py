"""Deterministic pipeline tests; fixture responses are not new model evidence."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from creation_pipeline.validation.checks import classify, static_checks
from creation_pipeline.resources.intake import Sources
from creation_pipeline.models import BlockedError, load_config
from creation_pipeline.artifacts.package import install, manifest, verify_output
from creation_pipeline.generation.discovery import ROOT
from creation_pipeline.records import clean_run, digest, read_json, safe_relative, write_json


from tests.pipeline.support import MAIN, PLAN, ARTIFACT, write_fixture_files


class PipelineTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / ".pipeline/test-tmp"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "adder.py").write_text('def add(a, b):\n    """Return a+b. Example: add(2,3)==5."""\n    return a+b\n', encoding="utf-8")
        self.config = self.root / "build.json"
        self.options = {"sources": [{"id": "tool", "path": "source"}], "limits": {"repair_rounds": 1}}
        write_json(self.config, self.options)
        self.state = self.root / "state"

    def tearDown(self):
        self.temp.cleanup()


    def test_clean_requires_registration_and_supports_dry_run(self):
        run = self.state / "runs/example"
        run.mkdir(parents=True)
        (run / "user.txt").write_text("keep", encoding="utf-8")
        with self.assertRaises((ValueError, OSError)):
            clean_run(self.state, "example")
        write_json(run / "workspace.json", {"build_id": "example", "workspace": str(run.resolve())})
        clean_run(self.state, "example", dry_run=True)
        self.assertTrue(run.exists())
        clean_run(self.state, "example")
        self.assertFalse(run.exists())
        self.assertTrue(self.source.exists())

    def test_path_escapes_and_windows_drives_are_rejected(self):
        for name in ("../source/adder.py", "C:/windows/file", "x/../../y", "x:secret", "/etc/test", "x//y", "scripts/NUL.py", "x. "):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_relative(self.root, name)

    def test_generated_file_roles_and_credential_literals_are_rejected(self):
        for path, content in (("../outside.md", "text"), ("build.json", "text"),
                              ("scripts/key.py", 'api_key="sk-1234567890123456"')):
            files = copy.deepcopy(ARTIFACT["files"])
            files.append({"path": path, "content": content, "purpose": "test"})
            with self.subTest(path=path), self.assertRaises(ValueError):
                write_fixture_files(self.root / "package", files, 10000)

    def test_missing_link_and_python_syntax_are_reported(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact["files"][0]["content"] += "\n[Details](references/missing.md)\n"
        artifact["files"].append({"path": "scripts/run.py", "content": "def broken(\n", "purpose": "bad script"})
        package = self.root / "package"
        write_fixture_files(package, artifact["files"], 10000)
        findings = static_checks(package)[0]["findings"]
        self.assertTrue(any("link" in s for s in findings))
        self.assertTrue(any("syntax" in s for s in findings))









if __name__ == "__main__":
    unittest.main()
