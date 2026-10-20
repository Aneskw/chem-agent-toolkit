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
from creation_pipeline.pipeline import ROOT, build
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

    def call(self, prompt, timeout, schema=None):
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
                        "limits": {"repair_rounds": 1}, "checks": [{"name": "actual-tool-result",
                        "argv": ["{python}", "-c", "import sys; sys.path.insert(0,sys.argv[1]); from adder import add; print(add(2,3))", "{source:tool}"],
                        "stdout_contains": ["5"]}]}
        write_json(self.config, self.options)
        self.state = self.root / "state"

    def tearDown(self):
        self.temp.cleanup()

    def backend(self, *artifacts, plan=None):
        return ReplayBackend([{"action": "read", "source": "tool", "path": "adder.py", "start": 1, "limit": 50},
                              response(plan or PLAN), *[response(a) for a in (artifacts or (ARTIFACT,))]])

    def run_build(self, *artifacts, plan=None, **kw):
        result = build(self.config, self.state, backend=self.backend(*artifacts, plan=plan), **kw)
        return result, read_json(Path(result["output"]) / "build.json")

    def test_compact_build_keeps_verbatim_files_and_cleans_only_work(self):
        result, record = self.run_build()
        self.assertEqual(result["status"], "ready")
        output = Path(result["output"])
        self.assertEqual((output / "add-numbers/SKILL.md").read_text(encoding="utf-8"), MAIN)
        self.assertEqual(len(record["files"]), 1)
        self.assertTrue(record["replay"])
        self.assertIsNone(record["model_metrics"]["reported_token_totals"])
        self.assertFalse((self.state / "runs" / result["build_id"]).exists())
        self.assertTrue((self.source / "adder.py").exists())
        verify_output(output)

    def test_missing_source_is_blocked_and_keeps_error_record(self):
        self.options["sources"][0]["path"] = "missing"
        write_json(self.config, self.options)
        result, record = self.run_build()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("Missing source", record["error"])

    def test_readiness_blocker_does_not_author_files(self):
        plan = dict(PLAN, readiness="blocked", gaps=["missing implementation"])
        result, record = self.run_build(plan=plan)
        self.assertEqual(result["status"], "blocked")
        self.assertNotIn("package", record)

    def test_plan_only_is_not_a_ready_package(self):
        result, record = self.run_build(plan_only=True)
        self.assertEqual(result["status"], "draft")
        self.assertNotIn("package", record)

    def test_no_execution_is_draft(self):
        self.options["checks"] = []
        write_json(self.config, self.options)
        result, record = self.run_build()
        self.assertEqual(result["status"], "draft")
        self.assertEqual(record["checks"][-1]["status"], "not_run")

    def test_check_failure_does_not_weaken_configured_oracle(self):
        self.options["checks"][0]["stdout_contains"] = ["impossible-value"]
        self.options["limits"]["repair_rounds"] = 2
        write_json(self.config, self.options)
        result, record = self.run_build(ARTIFACT, ARTIFACT)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(record["stopped_reason"], "Repeated unchanged failure")
        self.assertEqual(record["test_definitions"]["configured"][0]["stdout_contains"], ["impossible-value"])
        self.assertTrue(Path(record["temporary_workspace"]).exists())

    def test_invalid_coverage_can_be_repaired_without_fixed_headings(self):
        wrong = copy.deepcopy(ARTIFACT)
        wrong["coverage"]["io"] = "invented quotation"
        result, record = self.run_build(wrong, ARTIFACT)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(record["repair_rounds"], 1)

    def test_model_budget_failure_is_explicit(self):
        self.options["limits"]["model_calls"] = 1
        write_json(self.config, self.options)
        result, record = self.run_build()
        self.assertEqual(result["status"], "failed")
        self.assertIn("budget", record["error"])

    def test_install_checks_manifest_and_refuses_existing_destination(self):
        result, _ = self.run_build()
        target = self.root / "installed"
        installed = install(result["output"], target)
        self.assertTrue(Path(installed["installed"]).is_dir())
        with self.assertRaises(ValueError):
            install(result["output"], target)
        (Path(result["output"]) / "add-numbers/extra.txt").write_text("unvalidated", encoding="utf-8")
        with self.assertRaises(ValueError):
            install(result["output"], self.root / "other")

    def test_draft_cannot_install(self):
        self.options["checks"] = []
        write_json(self.config, self.options)
        result, _ = self.run_build()
        with self.assertRaises(ValueError):
            install(result["output"], self.root / "installed")

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

    def test_absent_coverage_cannot_bypass_minimum_checks(self):
        bad = copy.deepcopy(ARTIFACT)
        del bad["coverage"]
        result, record = self.run_build(bad, bad)
        self.assertEqual(result["status"], "failed")
        self.assertIn("minimum", record["error"])

    def test_package_mutation_during_check_is_detected(self):
        self.options["limits"]["repair_rounds"] = 0
        self.options["checks"] = [{"name": "mutate", "argv": ["{python}", "-c",
            'from pathlib import Path; import sys; Path(sys.argv[1],"SKILL.md").write_text("changed"); print("done")',
            "{package}"], "stdout_contains": ["done"]}]
        write_json(self.config, self.options)
        result, record = self.run_build()
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any(r["name"] == "artifact_immutability" for r in record["checks"]))

    def test_source_mutation_during_check_is_detected(self):
        self.options["checks"] = [{"name": "mutate", "argv": ["{python}", "-c",
            'from pathlib import Path; import sys; Path(sys.argv[1],"adder.py").write_text("changed"); print("done")',
            "{source:tool}"], "stdout_contains": ["done"]}]
        write_json(self.config, self.options)
        result, record = self.run_build()
        self.assertEqual(result["status"], "failed")
        self.assertIn("Sources changed", record["error"])

    def test_blocked_plan_without_evidence_is_reported_as_blocked(self):
        plan = dict(PLAN, readiness="blocked", evidence=[], files=[], gaps=["missing interface"])
        result, _ = self.run_build(plan=plan)
        self.assertEqual(result["status"], "blocked")

    def test_explicit_document_gets_a_real_initial_view(self):
        self.options["sources"][0]["path"] = "source/adder.py"
        write_json(self.config, self.options)
        backend = ReplayBackend([response(PLAN), response(ARTIFACT)])
        result = build(self.config, self.state, backend=backend, plan_only=True)
        record = read_json(Path(result["output"]) / "build.json")
        self.assertEqual(record["evidence"][0]["id"], "e1")
        self.assertIn("def add", record["evidence"][0]["excerpt"])

    def test_expected_failure_and_json_assertions(self):
        config = load_config(self.config)
        sources = Sources(config, self.root / "cache")
        test = {"name": "rejected", "argv": ["{python}", "-c", 'import json,sys; print(json.dumps({"ok":False})); sys.exit(2)'],
                "expected_exit": 2, "json_equals": {"ok": False}}
        report = execute(test, self.root, sources, self.root / "check", 10, [])
        self.assertEqual(report["status"], "pass")

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

    def test_extension_without_negative_execution_is_draft(self):
        self.options["intent"] = "extension"
        write_json(self.config, self.options)
        plan = dict(PLAN, intent="extension", added_behavior="Additional numerical rule")
        backend = self.backend(ARTIFACT, {"status": "pass", "resolution": "none", "findings": []}, plan=plan)
        result = build(self.config, self.state, backend=backend)
        record = read_json(Path(result["output"]) / "build.json")
        self.assertEqual(result["status"], "draft")
        self.assertEqual(record["checks"][-1]["name"], "extension_positive_negative")

    def test_missing_review_evidence_stops_as_draft_without_rewriting(self):
        self.options["intent"] = "extension"
        write_json(self.config, self.options)
        plan = dict(PLAN, intent="extension", added_behavior="Additional numerical rule")
        backend = self.backend(ARTIFACT, {"status": "fail", "resolution": "supply_evidence",
                                       "findings": ["Missing upstream acquisition location"]}, plan=plan)
        result = build(self.config, self.state, backend=backend)
        record = read_json(Path(result["output"]) / "build.json")
        self.assertEqual(result["status"], "draft")
        self.assertEqual(record["repair_rounds"], 0)
        review = next(r for r in record["checks"] if r["name"] == "content_review")
        self.assertEqual(review["status"], "not_run")


if __name__ == "__main__":
    unittest.main()
