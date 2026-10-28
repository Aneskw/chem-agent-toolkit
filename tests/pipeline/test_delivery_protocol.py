"""Real filesystem/transaction tests with simulated author/reviewer decisions.

These tests are not model-quality or Docker acceptance evidence.
"""
import copy
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.pipeline import test_discovery as f
from tests.pipeline.test_discovery import candidate, discovery
from tests.pipeline.support import ReplayStages
from creation_pipeline.artifacts import store
from creation_pipeline.artifacts.evidence import verify
from creation_pipeline.artifacts.package import install, manifest
from creation_pipeline.contracts import qualify, fingerprint, inputs_for, versioned
from creation_pipeline.pipeline import build
from creation_pipeline.records import read_json, write_json


TEXT_SOURCE = "This checklist is applied by reading and comparing the supplied paragraphs; no program or external tool is required."


def text_artifact():
    return {"files": [{"path": "SKILL.md", "purpose": "Reading checklist", "content":
        "---\nname: add-numbers\ndescription: Review paragraphs using a reading checklist.\n---\n"
        "Read the supplied paragraphs and compare their stated assumptions. No executable is needed.\n"}],
        "tests": [], "issues": [], "notes": [], "runtime_requirement": {
            "status": "not_required", "reason": "Source explicitly defines a reading-only procedure",
            "citations": [{"source_id": "tool", "path": "api.py", "quote": TEXT_SOURCE}]}}


def configure_text(case):
    case.source.write_text(TEXT_SOURCE, encoding="utf-8")
    case.options["checks"] = []
    write_json(case.config, case.options)


