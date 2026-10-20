"""One task, explicit stages, bounded repair and separate installation."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from . import __version__
from .analyze import ROOT, analyze
from .author import author, review
from .checks import classify, run_checks, static_checks
from .intake import Sources
from .model_backend import CodexBackend, Session
from .models import BlockedError, load_config
from .package import manifest
from .records import clean_run, digest, has_link, now, redact, sanitized, write_json


def build(config_path, state_root=None, *, plan_only=False, keep_debug=False,
          execute_generated=False, backend=None, notify=lambda message: None):
    config = load_config(config_path)
    config["_deadline"] = time.monotonic() + config["limits"]["total_seconds"]
    state = Path(state_root or ROOT / ".pipeline").absolute()
    if has_link(state):
        raise ValueError("State directory must not contain linked paths")
    build_id = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    work = state / "runs" / build_id
    if has_link(work):
        raise ValueError("Run directory must not contain linked paths")
    work.mkdir(parents=True, exist_ok=False)
    write_json(work / "workspace.json", {"build_id": build_id, "workspace": str(work.resolve())})
    record = {"schema_version": 1, "build_id": build_id, "started_at": now(),
              "pipeline_version": __version__, "task": config["task"], "status": "failed",
              "plan": None, "checks": [], "files": [], "sources": [], "evidence": [],
              "model_calls": [], "replay": bool(getattr(backend, "replay", False)),
              "agent_efficacy": "not_evaluated_separate_work", "full_replay_available": False,
              "configuration": {"intent": config["intent"], "limits": config["limits"],
                                "requested_model": config.get("model"), "http_only": config.get("http_only", False)},
              "input_config_sha256": digest(Path(config_path).read_bytes()),
              "execution_policy": {"generated_checks_enabled": execute_generated,
                                   "environment_variable_names": config["environment"].get("allow", [])},
              "specifications": {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in
                                 (ROOT / "docs/skills/minimum.md", ROOT / "docs/skills/packaging.md")}}
    ref = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True)
    record["pipeline_revision"] = {"commit": ref.stdout.strip() if not ref.returncode else None,
                                   "working_tree_dirty": bool(dirty.stdout.strip())}
    session, sources, artifact, staging = None, None, None, work / "staging"
    try:
        notify("Reading source index and analyzing the task")
        sources = Sources(config, state / "cache")
        record["sources"] = sources.manifest()
        session = Session(backend or CodexBackend(config.get("model"), work / "model-calls", config.get("http_only", False)),
                          sources, config["limits"], work, keep_debug)
        plan = analyze(session, config)
        record["plan"] = plan
        record["evidence"] = sources.validate_evidence(plan["evidence"])
        if plan["readiness"] == "blocked":
            raise BlockedError("; ".join(plan["gaps"]) or "No callable/recoverable implementation")
        if plan_only:
            record["status"] = "draft"
            record["operation"] = "plan_only_no_artifact"
        else:
            feedback, previous_signature = None, None
            for iteration in range(config["limits"]["repair_rounds"] + 1):
                notify(f"Authoring files and checking results (attempt {iteration + 1})")
                record["repair_rounds"] = iteration
                try:
                    artifact = author(session, config, plan, staging, feedback, artifact)
                except ValueError as exc:
                    feedback = [{"name": "author_response", "status": "fail", "required": True,
                                 "findings": [redact(exc)]}]
                    record["checks"], record["status"] = feedback, "failed"
                    if iteration < config["limits"]["repair_rounds"]:
                        continue
                    raise
                record["author_notes"] = artifact.get("notes", [])
                record["file_purposes"] = [{"path": f["path"], "purpose": f["purpose"]} for f in artifact["files"]]
                record["test_definitions"] = {"configured": config["checks"], "generated": artifact["tests"]}
                record["coverage"] = artifact["coverage"]
                # Checks must not silently modify the artifact they are validating.
                before = manifest(staging)
                reports = static_checks(staging, plan["name"], artifact.get("coverage"))
                record["checks"] = reports
                if not any(r["status"] == "fail" for r in reports):
                    reports += run_checks(config, artifact, staging, sources, work / f"attempt-{iteration + 1}", execute_generated)
                    if manifest(staging) != before:
                        reports.append({"name": "artifact_immutability", "required": True, "status": "fail",
                                        "findings": ["Check modified package files; repair must produce clean files"]})
                    changed_sources = []
                    for evidence in sources.evidence:
                        source_path = sources._file(evidence["source"], evidence["path"])
                        if digest(source_path.read_bytes()) != evidence["sha256"]:
                            changed_sources.append(evidence["source"] + ":" + evidence["path"])
                    if changed_sources:
                        raise ValueError("Sources changed during build: " + ", ".join(sorted(set(changed_sources))))
                    # Nontrivial new code and domain judgments receive a separate targeted review.
                    if plan["intent"] == "extension" or any(f["path"].startswith("scripts/") for f in artifact["files"]):
                        reports.append(review(session, plan, artifact, reports))
                    if plan["intent"] == "extension":
                        kinds = {r.get("kind") for r in reports if r.get("status") == "pass"}
                        if not {"positive", "negative"}.issubset(kinds):
                            reports.append({"name": "extension_positive_negative", "status": "not_run", "required": True,
                                            "findings": ["Extension needs executed passing and failing cases"]})
                record["checks"] = reports
                record["status"] = classify(reports)
                record["repair_rounds"] = iteration
                if record["status"] != "failed":
                    break
                feedback = [r for r in reports if r["status"] == "fail"]
                signature = digest(json.dumps([
                    {"name": item["name"], "findings": item.get("findings", [])}
                    for item in feedback], sort_keys=True).encode())
                if signature == previous_signature:
                    record["stopped_reason"] = "Repeated unchanged failure"
                    break
                previous_signature = signature
    except BlockedError as exc:
        record["status"], record["error"] = "blocked", redact(exc)
    except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError) as exc:
        record["status"], record["error"] = "failed", redact(exc)
    finally:
        if session:
            record["model_calls"] = session.receipts
        if sources:
            # Retain actual read slices for claims/oracles even if a later stage fails.
            record["evidence"] = sources.compact_evidence()
        record["finished_at"] = now()
        usages = [r["usage"] for r in record["model_calls"] if isinstance(r.get("usage"), dict)]
        fields = {key for usage in usages for key, value in usage.items() if type(value) is int}
        record["model_metrics"] = {
            "calls_attempted": len(record["model_calls"]),
            "usage_fully_reported": bool(record["model_calls"]) and len(usages) == len(record["model_calls"]),
            "reported_token_totals": {key: sum(u.get(key, 0) for u in usages) for key in fields} if usages else None,
            "monetary_cost": None,
        }
    failure = record["status"] in ("failed", "blocked")
    output = state / ("failures" if failure else "outputs") / build_id
    if has_link(output):
        raise ValueError("Output directory must not contain linked paths")
    output.mkdir(parents=True, exist_ok=False)
    if staging.exists() and record["plan"]:
        target = output / record["plan"]["name"]
        # Do not copy linked or unregistered files even on a failed check.
        try:
            files = manifest(staging)
            shutil.copytree(staging, target)
            if manifest(target) != files:
                raise ValueError("Output copy differs from checked staging files")
            record["package"], record["files"] = target.name, files
        except ValueError as exc:
            record["status"], record["error"] = "failed", redact(exc)
    record["temporary_workspace"] = str(work) if failure or keep_debug or record["status"] != "ready" else None
    record = sanitized(record)
    write_json(output / "build.json", record)
    if record["status"] == "ready" and not keep_debug:
        clean_run(state, build_id)
    return {"build_id": build_id, "status": record["status"], "output": str(output),
            "model_calls": len(record["model_calls"]), "error": record.get("error")}
