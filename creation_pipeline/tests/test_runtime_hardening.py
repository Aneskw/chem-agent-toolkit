"""Targeted state, repair-boundary, real-usage and process-supervision checks."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_runtime_model as baseline
import runtime_model_lifecycle as lifecycle
import runtime_package as runner
from runtime_common import read, write
from runtime_docker import validate


class HardeningTests(unittest.TestCase):
    setUp = baseline.ModelRuntimeTests.setUp
    generate = baseline.ModelRuntimeTests.generate
    verified = baseline.ModelRuntimeTests.verified
    fake_case = baseline.ModelRuntimeTests.fake_case
    fake_process = baseline.ModelRuntimeTests.fake_process

    def test_success_then_every_rebuild_fails_has_no_current_passes(self):
        first = self.verified()
        def fail_build(argv, timeout=60, cwd=None):
            return dict(exit_code=1, stdout="", stderr="bad dependency") if "build" in argv else self.fake_process(argv, timeout, cwd)
        with patch("runtime_package.process", side_effect=fail_build), \
             patch("model_call.call", return_value=({"action": "plan", "plan": self.plan}, {})):
            report = validate(self.skill)
        self.assertEqual(report["status"], "budget_exhausted")
        self.assertEqual(set(report["validation"].values()), {"not_verified"})
        self.assertEqual(report["tools"][0]["cases"], [])
        self.assertEqual(report["tools"][0]["examples"], [])
        historical = read(self.skill / report["previous_execution"]["path"])
        self.assertEqual(historical["validation"], first["validation"])
        self.assertTrue(historical["tools"][0]["cases"])
        self.assertNotIn("examples passed", (self.skill / "SKILL.md").read_text())
        self.assertIn("not_accepted", (self.skill / "DOCKER.md").read_text())
        self.failed_report = report
        self.check_local_publication(report)

    def check_local_publication(self, report):
        import publish_run
        import shutil
        pipeline = self.root / "pipeline"
        target = pipeline / "runs/retry/drafts-v03" / self.skill.name
        shutil.copytree(self.skill, target)
        write(pipeline / "results/retry.json", {"status": "method_drafts_created", "runtime_mode": "docker"})
        out = self.root / "published"
        out.mkdir()
        with patch.object(publish_run, "HERE", pipeline), patch.object(publish_run, "ROOT", out), \
             patch("sys.argv", ["publish_run.py", "--success-policy", "archive", "--run-id", "retry"]):
            self.assertEqual(publish_run.main(), 0)
        manifest = read(out / "skills/generated/retry/PUBLISHING.json")
        self.assertFalse(manifest["execution_validated"])
        self.assertEqual(manifest["layered_validation"][self.skill.name], report["validation"])

    def test_success_then_engine_blocked_does_not_reuse_cases(self):
        self.verified()
        with patch("runtime_package.process", return_value={"exit_code": 1, "stdout": "", "stderr": "engine unavailable"}), \
             patch("model_call.call", side_effect=AssertionError("No dependency repair")):
            report = validate(self.skill)
        self.assertEqual(report["status"], "blocked_resources")
        self.assertEqual(report["tools"][0]["cases"], [])
        self.assertNotIn("passed", report["validation"].values())

    def test_success_then_source_drift_invalidates_all_current_results(self):
        self.verified()
        (self.source / "cli.py").write_text("print(999)")
        with patch("model_call.call", side_effect=AssertionError("Must not replan changed inputs")):
            report = validate(self.skill)
        self.assertEqual(report["status"], "needs_review")
        self.assertEqual(report["tools"][0]["cases"], [])
        self.assertNotEqual(report["tools"][0]["status"], "execution_passed")
        self.assertTrue((self.skill / report["invalidated_observations"]["path"]).exists())

    def test_entrypoint_mismatch_is_repairable(self):
        self.generate()
        inspected = [0]
        def process(argv, timeout=60, cwd=None):
            result = self.fake_process(argv, timeout, cwd)
            if argv[:3] == ["docker", "image", "inspect"] and "--format" not in argv:
                inspected[0] += 1
                if inspected[0] == 1:
                    info = json.loads(result["stdout"])
                    info[0]["Config"]["Entrypoint"] = ["wrong"]
                    result["stdout"] = json.dumps(info)
            return result
        with patch("runtime_package.process", side_effect=process), patch("runtime_package.run_case", side_effect=self.fake_case), \
             patch("runtime_model_lifecycle.verify_examples", return_value=[]), \
             patch("model_call.call", return_value=({"action": "plan", "plan": self.plan}, {})) as model:
            report = validate(self.skill)
        self.assertEqual(report["status"], "execution_passed")
        self.assertIn("entrypoint mismatch", model.call_args.args[0])

    def test_source_integrity_failure_never_replans(self):
        self.generate()
        def process(argv, timeout=60, cwd=None):
            result = self.fake_process(argv, timeout, cwd)
            if any("sha256sum" in arg for arg in argv):
                result["stdout"] = "0" * 64 + "  cli.py\n"
            return result
        with patch("runtime_package.process", side_effect=process), \
             patch("model_call.call", side_effect=AssertionError("Must not repair integrity failures")):
            report = validate(self.skill)
        self.assertEqual(report["status"], "needs_review")
        self.assertTrue(report["requires_prepare"])
        self.assertEqual(report["tools"][0]["failure_kind"], "integrity")

    def test_engine_lost_during_inspect_is_blocked(self):
        self.generate()
        def process(argv, timeout=60, cwd=None):
            if argv[:3] == ["docker", "image", "inspect"]:
                return dict(exit_code=1, stdout="", stderr="Cannot connect to the Docker daemon")
            return self.fake_process(argv, timeout, cwd)
        with patch("runtime_package.process", side_effect=process), \
             patch("model_call.call", side_effect=AssertionError("Must not guess dependencies")):
            report = validate(self.skill)
        self.assertEqual(report["status"], "blocked_resources")
        self.assertEqual(report["tools"][0]["failure_kind"], "infrastructure")

    def test_unclassified_value_error_is_not_sent_to_model(self):
        self.generate()
        def process(argv, timeout=60, cwd=None):
            if "build" in argv:
                raise ValueError("unexpected internal format")
            return self.fake_process(argv, timeout, cwd)
        with patch("runtime_package.process", side_effect=process), \
             patch("model_call.call", side_effect=AssertionError("Unknown errors need inspection")):
            report = validate(self.skill)
        self.assertEqual(report["tools"][0]["failure_kind"], "unclassified")
        self.assertNotEqual(report["status"], "execution_passed")

    def test_usage_command_is_concrete_and_shares_assertions(self):
        self.generate()
        example = next(e for e in read(self.skill / "runtime/examples.json")["examples"] if e.get("kind") == "usage")
        self.assertEqual(example["argv"][-2:], ["--", "3"])
        self.assertNotIn("YOUR_TOOL_ARGUMENTS", (self.skill / "DOCKER.md").read_text())
        with patch("runtime_package.process", return_value={"exit_code": 0, "stdout": "6", "stderr": ""}):
            observations = lifecycle.verify_examples(self.skill, "double", __import__("time").monotonic() + 30)
        self.assertEqual(observations[-1]["status"], "passed")
        with patch("runtime_package.process", return_value={"exit_code": 0, "stdout": "999", "stderr": ""}):
            observations = lifecycle.verify_examples(self.skill, "double", __import__("time").monotonic() + 30)
        self.assertEqual(observations[-1]["status"], "failed")

    def test_planning_time_notes_are_labeled(self):
        self.plan["unresolved"] = ["Not executed when planned"]
        self.verified()
        text = (self.skill / "DOCKER.md").read_text()
        self.assertIn("Planning-time unresolved", text)
        self.assertIn("current results", text)

    def test_owned_container_labels_are_propagated(self):
        with patch.dict(os.environ, {"SKILLNET_EXECUTION_SCOPE": "test-owned"}):
            command = runner.invocation({"behavior": {"file_io": False}}, "image", [], "name")
        self.assertIn("skillnet.scope=test-owned", command)

    def test_preparation_budget_failure_cannot_become_prepared(self):
        from runtime_docker import prepare
        with patch("model_call.call", side_effect=subprocess.TimeoutExpired(["model"], 1)):
            self.assertEqual(prepare(self.skill, "job", self.bindings)["status"], "budget_exhausted")
        with patch("runtime_package.process", side_effect=AssertionError("No package was generated")):
            report = validate(self.skill)
        self.assertEqual(report["status"], "budget_exhausted")
        self.assertEqual(report["tools"][0]["status"], "budget_exhausted")

    def test_stdout_capture_is_explicit_and_preserves_file_checks(self):
        tool = {"behavior": {"file_io": True}}
        case = {"name": "stdout-tool", "args": ["/input/a.txt"], "input_files": {"a.txt": "abc"},
                "output_file": "sum.txt", "stdout_equals": "golden", "origin": "model_proposed", "basis": "reference"}
        with patch("runtime_package.run", return_value={"exit_code": 0, "stdout": "golden\n", "stderr": ""}):
            old = runner.run_case(self.skill, tool, "image", case)
            captured = runner.run_case(self.skill, tool, "image", dict(case, capture_stdout=True))
        self.assertEqual(old["status"], "failed", "Missing tool-created files must remain a failure")
        self.assertEqual(captured["status"], "passed")
        self.assertEqual(captured["persisted_output"], "golden\n")
        with patch("runtime_package.run", return_value={"exit_code": 0, "stdout": "wrong", "stderr": ""}):
            self.assertEqual(runner.run_case(self.skill, tool, "image", dict(case, capture_stdout=True))["status"], "failed")

    @unittest.skipUnless(os.name == "nt", "Windows process-tree regression; POSIX uses a new process group")
    def test_supervisor_terminates_python_descendant(self):
        import ctypes
        import time
        pid_file = self.root / "child.pid"
        code = "import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);Path(sys.argv[1]).write_text(str(p.pid));time.sleep(60)"
        with patch("runtime_package.cleanup_scope", return_value=[]):
            with self.assertRaises(subprocess.TimeoutExpired):
                runner.process([sys.executable, "-c", code, str(pid_file)], timeout=2, supervise=True)
        self.assertTrue(pid_file.exists())
        child_pid = int(pid_file.read_text())
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, child_pid)
        if handle:
            try:
                exit_code = ctypes.c_ulong()
                kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                self.assertNotEqual(exit_code.value, 259, "Descendant still running")
            finally:
                kernel.CloseHandle(handle)

    def configure_file_fixture(self):
        """The synthetic file tool now declares the same grounded v2 input contract."""
        description = 'File mode reads integer n.txt using --input and writes twice its value using --output; invalid integers raise ValueError.'
        with (self.source / 'README.md').open('a', encoding='utf-8') as handle:
            handle.write('\n' + description)
        (self.source / 'cli.py').write_text(
            "import sys\nfrom pathlib import Path\n"
            "args=sys.argv[1:]\n"
            "value=Path(args[args.index('--input')+1]).read_text() if '--input' in args else args[0]\n"
            "result=str(int(value)*2)\n"
            "if '--output' in args: Path(args[args.index('--output')+1]).write_text(result)\n"
            "print(result)\n", encoding='utf-8')
        policy = json.loads(self.plan['acceptance_json'])
        policy['checks'] = [dict(id='integer', channel='input_files', key='n.txt', pattern=r'-?[0-9]+\n?',
                                 source_path='README.md', source_quote=description)]
        policy.update(scope='file integer doubling', constraint='integer file')
        self.plan['acceptance_json'] = json.dumps(policy)
        negative = json.loads(self.plan['tests'][-1]['case_json'])
        negative.update(args=['--input', '/input/n.txt'], input_files={'n.txt': 'invalid'})
        self.plan['tests'][-1]['case_json'] = json.dumps(negative)
        return json.loads(self.plan['tests'][1]['case_json'])['acceptance']

    def test_file_usage_preparation_and_persistence_contract(self):
        contract = self.configure_file_fixture()
        self.plan["file_io"] = True
        test = copy.deepcopy(self.plan["tests"][1])
        test.update(name="persist", case_json=json.dumps({"args": ["--input", "/input/n.txt", "--output", "/output/result.txt"],
                    "input_files": {"n.txt": "3\n"}, "output_file": "result.txt", "stdout_equals": "6", "acceptance": contract}))
        self.plan["tests"].append(test)
        self.generate()
        example = next(e for e in read(self.skill / "runtime/examples.json")["examples"] if e.get("kind") == "usage")
        self.assertIn("--input-dir", example["argv"])
        self.assertIn("--output-dir", example["argv"])
        result = subprocess.run([sys.executable, str(self.skill / "runtime/runner.py"), *example["preparation_argv"][2:]],
                                capture_output=True, cwd=self.skill)
        self.assertEqual(result.returncode, 0, result.stderr)
        input_path = self.skill / example["input_dir"] / "n.txt"
        self.assertEqual(input_path.read_text(), "3\n")
        input_path.write_text("user data")
        result = subprocess.run([sys.executable, str(self.skill / "runtime/runner.py"), *example["preparation_argv"][2:]],
                                capture_output=True, cwd=self.skill)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(input_path.read_text(), "user data")

    def test_missing_documented_output_is_a_failed_invocation(self):
        contract = self.configure_file_fixture()
        self.plan["file_io"] = True
        test = copy.deepcopy(self.plan["tests"][1])
        test.update(name="persist", case_json=json.dumps({"args": ["--input", "/input/n.txt", "--output", "/output/result.txt"],
                    "input_files": {"n.txt": "3\n"}, "output_file": "result.txt", "stdout_equals": "6", "acceptance": contract}))
        self.plan["tests"].append(test)
        self.generate()
        with patch("runtime_package.process", return_value={"exit_code": 0, "stdout": "6", "stderr": ""}):
            observations = lifecycle.verify_examples(self.skill, "double", __import__("time").monotonic() + 30)
        self.assertEqual(observations[-1]["status"], "failed")
        self.assertIn("did not persist", observations[-1]["error"])