class DeliveryProtocolTests(unittest.TestCase):
    def setUp(self):
        self.c = f.DiscoveryTests()
        self.c.setUp()
        configure_text(self.c)
        self.c.options["adoption"] = {"enabled": True}
        write_json(self.c.config, self.c.options)
        self.lib = self.c.root / "library"

    def tearDown(self):
        self.c.tearDown()

    def run_text(self, artifact=None, **kwargs):
        artifact = text_artifact() if artifact is None else artifact
        result, summary = self.c.run_case(discovery(candidate()), artifact, library_root=self.lib, **kwargs)
        self.assertFalse(result["errors"], result)
        record = read_json(Path(result["output"]) / "records/add-numbers.json")
        return result, record

    def test_text_accepted_and_installable(self):
        result, record = self.run_text()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(record["delivery"]["execution"]["status"], "not_run")
        self.assertEqual(record["delivery"]["host"]["status"], "not_applicable")
        entry = store.get(self.lib, "add-numbers")
        self.assertEqual(entry["zone"], "accepted")
        installed = store.install_from_library(self.lib, "add-numbers", self.c.root / "installed")
        self.assertEqual(manifest(Path(installed["installed"])), record["files"])
        self.assertTrue(install(result["output"], self.c.root / "output-install"))

    def test_source_inventory_order_does_not_hide_byte_drift(self):
        directory = self.c.root / 'source-directory'
        directory.mkdir()
        (directory / 'api.py').write_text(TEXT_SOURCE, encoding='utf-8')
        (directory / 'README.md').write_text('Source release notes', encoding='utf-8')
        self.c.options['sources'][0]['path'] = str(directory)
        write_json(self.c.config, self.c.options)
        result, record = self.run_text()
        self.assertEqual(result['status'], 'ready', result)
        entry = store.get(self.lib, 'add-numbers')
        frozen = self.lib / entry['evidence']
        verify(frozen, entry['freeze_sha256'])
        (frozen / 'sources/tool/README.md').write_text('changed bytes', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed'):
            verify(frozen, entry['freeze_sha256'])
        self.assertEqual(store.entries(self.lib), [])

    def test_draft_never_accepted_even_when_no_execution_needed(self):
        with patch("creation_pipeline.validation.checks.execute", side_effect=AssertionError("draft executed")):
            result, record = self.run_text(draft_only=True, execute_generated=True)
        self.assertEqual(result["status"], "draft")
        self.assertFalse(qualify(record["delivery"])[0])
        self.assertEqual(store.entries(self.lib), [])
        with self.assertRaises(ValueError):
            store.get(self.lib, "add-numbers")
        entry = store.get(self.lib, "add-numbers", include_candidates=True)
        self.assertEqual(entry["zone"], "candidates")
        with self.assertRaises(ValueError):
            store.install_from_library(self.lib, "add-numbers", self.c.root / "installed")
        with self.assertRaises(ValueError):
            install(result["output"], self.c.root / "output-install")

    def test_unknown_and_required_are_not_formal(self):
        for state in ("unknown", "required"):
            with self.subTest(state=state):
                artifact = text_artifact()
                artifact["runtime_requirement"]["status"] = state
                # Mechanism fixture: review confirms the declaration, no real model evidence.
                result, record = self.run_text(artifact)
                self.assertFalse(record["delivery"]["qualification"]["accepted"])
                self.assertEqual(record["content_status"], "passed")
                self.assertEqual(record["delivery"]["execution"]["status"], "runtime_blocked")
                self.assertEqual(record["runtime"]["execution_status"], "runtime_blocked")
                self.assertEqual(store.entries(self.lib), [])

    def test_unreviewed_or_fabricated_requirement_is_unknown(self):
        artifact = text_artifact()
        artifact["runtime_requirement"]["citations"][0]["quote"] = "fabricated"
        _, record = self.run_text(artifact)
        self.assertEqual(record["delivery"]["inputs"]["requirement"]["status"], "unknown")
        result, _ = self.c.run_case(discovery(candidate()), text_artifact(),
            {"status": "pass", "resolution": "none", "findings": [], "requirement_assessment": "unknown"},
            library_root=self.c.root / "other")
        self.assertEqual(result["status"], "blocked")
        artifact = text_artifact()
        artifact["runtime_requirement"] = "none"
        _, malformed = self.run_text(artifact)
        self.assertEqual(malformed["delivery"]["inputs"]["requirement"]["status"], "unknown")

    def test_durable_sources_survive_run_and_cache_cleanup(self):
        result, _ = self.run_text()
        entry = store.get(self.lib, "add-numbers")
        shutil.rmtree(self.c.state)
        self.c.source.unlink()
        frozen = verify(self.lib / entry["evidence"], entry["freeze_sha256"])
        self.assertTrue(qualify(frozen["delivery"])[0])
        self.assertEqual(store.get(self.lib, "add-numbers")["revision_id"], entry["revision_id"])
        self.assertTrue((self.lib / entry["evidence"] / "sources/tool/api.py").is_file())
        self.assertFalse(Path(entry["evidence"]).is_absolute())

    def test_active_file_drift_demotes_without_destroying_frozen_history(self):
        _, _ = self.run_text()
        old = store.get(self.lib, "add-numbers")
        (self.lib / old["path"] / "SKILL.md").write_text("changed", encoding="utf-8")
        self.assertEqual(store.entries(self.lib), [])
        current = store.get(self.lib, "add-numbers", include_candidates=True)
        self.assertIn("invalidated", current)
        self.assertFalse((self.lib / "accepted/add-numbers").exists())
        self.assertEqual((self.lib / "candidates/add-numbers/SKILL.md").read_text(), "changed")
        self.assertTrue(qualify(verify(self.lib / old["evidence"], old["freeze_sha256"])["delivery"])[0])

    def test_source_or_contract_tampering_revokes_qualification(self):
        for target in ("sources/tool/api.py", "record.json"):
            with self.subTest(target=target):
                self.lib = self.c.root / ("lib-" + str(len(list(self.c.root.glob("lib-*")))))
                self.run_text()
                old = store.get(self.lib, "add-numbers")
                path = self.lib / old["evidence"] / target
                path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
                self.assertEqual(store.entries(self.lib), [])
                current = store.get(self.lib, "add-numbers", include_candidates=True)
                self.assertIn("invalidated", current)

    def test_replacement_preserves_pending_evidence_and_revoked_assessment(self):
        artifact = text_artifact(); artifact['runtime_requirement']['status'] = 'required'
        self.run_text(artifact)
        value = store.catalog(self.lib); entry = value['skills'][0]
        pending = {'path': 'runtime/interrupted', 'files': [], 'reason': 'Imported failed attempt'}
        (self.lib / pending['path']).mkdir(parents=True)
        entry['pending_runtime'] = pending
        entry['current_content'] = {'status': 'failed'}
        write_json(self.lib/'catalog.json', value)
        self.c.options['revision_parents'] = {'add-numbers': entry['revision_id']}
        write_json(self.c.config, self.c.options)
        self.run_text()
        current = store.get(self.lib, 'add-numbers')
        previous = current['history'][-1]
        self.assertEqual(previous['pending_runtime'], pending)
        self.assertEqual(previous['current_content'], {'status': 'failed'})
        self.assertTrue((self.lib/previous['pending_runtime']['path']).is_dir())

    def test_changed_inputs_create_new_revision_and_retain_history(self):
        self.run_text()
        old = store.get(self.lib, "add-numbers")
        self.c.options["revision_parents"] = {"add-numbers": old["revision_id"]}
        write_json(self.c.config, self.c.options)
        artifact = text_artifact()
        artifact["files"][0]["content"] += "\nA revised reading instruction.\n"
        self.c.source.write_text(TEXT_SOURCE + "\nAdditional source context.", encoding="utf-8")
        self.run_text(artifact)
        new = store.get(self.lib, "add-numbers")
        self.assertNotEqual(old["revision_id"], new["revision_id"])
        self.assertEqual(old["candidate_id"], new["candidate_id"])
        self.assertEqual(new["history"][0]["revision_id"], old["revision_id"])
        self.assertTrue(verify(self.lib / old["evidence"], old["freeze_sha256"]))

    def test_promotion_requires_new_review_and_explicit_revision_parent(self):
        self.run_text(draft_only=True)
        old = store.get(self.lib, "add-numbers", include_candidates=True)
        self.c.options["revision_parents"] = {"add-numbers": old["revision_id"]}
        write_json(self.c.config, self.c.options)
        result, _ = self.run_text()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(store.get(self.lib, "add-numbers")["zone"], "accepted")
        self.assertFalse((self.lib / "candidates/add-numbers").exists())
        self.assertEqual(len(store.get(self.lib, "add-numbers")["history"]), 1)

    def test_manifest_and_contracts_cannot_be_relaxed_for_reuse(self):
        _, record = self.run_text()
        original = record["delivery"]
        for field in ("files", "sources", "bindings", "environment", "acceptance"):
            changed = copy.deepcopy(original)
            changed["inputs"][field] = {"changed": True}
            self.assertFalse(qualify(changed)[0], field)
        for field in ("bindings", "environment", "acceptance"):
            changed = copy.deepcopy(original)
            changed["inputs"][field] = versioned({"changed": True}, 2)
            self.assertNotEqual("rev-" + fingerprint(changed["inputs"]), original["revision_id"])

    def test_required_cannot_be_accepted_by_forged_pass_boolean(self):
        artifact = text_artifact()
        artifact["runtime_requirement"]["status"] = "required"
        _, record = self.run_text(artifact)
        delivery = record["delivery"]
        delivery["execution"].update(status="passed", accepted=True)
        delivery["host"]["status"] = "available"
        self.assertFalse(qualify(delivery)[0])

    def test_catalog_write_failure_restores_old_package_and_history(self):
        self.run_text()
        old = store.get(self.lib, "add-numbers")
        before = (self.lib / "catalog.json").read_bytes()
        self.c.options["revision_parents"] = {"add-numbers": old["revision_id"]}
        write_json(self.c.config, self.c.options)
        artifact = text_artifact()
        artifact["files"][0]["content"] += "\nRevised.\n"
        actual_write = store.write_json
        def fail_catalog(path, value):
            if Path(path).name == "catalog.json":
                raise OSError("injected catalog disk failure")
            return actual_write(path, value)
        with patch.object(store, "write_json", side_effect=fail_catalog):
            result, _ = self.c.run_case(discovery(candidate()), artifact, library_root=self.lib)
        self.assertEqual(result["status"], "failed")
        self.assertEqual((self.lib / "catalog.json").read_bytes(), before)
        self.assertEqual(store.get(self.lib, "add-numbers")["revision_id"], old["revision_id"])
        self.assertFalse((self.lib / ".transaction.json").exists())
        self.assertFalse((self.lib / ".catalog.lock").exists())

    def test_mixed_text_and_unknown_preserves_partial(self):
        other = text_artifact()
        other["files"][0]["content"] = other["files"][0]["content"].replace("name: add-numbers", "name: unknown")
        other.pop("runtime_requirement")
        result, _ = self.c.run_case(discovery(candidate(), candidate("unknown")), text_artifact(), other, library_root=self.lib)
        self.assertEqual(result["status"], "partial", result)
        self.assertEqual([e["name"] for e in store.entries(self.lib)], ["add-numbers"])
        self.assertEqual(len(store.entries(self.lib, include_candidates=True)), 2)

    def test_receipt_is_not_final_qualification_and_frozen_output_detects_edit(self):
        result, record = self.run_text()
        package = Path(result["output"]) / "bundle/skills/add-numbers/SKILL.md"
        package.write_text("changed", encoding="utf-8")
        with self.assertRaises(ValueError):
            install(result["output"], self.c.root / "installed")

    def test_interrupted_precommit_is_rolled_back_on_next_access(self):
        self.run_text()
        entry = store.get(self.lib, "add-numbers")
        txid = "interrupted-test"
        stage = self.lib / ".transactions" / txid
        stage.mkdir(parents=True)
        original = self.lib / entry["path"]
        original.rename(stage / "backup-0")
        original.mkdir()
        (original / "SKILL.md").write_text("uncommitted", encoding="utf-8")
        write_json(self.lib / ".transaction.json", {"id": txid, "operations": [{
            "target": entry["path"], "backup": ".transactions/" + txid + "/backup-0", "existed": True, "new": None}]})
        self.assertEqual(store.get(self.lib, "add-numbers")["revision_id"], entry["revision_id"])
        self.assertEqual(manifest(original), entry["delivery"]["inputs"]["files"])
        self.assertFalse(stage.exists())

    def test_library_lock_refuses_concurrent_access(self):
        self.run_text()
        with store.locked(self.lib):
            with self.assertRaises(FileExistsError):
                store.entries(self.lib)

    def test_runtime_handoff_binds_all_inputs_without_executor(self):
        from creation_pipeline.contracts import runtime_request
        _, record = self.run_text()
        entry = store.get(self.lib, "add-numbers")
        frozen = self.lib / entry["evidence"]
        request = runtime_request(record["delivery"], frozen, entry["freeze_sha256"], self.lib / "future-attempts")
        self.assertEqual(request.revision_id, record["delivery"]["revision_id"])
        self.assertEqual(request.source_fingerprint, record["delivery"]["fingerprints"]["sources"])
        self.assertEqual(request.acceptance_fingerprint, record["delivery"]["fingerprints"]["acceptance"])
        with self.assertRaises(ValueError):
            runtime_request(record["delivery"], frozen, entry["freeze_sha256"], frozen / "logs")
        with self.assertRaises(ValueError):
            runtime_request(record["delivery"], frozen, entry["freeze_sha256"], frozen.parent)

    def test_credential_source_is_not_copied_to_library(self):
        self.c.source.write_text(TEXT_SOURCE + "\napi_key=sk-examplecredentialvalue123456789", encoding="utf-8")
        result, _ = self.c.run_case(discovery(candidate()), text_artifact(), library_root=self.lib)
        self.assertEqual(result["status"], "failed")
        self.assertFalse((self.lib / "catalog.json").exists())

    def test_cli_requires_explicit_candidate_selection(self):
        import io
        from contextlib import redirect_stdout
        from creation_pipeline.cli import main
        self.run_text(draft_only=True)
        stream = io.StringIO()
        with redirect_stdout(stream):
            self.assertEqual(main(["library", str(self.lib)]), 0)
        self.assertEqual(json.loads(stream.getvalue())["skills"], [])
        stream = io.StringIO()
        with redirect_stdout(stream):
            self.assertEqual(main(["library", str(self.lib), "--include-candidates"]), 0)
        self.assertEqual(len(json.loads(stream.getvalue())["skills"]), 1)

    def test_legacy_ready_record_is_not_installable(self):
        output = self.c.root / "legacy"
        output.mkdir()
        write_json(output / "build.json", {"status": "ready"})
        with self.assertRaises(ValueError):
            install(output, self.c.root / "installed")

    def test_structured_credentials_are_redacted(self):
        from creation_pipeline.records import sanitized, redact
        self.assertEqual(sanitized({"password": "opaque-value"})["password"], "[REDACTED]")
        self.assertNotIn("opaque-value", redact('{"api_key": "opaque-value"}'))

    def test_config_cannot_silently_override_authored_requirement(self):
        self.c.options["runtime_requirements"] = {"add-numbers": text_artifact()["runtime_requirement"]}
        write_json(self.c.config, self.c.options)
        artifact = text_artifact()
        artifact["runtime_requirement"]["status"] = "required"
        _, record = self.run_text(artifact)
        self.assertEqual(record["delivery"]["inputs"]["requirement"]["status"], "unknown")
        self.assertEqual(store.entries(self.lib), [])

    def test_draft_permission_is_false_even_with_execution_flag(self):
        self.run_text(draft_only=True, execute_generated=True)
        author = [p for p in self.c.last_backend.prompts if '"output_directory"' in p][0]
        self.assertIn('"generated_checks_enabled": false', author)


if __name__ == "__main__":
    unittest.main()
