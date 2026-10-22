"""Deterministic pipeline tests; fixture responses are not new model evidence."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from creation_pipeline.checks import classify, run_checks, static_checks
from creation_pipeline.intake import Sources
from creation_pipeline.models import BlockedError, load_config
from creation_pipeline.model_backend import CodexBackend, disable_mcp_options
from creation_pipeline.package import install, manifest, save_files, verify_output
from creation_pipeline.analyze import ROOT
from creation_pipeline.records import clean_run, digest, read_json, safe_relative, write_json
from creation_pipeline.runtime import execute


MAIN = """---
name: add-numbers
description: Add two numeric inputs using the supplied tool.
---
# Add numbers
Use adder for numeric addition. This does not concatenate strings.
Inputs a and b are numbers; output is their sum.
```python
print(2 + 3)
```
Check that the result equals 5 for this example.
"""
COVERAGE = {"scope": "Use adder for numeric addition.", "io": "Inputs a and b are numbers; output is their sum.",
            "usage": "print(2 + 3)", "result_checks": "Check that the result equals 5 for this example."}
PLAN = {"name": "add-numbers", "task": "Add two numbers", "scope": "Numeric addition",
        "entrypoint": "adder.add(a,b)", "readiness": "callable", "intent": "direct", "added_behavior": "none",
        "dependencies": [], "files": [{"path": "SKILL.md", "purpose": "Instructions"}],
        "checks": ["2+3=5"], "evidence": [{"id": "e1", "claim": "Tool adds two numbers"}], "gaps": []}
ARTIFACT = {"files": [{"path": "SKILL.md", "content": MAIN, "purpose": "Instructions"}],
            "coverage": COVERAGE, "tests": [], "notes": []}


def response(value):
    return {"action": "complete", "payload": value}


class ReplayBackend:
    replay = True

    def __init__(self, values):
        self.values = iter(values)
        self.prompts = []

    def call(self, prompt, timeout, schema=None):
        self.prompts.append(prompt)
        return next(self.values), {"model": "deterministic-test-fixture", "usage": None}


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
                save_files(self.root / "package", files, 10000)

    def test_missing_link_and_python_syntax_are_reported(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact["files"][0]["content"] += "\n[Details](references/missing.md)\n"
        artifact["files"].append({"path": "scripts/run.py", "content": "def broken(\n", "purpose": "bad script"})
        package = self.root / "package"
        save_files(package, artifact["files"], 10000)
        findings = static_checks(package)[0]["findings"]
        self.assertTrue(any("link" in s for s in findings))
        self.assertTrue(any("syntax" in s for s in findings))

    def test_source_reads_are_bounded_and_evidence_is_real(self):
        sources = Sources(load_config(self.config), self.root / "cache")
        record = sources.request({"action": "read", "source": "tool", "path": "adder.py", "start": 1, "limit": 1})
        self.assertEqual(record["start"], record["end"])
        self.assertEqual(record["sha256"], digest((self.source / "adder.py").read_bytes()))
        with self.assertRaises(ValueError):
            sources.validate_evidence([{"id": "made-up", "claim": "x"}])
        with self.assertRaises(ValueError):
            sources.request({"action": "read", "source": "tool", "path": "../build.json"})

    def test_source_search_returns_locations_not_execution_claims(self):
        sources = Sources(load_config(self.config), self.root / "cache")
        record = sources.request({"action": "search", "source": "tool", "path": "adder.py", "query": "return"})
        self.assertEqual(record["total"], 2)
        self.assertEqual(sources.evidence, [])

    def test_large_single_line_is_paginated_and_duplicate_evidence_is_compact(self):
        (self.source / "long.txt").write_text("0123456789" * 500, encoding="utf-8")
        config = load_config(self.config)
        config["limits"]["view_chars"] = 100
        sources = Sources(config, self.root / "cache")
        action = {"action": "read", "source": "tool", "path": "long.txt", "start": 1, "limit": 1}
        first = sources.request(action)
        self.assertEqual(len(first["excerpt"]), 100)
        self.assertEqual(first["next_offset"], 100)
        sources.request(action)
        third = sources.request(dict(action, offset=100))
        self.assertEqual(third["offset"], 100)
        compact = sources.compact_evidence()
        self.assertEqual(compact[1]["excerpt_ref"], "e1")
        self.assertNotIn("excerpt", compact[1])

    def test_generated_checks_need_opt_in(self):
        config = load_config(self.config)
        config["checks"] = []
        sources = Sources(config, self.root / "cache")
        sources.request({"action": "read", "source": "tool", "path": "adder.py"})
        test = {"name": "suggested", "argv": ["{python}", "-c", "print(5)"], "stdout_contains": ["5"],
                "evidence": "e1", "purpose": "example"}
        results = run_checks(config, {"tests": [test]}, self.root, sources, self.root / "checks")
        self.assertEqual(classify(results), "draft")
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
        process = subprocess.run([sys.executable, str(ROOT / 'examples/verify_python_example.py'), str(package)],
                                 capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn('standalone-example', process.stdout)

    def test_timeout_kills_check_and_reports_failure(self):
        sources = Sources(load_config(self.config), self.root / "cache")
        test = {"name": "timeout", "argv": ["{python}", "-c", "import time; time.sleep(30)"], "stdout_contains": ["done"]}
        report = execute(test, self.root, sources, self.root / "check", 0.2, [])
        self.assertEqual(report["status"], "fail")
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

    def test_backend_requires_completed_turn_and_rejects_actual_tools(self):
        good = {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(response(PLAN))}}
        complete = {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}}
        for events, should_pass in (([good, complete], True), ([good], False),
                ([{"type": "item.completed", "item": {"type": "command_execution"}}, good, complete], False)):
            process = Mock(returncode=0)
            process.communicate.return_value = ("\n".join(json.dumps(e) for e in events), "")
            with self.subTest(events=events), patch("creation_pipeline.model_backend.codex_command", return_value=["codex"]), \
                    patch("creation_pipeline.model_backend.subprocess.Popen", return_value=process):
                backend = CodexBackend(scratch=self.root / "model")
                if should_pass:
                    answer, receipt = backend.call("test", 1)
                    self.assertEqual(answer["action"], "complete")
                    self.assertEqual(receipt["usage"]["input_tokens"], 10)
                else:
                    with self.assertRaises(ValueError):
                        backend.call("test", 1)

    def test_user_mcp_tables_are_explicitly_disabled_including_profile_servers(self):
        options = disable_mcp_options({"mcp_servers": {"user-server": {}}, "profile": "local",
            "profiles": {"local": {"mcp_servers": {"another-server": {}}}}})
        self.assertIn('mcp_servers.user-server.enabled=false', options)
        self.assertIn('mcp_servers.another-server.enabled=false', options)
        with self.assertRaises(ValueError):
            disable_mcp_options({"mcp_servers": {"unsupported.name": {}}})




if __name__ == "__main__":
    unittest.main()
