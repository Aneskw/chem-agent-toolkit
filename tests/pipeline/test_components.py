"""Deterministic pipeline tests; fixture responses are not new model evidence."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from creation_pipeline.validation.checks import classify, run_checks, static_checks
from creation_pipeline.resources.intake import Sources
from creation_pipeline.models import BlockedError, load_config
from creation_pipeline.artifacts.package import install, manifest, verify_output
from creation_pipeline.generation.discovery import ROOT
from creation_pipeline.records import clean_run, digest, read_json, safe_relative, write_json
from creation_pipeline.validation.runtime import execute


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
        self.options = {"task": "Add two numbers", "sources": [{"id": "tool", "path": "source"}],
                        "limits": {"repair_rounds": 1}, "checks": [{"candidate": "add-numbers", "name": "actual-tool-result",
                        "argv": ["{python}", "-c", "import sys; sys.path.insert(0,sys.argv[1]); from adder import add; print(add(2,3))", "{source:tool}"],
                        "stdout_contains": ["5"]}]}
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

    def test_generated_checks_need_opt_in(self):
        config = load_config(self.config)
        config["checks"] = []
        sources = Sources(config, self.root / "cache")
        from creation_pipeline.resources.workspace import prepare
        prepare(sources, self.root / "agent-run")
        test = {"name": "suggested", "argv": ["{python}", "-c", "print(5)"], "stdout_contains": ["5"],
                "evidence": "e1", "purpose": "example"}
        results = run_checks(config, {"tests": [test]}, self.root, sources, self.root / "checks")
        self.assertFalse(any(r["status"] == "pass" for r in results))
        self.assertFalse(any(r["required"] for r in results))
        self.assertFalse((self.root / "checks").exists())


    def test_expected_failure_and_json_assertions(self):
        config = load_config(self.config)
        sources = Sources(config, self.root / "cache")
        test = {"name": "rejected", "argv": ["{python}", "-c", 'import json,sys; print(json.dumps({"ok":False})); sys.exit(2)'],
                "expected_exit": 2, "json_equals": {"ok": False}}
        report = execute(test, self.root, sources, self.root / "check", 10, [])
        self.assertEqual(report["status"], "pass")

    def test_check_can_use_explicit_source_directory_without_moving_logs(self):
        sources = Sources(load_config(self.config), self.root / 'cache')
        test = {'name': 'relative-resource', 'argv': ['{python}', '-c', "from pathlib import Path; print('def add' in Path('adder.py').read_text())"],
                'cwd': '{source:tool}', 'stdout_contains': ['True']}
        work = self.root / 'cwd-check'
        report = execute(test, self.root, sources, work, 10, [])
        self.assertEqual(report['status'], 'pass')
        self.assertTrue((work / 'stdout.log').exists())
        self.assertEqual(report['cwd'], sources.entries['tool']['path'])

    def test_example_verifier_does_not_leak_its_arguments(self):
        import subprocess
        import sys
        package = self.root / 'example'
        package.mkdir()
        (package / 'SKILL.md').write_text('```python\nimport sys\nassert len(sys.argv) == 1\nprint("standalone-example")\n```\n', encoding='utf-8')
        process = subprocess.run([sys.executable, str(ROOT / 'creation_pipeline/validation/example_runner.py'), str(package)],
                                 capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn('standalone-example', process.stdout)

    def test_timeout_kills_check_and_records_unverified(self):
        sources = Sources(load_config(self.config), self.root / "cache")
        test = {"name": "timeout", "argv": ["{python}", "-c", "import time; time.sleep(30)"], "stdout_contains": ["done"]}
        report = execute(test, self.root, sources, self.root / "check", 0.2, [])
        self.assertEqual(report["status"], "not_run")
        self.assertTrue(any("timeout" in s for s in report["findings"]))

    def test_arbitrary_environment_is_not_inherited(self):
        sources = Sources(load_config(self.config), self.root / "cache")
        os.environ["PIPELINE_TEST_SECRET"] = "private-test-value-123456"
        try:
            test = {"name": "environment", "argv": ["{python}", "-c", 'import os; print(os.getenv("PIPELINE_TEST_SECRET", "absent"))'],
                    "stdout_contains": ["absent"]}
            report = execute(test, self.root, sources, self.root / "check", 10, [])
            self.assertEqual(report["status"], "pass")
        finally:
            del os.environ["PIPELINE_TEST_SECRET"]


if __name__ == "__main__":
    unittest.main()
