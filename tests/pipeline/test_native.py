"""Native lifecycle tests run a fake CLI, never a remote model."""
import json
import os
import subprocess
import time
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

    def test_failed_event_rejects_answer_even_with_completion(self):
        with self.fake.open('a', encoding='utf-8') as stream:
            stream.write('print(json.dumps({"type":"error","message":"transport failed"}),flush=True)\n')
        session = self.session()
        with patch('creation_pipeline.agent.backend.codex_command', return_value=[sys.executable, str(self.fake)]):
            with self.assertRaises(ModelCallError):
                session.stage('test', {}, {})
        self.assertEqual(read_json(session.state_path)['receipts'][0]['status'], 'failed')

    def test_start_failure_has_durable_failed_receipt(self):
        session = self.session()
        with patch('creation_pipeline.agent.backend.codex_command', return_value=[str(self.root / 'missing')]):
            with self.assertRaises(ModelCallError):
                session.stage('test', {}, {})
        self.assertEqual(read_json(session.state_path)['receipts'][0]['status'], 'failed')

    def test_interruption_during_thread_start_preserves_receipt(self):
        import threading
        original = threading.Thread.start
        calls = 0
        def start(thread):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise KeyboardInterrupt()
            return original(thread)
        session = self.session()
        with patch('creation_pipeline.agent.backend.codex_command', return_value=[sys.executable, str(self.fake)]), \
             patch.object(threading.Thread, 'start', start):
            with self.assertRaises(KeyboardInterrupt):
                session.stage('test', {}, {})
        self.assertEqual(read_json(session.state_path)['receipts'][0]['status'], 'interrupted')

    @unittest.skipUnless(os.name == 'posix', 'Detached POSIX session pipe ownership')
    def test_detached_pipe_cannot_block_failed_receipt(self):
        import signal
        self.fake.write_text('import subprocess,sys\nfrom pathlib import Path\nsys.stdin.read()\np=subprocess.Popen([sys.executable,"-c","import time; time.sleep(12)"],start_new_session=True)\nPath(sys.argv[0]).with_name("detached.pid").write_text(str(p.pid))\n', encoding='utf-8')
        session = self.session()
        started = time.monotonic()
        try:
            with patch('creation_pipeline.agent.backend.codex_command', return_value=[sys.executable, str(self.fake)]):
                with self.assertRaises(ModelCallError):
                    session.stage('test', {}, {})
            self.assertLess(time.monotonic() - started, 8)
            saved = read_json(session.state_path)['receipts'][0]
            self.assertEqual(saved['status'], 'failed')
            self.assertFalse(saved['stream_threads_finished'])
        finally:
            pidfile = self.root / 'detached.pid'
            if pidfile.exists():
                try: os.kill(int(pidfile.read_text()), signal.SIGKILL)
                except ProcessLookupError: pass

    def test_nonreading_child_cannot_block_stdin_past_timeout(self):
        from creation_pipeline.models import BudgetError
        self.fake.write_text('import time; time.sleep(30)', encoding='utf-8')
        session = self.session()
        session.limits['model_timeout'] = 1
        started = time.monotonic()
        with patch('creation_pipeline.agent.backend.codex_command', return_value=[sys.executable, str(self.fake)]):
            with self.assertRaises(BudgetError):
                session.stage('x' * 2_000_000, {}, {})
        self.assertLess(time.monotonic() - started, 10)
        self.assertTrue(read_json(session.state_path)['receipts'][0]['stream_threads_finished'])

    def test_reader_exception_is_transport_error_and_reaps_child(self):
        original = subprocess.Popen
        class BrokenReader:
            def __init__(self, stream): self.stream = stream
            def __iter__(self): raise OSError('injected native reader failure')
            def close(self): self.stream.close()
        def start(*args, **kwargs):
            proc = original(*args, **kwargs)
            # Patching subprocess.Popen also affects cleanup helpers. Inject
            # only into the intended fake CLI, not taskkill's communicate().
            if str(self.fake) in args[0] and kwargs.get('stdout') == subprocess.PIPE:
                proc.stdout = BrokenReader(proc.stdout)
            return proc
        session = self.session()
        with patch('creation_pipeline.agent.backend.codex_command', return_value=[sys.executable, str(self.fake)]), \
             patch('creation_pipeline.agent.backend.subprocess.Popen', side_effect=start):
            with self.assertRaisesRegex(ModelCallError, 'I/O'):
                session.stage('test', {}, {})
        saved = read_json(session.state_path)['receipts'][0]
        self.assertTrue(saved['stream_threads_finished'])
        self.assertIn('stdout', str(saved['io_errors']))

    def test_exited_parent_with_inherited_pipe_is_reaped(self):
        self.fake.write_text('import subprocess,sys\nsys.stdin.read()\nsubprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"])\n', encoding='utf-8')
        session = self.session()
        started = time.monotonic()
        with patch('creation_pipeline.agent.backend.codex_command', return_value=[sys.executable, str(self.fake)]):
            with self.assertRaises(ModelCallError):
                session.stage('test', {}, {})
        self.assertLess(time.monotonic() - started, 10)
        self.assertTrue(read_json(session.state_path)['receipts'][0]['stream_threads_finished'])

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

    def test_opt_in_agent_progress_watchdog_stops_a_silent_turn(self):
        from creation_pipeline.models import BudgetError, ModelCallError
        self.fake.write_text('import sys,json,time\nsys.stdin.read()\n'
                             'print(json.dumps({"type":"thread.started","thread_id":"silent"}),flush=True)\n'
                             'time.sleep(30)\n', encoding='utf-8')
        session = self.session()
        session.limits['agent_progress_timeout'] = 1
        started = time.monotonic()
        with patch("creation_pipeline.agent.backend.codex_command", return_value=[sys.executable, str(self.fake)]):
            with self.assertRaisesRegex(ModelCallError, 'no output or process activity') as caught:
                session.stage("test", {}, {})
        # A silent turn is a transport fault, not a budget stop.
        self.assertNotIsInstance(caught.exception, BudgetError)
        self.assertEqual(caught.exception.code, 'model_stalled')
        self.assertLess(time.monotonic() - started, 20)
        saved = read_json(session.state_path)
        self.assertEqual(saved['confidence'] if 'confidence' in saved else saved['sessions'].get('discovery'), 'silent')
        self.assertEqual(saved['receipts'][0]['status'], 'failed')

    def test_agent_progress_watchdog_is_off_by_default(self):
        self.fake.write_text('import sys,json,time\nsys.stdin.read()\n'
                             'print(json.dumps({"type":"thread.started","thread_id":"default-silent"}),flush=True)\n'
                             'time.sleep(1.2)\n'
                             'print(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":json.dumps({"ok":True})}}),flush=True)\n'
                             'print(json.dumps({"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}),flush=True)\n',
                             encoding='utf-8')
        session = self.session()
        self.assertIsNone(session.limits.get('agent_progress_timeout'))
        with patch("creation_pipeline.agent.backend.codex_command", return_value=[sys.executable, str(self.fake)]):
            self.assertEqual(session.stage("test", {}, {}), {'ok': True})

    def test_agent_silence_is_observed_without_terminating(self):
        self.fake.write_text('import sys,json,time\nsys.stdin.read()\n'
                             'print(json.dumps({"type":"thread.started","thread_id":"observed"}),flush=True)\n'
                             'time.sleep(1.5)\n'
                             'print(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":json.dumps({"ok":True})}}),flush=True)\n'
                             'print(json.dumps({"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}),flush=True)\n',
                             encoding='utf-8')
        session = self.session()
        with patch("creation_pipeline.agent.backend.codex_command", return_value=[sys.executable, str(self.fake)]):
            self.assertEqual(session.stage("test", {}, {}), {'ok': True})
        receipt = read_json(session.state_path)['receipts'][0]
        observed = receipt['progress_observation']
        self.assertEqual(observed['watchdog'], 'observe_only')
        self.assertIsNone(observed['progress_timeout_seconds'])
        # Silence is recorded, never acted on, while the total budget still applies.
        self.assertGreaterEqual(observed['max_silence_seconds'], 1.0)
        self.assertEqual(receipt['status'], 'completed')

    def test_agent_progress_watchdog_option_is_validated(self):
        write_json(self.root / "input.json", {"sources": [{"id": "code", "path": "source.py"}],
            "network": False, "limits": {"model_calls": 4, "model_timeout": 10, "agent_progress_timeout": 120}})
        self.assertEqual(load_config(self.root / "input.json")["limits"]["agent_progress_timeout"], 120)
        write_json(self.root / "input.json", {"sources": [{"id": "code", "path": "source.py"}],
            "network": False, "limits": {"agent_progress_timeout": -1}})
        with self.assertRaisesRegex(ValueError, 'Limits'):
            load_config(self.root / "input.json")

    def test_complete_native_build_and_failed_turn_resume(self):
        from creation_pipeline.pipeline import build
        from tests.pipeline.support import MAIN
        from tests.pipeline.test_discovery import candidate, discovery
        plan = discovery(candidate())
        plan.update(outcome="candidates", handoff=[])
        fixture = {"discovery": plan, "main": MAIN}
        write_json(self.root / "fixture.json", fixture)
        # First author turn fails after session creation. Resume must reuse that
        # candidate session without repeating discovery, then run actual checks.
        self.fake.write_text('''import sys,json
from pathlib import Path
d=json.loads(Path(sys.argv[0]).with_name('fixture.json').read_text(encoding='utf-8'))
p=sys.stdin.read(); c=json.loads(p.split('\\nCONTEXT:\\n',1)[1])
phase=c.get('_unused','discovery')
phase='author' if 'output_directory' in c else 'review' if 'artifact' in c else 'discovery'
print(json.dumps({'type':'thread.started','thread_id':'session-'+phase}),flush=True)
if phase=='author':
 marker=Path(sys.argv[0]).with_name('first-author')
 if not marker.exists():
  marker.touch(); sys.exit(1)
 out=Path(c['output_directory']); out.mkdir(parents=True,exist_ok=True)
 (out/'SKILL.md').write_text(d['main'],encoding='utf-8')
 result={'files':[{'path':'SKILL.md','purpose':'Invocation'}],
 'tests':[{'name':'source-result','argv':['{python}','-c','print(2 + 3)'],
 'cwd':'{run}','expected_exit':0,'stdout_contains':['5'],'evidence':'e1','purpose':'Source result','kind':'positive'}], 'issues':[], 'notes':[]}
 Path(c['metadata_path']).parent.mkdir(parents=True,exist_ok=True)
 Path(c['metadata_path']).write_text(json.dumps({'tests':result['tests'],'issues':[],'notes':[]}),encoding='utf-8')
 result={'completed':True,'summary':'written'}
elif phase=='review': result={'status':'pass','resolution':'none','findings':[],'issues_complete':True}
else: result=d['discovery']
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(result)}}),flush=True)
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':2}}),flush=True)
''', encoding="utf-8")
        options = read_json(self.root / "input.json")
        options.update(adoption={"enabled": False}, execute_generated_checks=True)
        options["limits"]["repair_rounds"] = 0
        write_json(self.root / "input.json", options)
        with patch("creation_pipeline.agent.backend.codex_command", return_value=[sys.executable, str(self.fake)]):
            result = build(self.root / "input.json", self.root / "state", keep_debug=True)
            self.assertEqual(result["status"], "failed", result)
            resumed = build(state_root=self.root / "state", resume_id=result["build_id"], keep_debug=True)
        self.assertEqual(resumed["status"], "blocked", resumed)  # no reviewed requirement in this fake CLI result
        summary = read_json(Path(resumed["output"]) / "summary.json")
        self.assertEqual(len(summary["model_metrics"]["receipts"]), 4)
        self.assertEqual(summary["model_metrics"]["receipts"][2]["resumed"], True)


if __name__ == "__main__":
    unittest.main()
