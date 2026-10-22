"""Discover once, build skills independently, verify and adopt ready packages."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import time
import uuid
from collections import Counter
from pathlib import Path

from . import __version__
from .acquisition import Acquisition
from .analyze import ROOT, analyze, ordered, specifications, validate_discovery
from .author import author, review
from .checks import classify, run_checks, static_checks
from .intake import Sources
from .model_backend import Session
from .models import BlockedError, ModelCallError, load_config
from .package import manifest
from .providers import backend_for
from .library import adopt
from .schemas import DISCOVERY
from .records import clean_run, digest, has_link, now, read_json, redact, sanitized, write_json, safe_relative


def hash_object(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def _restore(document, state, replan=False):
    if document.get("schema_version") != 3:
        raise ValueError("Legacy plan schema: rediscover with the skill-only pipeline")
    config = copy.deepcopy(document["config"])
    current_specs = specifications()
    changed = {p for p in current_specs if current_specs[p] != document["specifications"].get(p)}
    author_only = {"creation_pipeline/prompts/author.md", "creation_pipeline/prompts/review.md"}
    if changed - author_only and not replan:
        raise ValueError("Discovery/content specifications changed; run discovery again before building")
    config["_revalidated_prompts"] = sorted(changed)
    sources = Sources.__new__(Sources)
    sources.config, sources.limits = config, config["limits"]
    sources.cache, sources.total_bytes = state / "cache", 0
    sources.acquisition = Acquisition(config, sources.cache)
    sources.restore(document["sources"], document["evidence"], document.get("source_errors", []))
    sources.acquisition.requests = document.get("network_requests", 0)
    validate_discovery(document["discovery"], config, sources)
    return config, sources


def _candidate(session, config, entity, bundle, work, allow_generated):
    directory = safe_relative(bundle, "skills/" + entity["name"])
    record = {"name": entity["name"], "kind": entity["kind"], "plan": entity, "status": "failed",
              "checks": [], "repair_rounds": 0, "files": [], "repair_history": []}
    if entity["readiness"] == "blocked":
        record.update(status="blocked", error="; ".join(entity["gaps"]))
        return record
    before_calls, global_limit = len(session.receipts), session.limits["model_calls"]
    session.limits["model_calls"] = min(global_limit, before_calls + config["limits"]["candidate_calls"])
    previous, feedback, signature = None, [], None
    failed_oracles = {}
    scoped = copy.deepcopy(config)
    scoped["execute_generated_checks"] = allow_generated
    scoped["checks"] = [t for t in config["checks"] if t.get("candidate") == entity["name"]]
    try:
        for attempt in range(config["limits"]["repair_rounds"] + 1):
            record["repair_rounds"] = attempt
            try:
                scoped["_previous_issues"] = previous.get("issues", []) if previous else []
                artifact = author(session, scoped, entity, directory, feedback, previous)
                previous = artifact
                reports = static_checks(directory, entity["name"], artifact["coverage"], bundle)
                initial = manifest(bundle)
                if not any(r["status"] == "fail" for r in reports):
                    reports += run_checks(scoped, artifact, directory, session.sources,
                                          work / entity["name"] / f"attempt-{attempt}", allow_generated)
                    if initial != manifest(bundle):
                        reports.append({"name": "artifact_immutability", "status": "fail", "required": True,
                                        "findings": ["Execution modified bundle files"]})
                    session.sources.verify()
                    reports.append(review(session, entity, artifact, reports, scoped))
                    if entity["intent"] == "extension":
                        kinds = {r.get("kind") for r in reports if r["status"] == "pass"}
                        if not {"positive", "negative"}.issubset(kinds):
                            reports.append({"name": "extension_positive_negative", "status": "not_run", "required": True,
                                            "findings": ["Extension requires executed positive and negative cases"]})
                issues = artifact.get("issues", [])
                if not isinstance(issues, list) or any(not isinstance(i, dict) or type(i.get("blocking")) is not bool for i in issues):
                    raise ValueError("Invalid structured issues")
                if any(i["blocking"] for i in issues):
                    reports.append({"name": "blocking_issues", "status": "not_run", "required": True,
                                    "findings": [i["description"] for i in issues if i["blocking"]]})
                current_tests = {t["name"]: t for t in artifact["tests"]}
                changed = [name for name, oracle in failed_oracles.items()
                    if name not in current_tests or oracle != {k: current_tests[name].get(k) for k in
                        ("expected_exit", "stdout_contains", "json_equals", "artifacts")}]
                if changed:
                    reports.append({"name": "changed_failed_oracles", "status": "not_run", "required": True,
                        "findings": ["Previously failed checks removed/expected results changed; requires independent oracle review: " + ", ".join(changed)]})
                record.update(status=classify(reports), checks=reports, coverage=artifact["coverage"],
                    test_definitions={"configured": scoped["checks"], "generated": artifact["tests"]},
                    issues=issues, notes=artifact.get("notes", []), file_purposes=[{"path": f["path"], "purpose": f["purpose"]} for f in artifact["files"]])
                if record["status"] != "failed":
                    record.pop("error", None)
                    break
                record["repair_history"].append({"attempt": attempt, "checks": reports,
                                                "generated_tests": artifact["tests"]})
                for report in reports:
                    if report["status"] == "fail" and report.get("origin") == "generated" and report["name"] in current_tests:
                        test = current_tests[report["name"]]
                        failed_oracles[test["name"]] = {k: test.get(k) for k in
                            ("expected_exit", "stdout_contains", "json_equals", "artifacts")}
                feedback = [r for r in reports if r["status"] == "fail"]
            except (ValueError, OSError, KeyError, TypeError) as exc:
                if isinstance(exc, ModelCallError):
                    record.update(status="failed", error=redact(exc), stopped_reason="Model backend failure; no file-repair retry")
                    break
                if isinstance(exc, BlockedError):
                    record.update(status="blocked", error=redact(exc))
                    break
                feedback = [{"name": "author_or_validation", "status": "fail", "required": True, "findings": [redact(exc)]}]
                record.update(status="failed", checks=feedback, error=redact(exc))
            current = hash_object(feedback)
            if current == signature:
                record["stopped_reason"] = "Repeated unchanged failure"
                break
            signature = current
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        record.update(status="failed", error=redact(exc))
    finally:
        session.limits["model_calls"] = global_limit
        record["model_calls"] = session.receipts[before_calls:]
        if directory.exists():
            record["files"] = manifest(directory)
    return record


def build(config_path=None, state_root=None, *, plan_only=False, plan_path=None, keep_debug=False,
          execute_generated=False, backend=None, notify=lambda message: None, feedback=None,
          library_root=None, no_adopt=False):
    state = Path(state_root or ROOT / ".pipeline").absolute()
    if has_link(state):
        raise ValueError("State root must not contain linked paths")
    build_id = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    work = safe_relative(state, "runs/" + build_id)
    output = safe_relative(state, "outputs/" + build_id)
    work.mkdir(parents=True)
    output.mkdir(parents=True)
    write_json(work / "workspace.json", {"build_id": build_id, "workspace": str(work.resolve())})
    record = {"schema_version": 3, "pipeline_version": __version__, "build_id": build_id,
              "started_at": now(), "status": "failed", "entities": [], "errors": [],
              "agent_efficacy": "not_evaluated_separate_work", "replay": bool(getattr(backend, "replay", False))}
    implementation = [p for p in sorted((ROOT / "creation_pipeline").rglob("*")) if p.suffix in (".py", ".md")]
    implementation.append(ROOT / "examples/verify_python_example.py")
    record["implementation_sha256"] = hash_object({p.relative_to(ROOT).as_posix(): digest(p.read_bytes())
                                                  for p in implementation})
    session, sources, plan, config = None, None, None, None
    prior_output = None
    try:
        if plan_path:
            if has_link(Path(plan_path)):
                raise ValueError("Linked plan path")
            document = read_json(plan_path)
            prior_output = Path(plan_path).absolute().parent
            lock = read_json(prior_output / "sources.lock.json")
            if hash_object({k: document[k] for k in ("config", "sources", "evidence", "source_errors", "specifications", "network_requests")}) != lock["source_context_sha256"]:
                raise ValueError("Plan source context changed; rediscover rather than editing source evidence")
            config, sources = _restore(document, state, replan=feedback is not None)
            plan = document["discovery"]
            notify("Continuing saved discovery plan; no discovery model call")
        else:
            config = load_config(config_path)
            config["_deadline"] = time.monotonic() + config["limits"]["total_seconds"]
            notify("Acquiring and snapshotting sources")
            sources = Sources(config, state / "cache")
        config.setdefault("_deadline", time.monotonic() + config["limits"]["total_seconds"])
        session = Session(backend or backend_for(config, work / "model-calls"), sources,
                          copy.deepcopy(config["limits"]), work, keep_debug)
        session.started = config["_deadline"] - config["limits"]["total_seconds"]
        session.notify = notify
        if feedback is not None:
            if plan is None:
                raise ValueError("Revision requires --plan")
            context = {"previous_discovery": plan, "feedback": feedback, "sources": sources.index(),
                       "read_evidence": sources.compact_evidence(), "user_guidance": config["prompt"],
                       "constraints": config["constraints"], "user_notes": config["notes"]}
            revised = session.stage((ROOT / "creation_pipeline/prompts/revise.md").read_text(encoding="utf-8"), context,
                                    schema=DISCOVERY)
            plan = validate_discovery(revised, config, sources)
            write_json(output / "revision.json", {"parent": str(Path(plan_path).absolute()), "feedback": feedback})
        if plan is None:
            notify("Discovering capabilities and choosing packaging directions")
            plan = analyze(session, config)
        config["_handoff"] = plan.get("handoff", [])
        sources.verify()
        clean_config = {k: v for k, v in config.items() if not k.startswith("_")}
        document = {"schema_version": 3, "config": clean_config, "discovery": plan,
                    "sources": sources.manifest(), "evidence": sources.evidence,
                    "source_errors": sources.errors, "specifications": specifications(),
                    "network_requests": sources.acquisition.requests}
        document = sanitized(document)
        write_json(output / "plan.json", sanitized(document))
        write_json(output / "sources.lock.json", {"source_context_sha256": hash_object({k: document[k] for k in
            ("config", "sources", "evidence", "source_errors", "specifications", "network_requests")})})
        record["accepted_plan_sha256"] = hash_object(plan)
        record["revalidated_prompts"] = config.get("_revalidated_prompts", [])
        record["source_context_sha256"] = hash_object({k: document[k] for k in
            ("config", "sources", "evidence", "source_errors", "specifications", "network_requests")})
        if plan_only:
            record["status"] = "planned" if plan["candidates"] else "no_candidates"
        else:
            bundle = work / "bundle"
            bundle.mkdir()
            selected = [e for e in ordered(plan) if e["selected"]]
            roots = selected[:config["limits"]["max_builds"]]
            record["deferred"] = [e["name"] for e in selected[len(roots):]]
            outcomes = {}
            for entity in roots:
                name = entity["name"]
                notify("Building skill: " + name)
                fingerprint = hash_object({"entity": entity, "config": clean_config, "sources": sources.manifest(),
                                           "specs": specifications(), "code": record["implementation_sha256"]})
                entity_record = None
                if prior_output and (prior_output / "records" / (name + ".json")).exists():
                    old = read_json(prior_output / "records" / (name + ".json"))
                    old_path = safe_relative(prior_output, "bundle/skills/" + name)
                    if old.get("fingerprint") == fingerprint and old["status"] == "ready" and manifest(old_path) == old["files"]:
                        shutil.copytree(old_path, bundle / "skills" / name)
                        entity_record = dict(old, reused_from=prior_output.name, model_calls=[])
                if entity_record is None:
                    entity_record = _candidate(session, config, entity, bundle, work,
                                              execute_generated or config["execute_generated_checks"])
                entity_record["fingerprint"] = fingerprint
                # Run the delivered files from a different directory before readiness.
                if entity_record["status"] == "ready" and not entity_record.get("reused_from"):
                    relocated = work / "relocated" / name
                    shutil.copytree(bundle / "skills" / name, relocated)
                    artifact = {"tests": entity_record["test_definitions"]["generated"]}
                    scoped = copy.deepcopy(config)
                    scoped["checks"] = entity_record["test_definitions"]["configured"]
                    checks = run_checks(scoped, artifact, relocated, sources, work / "relocation-checks" / name,
                                        execute_generated or config["execute_generated_checks"])
                    if manifest(relocated) != entity_record["files"]:
                        checks.append({"name": "relocation_immutability", "status": "fail", "required": True, "findings": ["Relocated files changed"]})
                    entity_record["checks"] += checks
                    entity_record["status"] = classify(entity_record["checks"])
                outcomes[name] = entity_record
                write_json(output / "records" / (name + ".json"), sanitized(entity_record))
                record["entities"].append({"name": name, "kind": "skill", "status": entity_record["status"], "needs": []})
            # Later checks must not alter any previously validated skill.
            for name, entity_record in outcomes.items():
                directory = bundle / "skills" / name
                if directory.exists() and manifest(directory) != entity_record["files"]:
                    raise ValueError("Bundle entity changed after validation: " + name)
            sources.verify()
            if any(bundle.iterdir()):
                shutil.copytree(bundle, output / "bundle")
            else:
                (output / "bundle").mkdir()
            write_json(output / "bundle/manifest.json", {"build_id": build_id, "entities": record["entities"],
                "files": manifest(bundle), "agent_efficacy": "not_evaluated"})
            adoption_enabled = config["adoption"]["enabled"] and not no_adopt
            if any(r["status"] == "ready" for r in outcomes.values()) and adoption_enabled:
                record["adoption"] = adopt(output, list(outcomes.values()), config, library_root or ROOT / "skills")
            else:
                record["adoption"] = [{"name": n, "status": "not_eligible" if adoption_enabled else "disabled"} for n in outcomes]
            states = [r["status"] for r in record["entities"]]
            record["status"] = ("no_candidates" if not states else "ready" if all(s == "ready" for s in states)
                                else "partial" if "ready" in states else "failed" if "failed" in states
                                else "blocked" if "blocked" in states else "draft")
            if any(a["status"] == "conflict" for a in record.get("adoption", [])):
                record["status"] = "partial"
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        record["status"] = "blocked" if isinstance(exc, BlockedError) else "failed"
        record["errors"].append(redact(exc))
    record["finished_at"] = now()
    record["counts"] = dict(Counter(e["status"] for e in record["entities"]))
    receipts = session.receipts if session else []
    record["model_metrics"] = {"calls_attempted": len(receipts), "usage_fully_reported": bool(receipts) and all(r.get("usage") for r in receipts),
                               "receipts": receipts, "monetary_cost": None}
    usages = [r["usage"] for r in receipts if isinstance(r.get("usage"), dict)]
    usage_keys = {k for u in usages for k, v in u.items() if type(v) is int}
    record["model_metrics"]["reported_totals"] = {k: sum(u.get(k, 0) for u in usages if type(u.get(k, 0)) is int)
                                                   for k in usage_keys} if usages else None
    if plan is not None:
        record["discovery_summary"] = plan["summary"]
        record["candidate_count"] = len(plan["candidates"])
    if sources:
        record["sources"] = sources.index()
        record["source_errors"] = sources.errors
        record["evidence"] = sources.compact_evidence()
        # Preserve reads and new acquisitions made by authors/reviewers for continuation.
        if plan is not None and (output / "plan.json").exists() and record["status"] != "failed":
            document.update(sources=sources.manifest(), evidence=sources.evidence,
                            source_errors=sources.errors, network_requests=sources.acquisition.requests)
            context_hash = hash_object({k: document[k] for k in
                ("config", "sources", "evidence", "source_errors", "specifications", "network_requests")})
            write_json(output / "plan.json", sanitized(document))
            write_json(output / "sources.lock.json", {"source_context_sha256": context_hash})
            record["source_context_sha256"] = context_hash
    successful = record["status"] in ("ready", "planned", "no_candidates")
    record["temporary_workspace"] = str(work) if not successful or keep_debug else None
    write_json(output / "summary.json", sanitized(record))
    if successful and not keep_debug:
        clean_run(state, build_id)
    return {"build_id": build_id, "status": record["status"], "output": str(output),
            "counts": record["counts"], "entities": record["entities"],
            "discovery_summary": record.get("discovery_summary"), "candidate_count": record.get("candidate_count", 0),
            "adoption": record.get("adoption", []), "deferred": record.get("deferred", []), "model_calls": len(receipts), "errors": record["errors"]}
