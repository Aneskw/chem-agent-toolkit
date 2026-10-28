"""Native lifecycle tests run a fake CLI, never a remote model."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from creation_pipeline.agent.backend import NativeSession, audit_images
from creation_pipeline.resources.intake import Sources
from creation_pipeline.models import load_config, ModelCallError
from creation_pipeline.resources.workspace import prepare
from creation_pipeline.records import write_json, read_json
from creation_pipeline.generation.discovery import analyze


class NativeTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2] / ".pipeline/test-tmp"
        root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.tmp.name).resolve()
        (self.root / "source.py").write_text("def identity(x): return x\n", encoding="utf-8")
        write_json(self.root / "input.json", {"sources": [{"id": "code", "path": "source.py"}],
            "network": False, "limits": {"model_calls": 4, "model_timeout": 10}})
        self.config = load_config(self.root / "input.json")
        self.sources = Sources(self.config, self.root / "cache")
        self.work = self.root / "run"
        self.work.mkdir()
        self.fake = self.root / "fake.py"
        self.fake.write_text('''import sys,json
from pathlib import Path
Path(sys.argv[0]).with_name('argv.json').write_text(json.dumps(sys.argv))
prompt=sys.stdin.read()
print(json.dumps({"type":"thread.started","thread_id":"fake-session"}),flush=True)
print(json.dumps({"type":"item.completed","item":{"type":"reasoning","text":"must not be retained"}}),flush=True)
print(json.dumps({"type":"item.completed","item":{"type":"command_execution","command":"read source","status":"completed"}}),flush=True)
print(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":json.dumps({"value":"resume" if "resume" in sys.argv else "new"})}}),flush=True)
print(json.dumps({"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}),flush=True)
''', encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def session(self):
        return NativeSession(self.config, self.sources, self.config["limits"].copy(), self.work)

    def test_native_turn_resume_and_durable_receipts(self):
        session = self.session()
        with patch("creation_pipeline.agent.backend.codex_command", return_value=[sys.executable, str(self.fake)]):
            self.assertEqual(session.stage("test", {}, {}), {"value": "new"})
            self.assertEqual(session.stage("test", {}, {}), {"value": "resume"})
        self.assertEqual(session.receipts[0]["tool_events"], 1)
        self.assertNotIn("must not be retained", (self.work / "agent-turns/001-discovery/events.jsonl").read_text())
        restored = self.session()
        self.assertEqual(len(restored.receipts), 2)
        resumed_prompt = (self.work / "agent-turns/002-discovery/prompt.txt").read_text(encoding="utf-8")
        self.assertIn("Continue from retained observations", resumed_prompt)
        self.assertEqual(restored.state["sessions"]["discovery"], "fake-session")
        argv = read_json(self.root / "argv.json")
        self.assertIn('sandbox_mode="workspace-write"', argv)
        self.assertNotIn("--ephemeral", argv)
        self.assertIn("resume", argv)

    def test_failure_retains_session_and_does_not_retry(self):
        self.fake.write_text('import json\nprint(json.dumps({"type":"thread.started","thread_id":"retained"}))\n', encoding="utf-8")
        session = self.session()
        with patch("creation_pipeline.agent.backend.codex_command", return_value=[sys.executable, str(self.fake)]):
            with self.assertRaises(ModelCallError):
                session.stage("test", {}, {})
        self.assertEqual(read_json(session.state_path)["sessions"]["discovery"], "retained")
        self.assertEqual(len(session.receipts), 1)

    def test_timeout_is_incomplete_work_and_preserves_checkpoint(self):
        from creation_pipeline.models import BudgetError
        self.fake.write_text('''import sys,json,time
sys.stdin.read()
print(json.dumps({"type":"thread.started","thread_id":"timeout-session"}),flush=True)
time.sleep(30)
''', encoding="utf-8")
        session = self.session()
        session.limits["model_timeout"] = 1
        with patch("creation_pipeline.agent.backend.codex_command", return_value=[sys.executable, str(self.fake)]):
            with self.assertRaises(BudgetError):
                session.stage("test", {}, {})
        saved = read_json(session.state_path)
        self.assertEqual(saved["sessions"]["discovery"], "timeout-session")
        self.assertIsNone(saved["receipts"][0]["usage"])

    def test_parser_failure_keeps_original(self):
        (self.root / "bad.pdf").write_bytes(b"%PDF-broken")
        write_json(self.root / "pdf.json", {"sources": [{"path": "bad.pdf"}]})
        sources = Sources(load_config(self.root / "pdf.json"), self.root / "cache-pdf")
        result = prepare(sources, self.work)
        index = read_json(result["resource_index"])
        self.assertTrue(Path(index["files"][0]["original"]).is_file())
        self.assertIn("render_command", index["files"][0])
        self.assertTrue(result["view_warnings"])

    def test_source_locators_are_explicit_not_reads(self):
        prepare(self.sources, self.work)
        self.assertEqual(self.sources.evidence[0]["kind"], "source_locator")
        self.assertEqual(self.sources.evidence[0]["end"], 0)
        prepare(self.sources, self.work)
        self.assertEqual(len(self.sources.evidence), 1)

    def test_direct_file_validation_preserves_bytes(self):
        from creation_pipeline.artifacts.delivery import validate_package
        target = self.work / "artifact"
        target.mkdir()
        raw = b"---\r\nname: sample\r\ndescription: sample\r\n---\r\nBody\r\n"
        (target / "SKILL.md").write_bytes(raw)
        validate_package(target, 1000)
        self.assertEqual((target / "SKILL.md").read_bytes(), raw)

    def test_missing_checkpoint_does_not_make_fake_resume(self):
        from creation_pipeline.pipeline import build
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            build(state_root=self.root / "state", resume_id="missing")

    def test_unfinished_discovery_not_zero_value(self):
        session = self.session()
        value = {"outcome": "incomplete", "summary": "Need more evidence", "candidates": []}
        with patch.object(session, "stage", return_value=value):
            with self.assertRaisesRegex(ValueError, "incomplete"):
                analyze(session, self.config)
        self.assertTrue((self.work / "discovery-partial.json").exists())

    def test_unknown_image_audit_is_not_success(self):
        self.assertEqual(audit_images(None)["status"], "unavailable")

    def test_image_delivery_audit_retains_no_image_payload(self):
        home = self.root / "codex-home"
        folder = home / "sessions/2026/10/24"
        folder.mkdir(parents=True)
        events = [
            {"type": "response_item", "payload": {"type": "function_call", "name": "view_image", "call_id": "image-call", "arguments": '{"path":"figure.png"}'}},
            {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "image-call", "output": [{"type": "input_image", "image_url": "data:image/png;base64,do-not-copy"}]}}
        ]
        (folder / "rollout-test-session.jsonl").write_text("\n".join(map(json.dumps, events)), encoding="utf-8")
        with patch.dict("os.environ", {"CODEX_HOME": str(home)}):
            audit = audit_images("test-session")
        self.assertEqual(audit["image_results"], 1)
        self.assertNotIn("base64", json.dumps(audit))

    def test_same_command_loop_stops(self):
        self.fake.write_text('''import json,sys
sys.stdin.read()
for i in range(5):
 print(json.dumps({"type":"item.completed","item":{"type":"command_execution","command":"same","status":"failed"}}),flush=True)
''', encoding="utf-8")
        with patch("creation_pipeline.agent.backend.codex_command", return_value=[sys.executable, str(self.fake)]):
            with self.assertRaisesRegex(ModelCallError, "Repeated identical"):
                self.session().stage("test", {}, {})



if __name__ == "__main__":
    unittest.main()


class PreflightTests(unittest.TestCase):
    def test_preflight_uses_selected_cli_settings_without_fetching_sources(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / ".pipeline/test-tmp") as directory:
            root = Path(directory)
            write_json(root / "config.json", {"sources": [{"repo": "https://example.org/unfetched.git"}],
                "model": {"name": "selected-model"}, "http_only": True})
            fake = root / "cli.py"
            fake.write_text('import sys,json\nfrom pathlib import Path\nPath(sys.argv[0]).with_name("args.json").write_text(json.dumps(sys.argv))\nsys.stdin.read()\nprint(json.dumps({"type":"thread.started","thread_id":"probe"}))\nprint(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":"{\\\"ready\\\":true}"}}))\nprint(json.dumps({"type":"turn.completed","usage":{"input_tokens":1}}))\n', encoding="utf-8")
            config = load_config(root / "config.json")
            with patch("creation_pipeline.agent.backend.codex_command", return_value=[sys.executable, str(fake)]), patch("creation_pipeline.resources.acquisition.Acquisition.repository") as acquire:
                receipts = NativeSession.preflight(config, root / "work")
            acquire.assert_not_called()
            args = read_json(root / "args.json")
            self.assertIn("selected-model", args)
            self.assertIn('model_provider="skill-pipeline-http"', args)
            self.assertEqual(receipts[0]["phase"], "preflight")
