"""Mechanism tests use a fake planner/Docker; they are not generalization evidence."""
import copy
import json
import subprocess
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import runtime_model as planner
import runtime_model_lifecycle as lifecycle
import runtime_package as runner
from runtime_docker import read, write, prepare, validate, evidence
from render_drafts_v03 import render
from test_creation_contract import candidate, bundle


FIXTURE_DOC = 'Python CLI doubling n: print 2*n. Integer argument required; non-integer input raises ValueError on stderr and exits 1.'


def fixture_plan():
    def test(name, layer, args, **assertions):
        return dict(name=name, layer=layer, kind="derived", source_paths=["README.md"],
                    basis="README defines doubling; 2*3=6 independently", oracle_status="supported",
                    tolerance=0, limitations=["Tiny deterministic example only"],
                    case_json=json.dumps(dict(args=args, **assertions)))
    plan = dict(entrypoint=["python", "/opt/skill/cli.py"], script="cli.py", base_image="python:3.11-slim",
                platform="linux/amd64", language="python", language_version="3.11", source_files=["cli.py"],
                dependencies=[], steps=[], environment=[], resources=[], file_io=False, output_contract="decimal integer",
                runtime_network=False, network_reason="", choices=[dict(choice="Python 3.11", evidence="cli.py uses Python", certainty="inferred")],
                unresolved=[], unverified_behavior=["Only doubling is checked"], generated_files=[],
                tests=[test("environment", "environment", ["-c", "print('available')"], entrypoint="python", stdout_equals="available"),
                       test("interface", "interface", ["3"], stdout_equals="6"),
                       test("double", "behavior", ["3"], stdout_equals="6")])
    evidence = dict(source_path='README.md', source_quote=FIXTURE_DOC)
    plan['acceptance_json'] = json.dumps(dict(evidence, invalid_input='required', scope='integer doubling',
        purposes=['operation'], constraint='integer input', checks=[dict(evidence, id='integer', channel='args', key=0, pattern=r'-?[0-9]+')]))
    for entry in plan['tests'][1:]:
        case = json.loads(entry['case_json'])
        case['acceptance'] = dict(evidence, purpose='operation', assertion=dict(evidence, role='result', kind='stdout_equals', value='6'))
        entry['case_json'] = json.dumps(case)
    rejection = test('invalid-integer', 'interface', ['invalid'], expected_exit=1)
    case = json.loads(rejection['case_json'])
    case['acceptance'] = dict(evidence, purpose='input_rejection', violates='integer', invalid_input_reason='invalid is not an integer',
        assertion=dict(evidence, role='rejection', kind='stderr_contains', value='ValueError'))
    rejection['case_json'] = json.dumps(case)
    plan['tests'].append(rejection)
    return plan


class ModelRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "cli.py").write_text("import sys\nprint(int(sys.argv[1])*2)\n", encoding="utf-8")
        (self.source / "README.md").write_text(FIXTURE_DOC + '\n', encoding="utf-8")
        self.skill = self.root / "example-procedure"
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_text(render(candidate(), bundle(), {"state": "draft_unexecuted"}), encoding="utf-8")
        self.bindings = self.root / "bindings.json"
        self.settings = dict(schema_version=3, planner={"max_attempts": 2},
                             tools={"double": {"root": str(self.source)}},
                             bindings=[dict(job_id="job", candidate=self.skill.name, requirement="required", tools=["double"])])
        write(self.bindings, self.settings)
        self.plan = fixture_plan()

    def generate(self, plan=None):
        with patch("model_call.call", return_value=({"action": "plan", "plan": plan or self.plan, "reason": "test", "requested_files": []}, {"model": "fake"})):
            return prepare(self.skill, "job", self.bindings)

    def fake_process(self, argv, timeout=60, cwd=None):
        output = ""
        if len(argv)>2 and argv[1] == 'runtime/runner.py' and argv[2] == 'build':
            output = json.dumps({'image_id': 'sha256:' + 'a'*64})
        if argv[:2] == ["docker", "run"] and any("sha256sum" in a for a in argv):
            import hashlib
            output = hashlib.sha256((self.source / "cli.py").read_bytes()).hexdigest() + "  cli.py\n"
        if argv[:3] == ["docker", "image", "inspect"]:
            output = "sha256:" + 'a'*64 if "--format" in argv else json.dumps([{"Id": "sha256:" + 'a'*64, "Os": "linux", "Architecture": "amd64", "Config": {"Entrypoint": self.plan["entrypoint"]}}])
        return dict(command=argv, exit_code=0, stdout=output, stderr="")

    def fake_case(self, root, tool, image, case, **kwargs):
        return dict(case, status="passed", stdout="6", stderr="", exit_code=0)

    def verified(self):
        self.generate()
        with patch("runtime_package.process", side_effect=self.fake_process), \
             patch("runtime_package.run_case", side_effect=self.fake_case), \
             patch("runtime_model_lifecycle.verify_examples", return_value=[{"status": "passed"}]):
            return validate(self.skill)

    def test_no_profile_or_hash_support_gate(self):
        self.assertEqual(self.generate()["status"], "prepared")
        (self.source / "cli.py").write_text("# another version\nprint(6)\n")
        self.assertEqual(self.generate()["status"], "prepared")
        self.assertTrue(list((self.skill / "reports").glob("runtime-archive-*")))

    def test_channels_pip_system_conda_compile_are_generic(self):
        for command, generated in [("python -m pip install rich", []), ("apt-get update && apt-get install -y jq", []),
                                   ("conda env update -f env.yml", [{"path": "env.yml", "content": "dependencies: [python]"}]),
                                   ("cc cli.c -o /usr/local/bin/tool", [])]:
            p = copy.deepcopy(self.plan)
            p["steps"] = [{"command": command, "purpose": "install", "evidence": "fixture mechanism"}]
            p["generated_files"] = generated
            result = self.generate(p)
            self.assertEqual(result["status"], "prepared")
            self.assertIn(command, (self.skill / "runtime/tools/double/context/Dockerfile").read_text())

    def test_bad_schema_is_diagnosed_and_retried(self):
        bad = copy.deepcopy(self.plan)
        bad.pop("base_image")
        with patch("model_call.call", side_effect=[({"action": "plan", "plan": bad}, {}), ({"action": "plan", "plan": self.plan}, {})]):
            self.assertEqual(prepare(self.skill, "job", self.bindings)["status"], "prepared")
        self.assertTrue((self.skill / "runtime/tools/double/attempts/0001/rejection.json").exists())

    def test_invalid_plan_budget_is_bounded(self):
        bad = copy.deepcopy(self.plan)
        bad["platform"] = "linux/arm64"
        with patch("model_call.call", return_value=({"action": "plan", "plan": bad}, {})) as call:
            self.assertEqual(prepare(self.skill, "job", self.bindings)["status"], "needs_review")
        self.assertEqual(call.call_count, 2)

    def test_material_requests_are_recorded(self):
        opts = planner.options({"context_chars": 4000})
        (self.source / "large.txt").write_text("x" * 3000)
        audit = self.root / "audit"
        with patch("model_call.call", side_effect=[({"action": "read", "requested_files": ["large.txt"]}, {}),
                                                  ({"action": "plan", "plan": self.plan}, {})]):
            planner.plan(self.source, {}, audit, opts, time.monotonic() + 30)
        self.assertIn("large.txt", read(audit / "materials.json")["read"])

    def test_path_escape_and_source_overwrite_rejected(self):
        for name in ("../oops", "C:/oops", "cli.py", "scripts/hack.py"):
            p = copy.deepcopy(self.plan)
            p["generated_files"] = [{"path": name, "content": "oops"}]
            self.assertEqual(self.generate(p)["status"], "needs_review")
        self.assertIn("sys.argv", (self.source / "cli.py").read_text())

    def test_build_directive_injection_rejected(self):
        p = copy.deepcopy(self.plan)
        p["steps"] = [{"command": "true\nUSER root", "purpose": "bad", "evidence": "none"}]
        self.assertEqual(self.generate(p)["status"], "needs_review")

    def test_missing_and_unsupported_resources_are_blockers(self):
        for kind in ("gpu", "private_dependency", "credential", "weight", "service", "data"):
            p = copy.deepcopy(self.plan)
            p["resources"] = [{"kind": kind, "description": "missing", "available": False, "evidence": "README"}]
            self.assertEqual(self.generate(p)["status"], "blocked_resources")

    def test_original_expectations_are_preserved(self):
        original = {"script": "cli.py", "name": "old", "args": ["3"], "stdout_equals": "6"}
        write(self.source / "execution/fixtures.json", {"cases": [original]})
        self.assertEqual(self.generate()["status"], "prepared")
        case = read(self.skill / "runtime/tools/double/context/.skillnet/fixtures.json")["cases"][0]
        self.assertEqual(case["stdout_equals"], "6")
        self.assertEqual(read(self.source / "execution/fixtures.json")["cases"][0], original)

    def test_test_weakening_is_rejected(self):
        index = planner.inventory(self.source, planner.options({}))
        cases, _, _ = planner.validate_plan(self.plan, index, self.source)
        weakened = copy.deepcopy(self.plan)
        weakened["tests"][2]["case_json"] = json.dumps({"args": ["3"]})
        with self.assertRaises(planner.PlanningError):
            planner.validate_plan(weakened, index, self.source, cases)

    def test_original_regression_baseline_is_not_promoted(self):
        write(self.source / "execution/fixtures.json", {"cases": [{"script": "cli.py", "args": ["3"],
              "stdout_equals": "6", "kind": "regression", "oracle_status": "regression"}]})
        self.assertEqual(self.generate()["status"], "prepared")
        case = read(self.skill / "runtime/tools/double/context/.skillnet/fixtures.json")["cases"][0]
        self.assertEqual(case["oracle_status"], "regression")
        self.assertEqual(case["args"], ["/opt/skill/cli.py", "3"])

    def test_candidate_oracle_is_not_behavior_acceptance(self):
        cases = [dict(layer="environment", oracle_status="supported", status="passed"),
                 dict(layer="behavior", oracle_status="candidate", status="passed")]
        self.assertEqual(lifecycle.states(cases)["behavior"], "not_verified")

    def test_guessed_oracle_cannot_be_promoted(self):
        self.plan["tests"][2]["kind"] = "candidate"
        self.assertEqual(self.generate()["status"], "needs_review")

    def test_layered_success_and_stale_evidence(self):
        report = self.verified()
        self.assertEqual(report["status"], "execution_passed")
        self.assertEqual(report["validation"], {k: "passed" for k in lifecycle.LAYERS})
        with patch("runtime_package.process", side_effect=self.fake_process):
            self.assertEqual(evidence(self.skill)["status"], "execution_passed")
        (self.skill / "DOCKER.md").write_text("changed")
        self.assertEqual(evidence(self.skill)["status"], "needs_review")
        self.assertEqual(validate(self.skill)["status"], "needs_review")
        self.assertNotIn("examples passed", (self.skill / "SKILL.md").read_text())

    def test_added_source_file_invalidates_evidence(self):
        self.verified()
        (self.source / "environment.yml").write_text("dependencies: []")
        self.assertEqual(evidence(self.skill)["status"], "needs_review")

    def test_missing_retained_image_invalidates_evidence(self):
        self.verified()
        with patch("runtime_package.process", return_value={"exit_code": 1, "stdout": "", "stderr": "missing"}):
            self.assertEqual(evidence(self.skill)["status"], "needs_review")

    def test_build_failure_replans_using_logs(self):
        self.generate()
        count = [0]
        def process(argv, timeout=60, cwd=None):
            if "build" in argv:
                count[0] += 1
                if count[0] == 1:
                    return dict(command=argv, exit_code=1, stdout="", stderr="package not found: wrong dependency")
            return self.fake_process(argv, timeout, cwd)
        with patch("runtime_package.process", side_effect=process), patch("runtime_package.run_case", side_effect=self.fake_case), \
             patch("runtime_model_lifecycle.verify_examples", return_value=[]), \
             patch("model_call.call", return_value=({"action": "plan", "plan": self.plan, "reason": "fix dependency"}, {})) as call:
            report = validate(self.skill)
        self.assertEqual(report["status"], "execution_passed")
        self.assertIn("wrong dependency", call.call_args.args[0])
        self.assertEqual(count[0], 2)

    def test_import_failure_is_environment_failure_and_repaired(self):
        self.generate()
        count = [0]
        def case(root, tool, image, c, **kwargs):
            result = self.fake_case(root, tool, image, c)
            if c["layer"] == "environment":
                count[0] += 1
                if count[0] == 1:
                    result.update(status="failed", stderr="ModuleNotFoundError: dependency")
            return result
        with patch("runtime_package.process", side_effect=self.fake_process), patch("runtime_package.run_case", side_effect=case), \
             patch("runtime_model_lifecycle.verify_examples", return_value=[]), \
             patch("model_call.call", return_value=({"action": "plan", "plan": self.plan}, {})):
            result = validate(self.skill)
        self.assertEqual(result["validation"]["environment"], "passed")
        self.assertEqual(count[0], 2)

    def test_attempt_exhaustion_preserves_last_failure(self):
        self.generate()
        def process(argv, timeout=60, cwd=None):
            if "build" in argv:
                return dict(exit_code=1, stdout="", stderr="bad dependency")
            return self.fake_process(argv, timeout, cwd)
        with patch("runtime_package.process", side_effect=process), \
             patch("model_call.call", return_value=({"action": "plan", "plan": self.plan}, {})):
            result = validate(self.skill)
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertEqual(result["tools"][0]["last_failure"], "build_failed")

    def test_unavailable_docker_does_not_trigger_model_repairs(self):
        self.generate()
        with patch("runtime_package.process", return_value=dict(exit_code=1, stdout="", stderr="no daemon")), \
             patch("model_call.call", side_effect=AssertionError("Do not replan for an unavailable engine")):
            self.assertEqual(validate(self.skill)["status"], "blocked_resources")

    def test_independent_retry_appends_audit_and_preserves_tests(self):
        self.verified()
        attempts = self.skill / "runtime/tools/double/attempts"
        first = (attempts / "0001/build.json").read_bytes()
        with patch("runtime_package.process", side_effect=self.fake_process), \
             patch("runtime_package.run_case", side_effect=self.fake_case), \
             patch("runtime_model_lifecycle.verify_examples", return_value=[]):
            self.assertEqual(validate(self.skill)["status"], "execution_passed")
        self.assertEqual((attempts / "0001/build.json").read_bytes(), first)
        self.assertTrue((attempts / "0002/build.json").exists())

    def test_total_time_budget(self):
        with self.assertRaises(planner.BudgetExceeded):
            planner.plan(self.source, {}, self.root / "audit", planner.options({}), time.monotonic() - 1)

    def test_metamorphic_relation_and_tolerance(self):
        case = dict(name="scale", origin="model", basis="doubling is linear", args=[],
                    relation={"type": "numeric_scale", "factor": 2, "runs": [{"args": ["3"]}, {"args": ["6"]}]}, tolerance=0.01)
        with patch("runtime_package.run", side_effect=[dict(exit_code=0, stdout="6", stderr=""), dict(exit_code=0, stdout="12.001", stderr="")]):
            self.assertEqual(runner.run_case(self.skill, {}, "image", case)["status"], "passed")

    def test_default_network_and_resources(self):
        tool = dict(behavior={"file_io": False}, limits={"memory": "1g", "cpus": "2", "pids": 100})
        command = runner.invocation(tool, "image", [], "container")
        self.assertEqual(command[command.index("--network") + 1], "none")
        self.assertIn("--read-only", command)
        self.assertIn("10001:10001", command)

    def test_stage_uses_model_generation_and_keeps_extraction_separate(self):
        import runtime_docker
        with patch("model_call.call", return_value=({"action": "plan", "plan": self.plan}, {})), \
             patch("runtime_package.process", side_effect=self.fake_process), \
             patch("runtime_package.run_case", side_effect=self.fake_case), \
             patch("runtime_model_lifecycle.verify_examples", return_value=[{"status": "passed"}]):
            result = runtime_docker.stage(self.root, "job", self.bindings)
        self.assertEqual(result["runtime_status"], "execution_passed")
        self.assertEqual(result["agent_effect_status"], "not_evaluated")

    def test_batch_passes_runtime_binding_to_real_creation_command(self):
        import batch_pipeline
        manifest = self.root / "manifest.json"
        write(manifest, {"jobs": [{"paper_id": "job", "sources": []}]})
        def run(argv, **kwargs):
            self.assertIn("--runtime-mode", argv)
            self.assertIn(str(self.bindings), argv)
            run_id = argv[argv.index("--run-id") + 1]
            write(self.root / "results" / (run_id + ".json"), {"status": "failed", "runtime_status": "blocked_resources"})
            import subprocess
            return subprocess.CompletedProcess(argv, 0, "", "")
        with patch.object(batch_pipeline, "HERE", self.root), patch.object(batch_pipeline.subprocess, "run", side_effect=run), \
             patch("sys.argv", ["batch_pipeline.py", "--manifest", str(manifest), "--runtime-mode", "docker", "--tool-bindings", str(self.bindings)]):
            batch_pipeline.main()

    def test_publish_v3_keeps_layers_and_removes_stale_claim(self):
        import publish_run
        self.verified()
        local = self.root / "pipeline"
        target = local / "runs/test/drafts-v03" / self.skill.name
        shutil = __import__("shutil")
        shutil.copytree(self.skill, target)
        write(local / "results/test.json", {"status": "method_drafts_created", "runtime_mode": "docker"})
        (target / "runtime/prepared.json").unlink()
        destination = self.root / "publication"
        destination.mkdir()
        with patch.object(publish_run, "HERE", local), patch.object(publish_run, "ROOT", destination), \
             patch("sys.argv", ["publish_run.py", "--success-policy", "archive", "--run-id", "test"]):
            self.assertEqual(publish_run.main(), 0)
        packaged = destination / "skills/generated/test" / self.skill.name
        self.assertNotIn("examples passed", (packaged / "SKILL.md").read_text())
        self.assertIn("NOT been accepted", (packaged / "SKILL.md").read_text())
        self.assertFalse(read(packaged.parent / "PUBLISHING.json")["execution_validated"])

    def test_source_modification_during_build_is_rejected(self):
        self.generate()
        def process(argv, timeout=60, cwd=None):
            if "build" in argv:
                (self.skill / "runtime/tools/double/context/cli.py").write_text("print(6)")
            return self.fake_process(argv, timeout, cwd)
        with patch("runtime_package.process", side_effect=process), patch("runtime_package.run_case", side_effect=self.fake_case), \
             patch("runtime_model_lifecycle.verify_examples", return_value=[]):
            self.assertEqual(validate(self.skill)["status"], "needs_review")

    def test_budget_options_reject_zero_and_invalid_resources(self):
        for option in ({"max_attempts": 0}, {"memory": "unlimited"}, {"cpus": "0"}, {"total_seconds": -1}):
            with self.assertRaises(planner.PlanningError):
                planner.options(option)

    def test_retired_bindings_are_rejected_without_touching_current_package(self):
        self.generate()
        before = (self.skill / "runtime/prepared.json").read_bytes()
        for version in (1, 2, None):
            self.settings["schema_version"] = version
            write(self.bindings, self.settings)
            with patch("model_call.call", side_effect=AssertionError("Retired bindings must not invoke the model")):
                with self.assertRaisesRegex(ValueError, "retired"):
                    prepare(self.skill, "job", self.bindings)
            self.assertEqual((self.skill / "runtime/prepared.json").read_bytes(), before)

    def test_retired_execution_evidence_is_rejected(self):
        for version in (1, 2):
            write(self.skill / "runtime/prepared.json", {"schema_version": version})
            write(self.skill / "runtime/execution.json", {"schema_version": version, "status": "execution_passed"})
            with patch("runtime_package.process", side_effect=AssertionError("No legacy execution")):
                self.assertEqual(evidence(self.skill)["status"], "needs_review")
                with self.assertRaisesRegex(ValueError, "retired"):
                    validate(self.skill)

    def test_timeout_still_removes_container(self):
        def process(argv, timeout=60, cwd=None):
            if argv[:2] == ["docker", "run"]:
                raise subprocess.TimeoutExpired(argv, timeout)
            return {"exit_code": 0, "stdout": "", "stderr": ""}
        with patch("runtime_package.process", side_effect=process) as called:
            with self.assertRaises(subprocess.TimeoutExpired):
                runner.run({"behavior": {"file_io": False}}, "image", [])
        self.assertTrue(any(call.args[0][:3] == ["docker", "rm", "--force"] for call in called.call_args_list))

    def test_all_required_tools_must_pass(self):
        self.settings["bindings"][0]["tools"].append("missing")
        write(self.bindings, self.settings)
        self.generate()
        with patch("runtime_package.process", side_effect=self.fake_process), \
             patch("runtime_package.run_case", side_effect=self.fake_case), \
             patch("runtime_model_lifecycle.verify_examples", return_value=[]):
            result = validate(self.skill)
        self.assertNotEqual(result["status"], "execution_passed")
        self.assertEqual(result["tools"][0]["status"], "execution_passed")

    def test_method_only_binding_needs_neither_model_nor_docker(self):
        self.settings["bindings"][0].update(requirement="not_required", tools=[])
        write(self.bindings, self.settings)
        with patch("model_call.call", side_effect=AssertionError("No model required")), \
             patch("runtime_package.process", side_effect=AssertionError("No Docker required")):
            self.assertEqual(prepare(self.skill, "job", self.bindings)["status"], "not_required")
            self.assertEqual(validate(self.skill)["status"], "not_required")

    def test_failed_candidate_does_not_stop_method_sibling(self):
        import runtime_docker
        sibling = self.root / "other-procedure"
        sibling.mkdir()
        item = candidate()
        item["name"] = sibling.name
        (sibling / "SKILL.md").write_text(render(item, bundle(), {"state": "draft_unexecuted"}), encoding="utf-8")
        self.settings["bindings"][0]["tools"] = ["missing"]
        self.settings["bindings"].append(dict(job_id="job", candidate=sibling.name, requirement="not_required", tools=[]))
        write(self.bindings, self.settings)
        result = runtime_docker.stage(self.root, "job", self.bindings)
        self.assertEqual(result["runtime_checks"][sibling.name], "not_required")
        self.assertNotEqual(result["runtime_checks"][self.skill.name], "execution_passed")

    def test_malformed_package_withdraws_previous_success(self):
        from validate_skill_format import validate as format_check
        self.verified()
        (self.skill / "runtime/package.json").write_text("{invalid")
        with patch("runtime_package.process", side_effect=AssertionError("No stale execution")):
            self.assertEqual(validate(self.skill)["status"], "needs_review")
        self.assertNotIn("examples passed", (self.skill / "SKILL.md").read_text())
        self.assertFalse(format_check(self.skill / "SKILL.md"))

    def test_documentation_preserves_citations_and_confidence(self):
        self.verified()
        text = (self.skill / "SKILL.md").read_text()
        self.assertIn("s1:L1-L1", text)
        self.assertIn("Low confidence", text)
        self.assertIn("behavior coverage is limited", text)

    def test_batch_summary_counts_actual_statuses(self):
        from batch_pipeline import execution_summary
        result = execution_summary([{"execution_checks": {"ok": "execution_passed", "bad": "build_failed"}}])
        self.assertEqual(result["candidate_status_counts"], {"execution_passed": 1, "build_failed": 1})

    def test_no_tests_cannot_pass(self):
        self.plan["tests"] = []
        result = self.generate()
        self.assertEqual(result["status"], "needs_review")
        self.assertIn("Environment and interface", result["tools"][0]["error"])

    def test_partial_behavior_status_remains_explicit(self):
        self.plan["tests"][2].update(kind="candidate", oracle_status="candidate")
        result = self.verified()
        self.assertEqual(result["status"], "execution_passed")
        self.assertEqual(result["validation"]["behavior"], "not_verified")


if __name__ == "__main__":
    unittest.main()
