"""Discover once, build skills independently, verify and adopt ready packages."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import time
import uuid
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

from . import __version__
from creation_pipeline.resources.acquisition import Acquisition
from creation_pipeline.generation.discovery import ROOT, analyze, ordered, specifications, validate_discovery
from creation_pipeline.generation.author import author, review
from creation_pipeline.validation.checks import classify, static_checks
from creation_pipeline.resources.intake import Sources
from creation_pipeline.models import BlockedError, BudgetError, IncompleteError, LocalPathError, ModelCallError, load_config, bound, iterations
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.artifacts.library import adopt
from creation_pipeline.validation.acceptance import certify, require_ready, ACCEPTANCE_VERSION
from creation_pipeline.agent.backend import NativeSession
from creation_pipeline.generation.discovery import reconcile
from creation_pipeline.records import clean_run, digest, has_link, now, read_json, redact, sanitized, write_json, safe_relative


def hash_object(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def candidate_identity(entity, config, sources):
    return {"entity": {k: v for k, v in entity.items() if k not in ("priority", "rationale")},
            "config": {k: v for k, v in config.items() if k != "limits"},
            "sources": sources.manifest(), "specs": specifications()}


def candidate_fingerprint(entity, config, sources):
    return hash_object({**candidate_identity(entity, config, sources), "acceptance_version": ACCEPTANCE_VERSION})


def cache_matches(old, entity, config, sources, prior_implementation):
    identity = candidate_identity(entity, config, sources)
    keys = [hash_object({**identity, "acceptance_version": ACCEPTANCE_VERSION})]
    # Read-only compatibility with earlier V1.1 receipts. Approval and current static checks
    # are still required; an infrastructure code hash is audit data, not content identity.
    if prior_implementation:
        keys.append(hash_object({**identity, "code": prior_implementation}))
    return old.get("fingerprint") in keys


def _restore(document, state, replan=False):
    if document.get("schema_version") != 3:
        raise ValueError("Legacy plan schema: rediscover with the skill-only pipeline")
    config = copy.deepcopy(document["config"])
    config.setdefault("research_access", "known_only")
    current_specs = specifications()
    changed = {p for p in current_specs if current_specs[p] != document["specifications"].get(p)}
    author_only = {"creation_pipeline/generation/prompts/author.md", "creation_pipeline/generation/prompts/review.md"}
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



def _candidate(session, config, entity, bundle, work):
    directory = safe_relative(bundle, "skills/" + entity["name"])
    record = {"name": entity["name"], "kind": "skill", "plan": entity, "status": "failed",
              "checks": [], "repair_rounds": 0, "files": [], "basis": [], "repair_summary": []}
    if entity["readiness"] == "blocked":
        record.update(status="incomplete", error="; ".join(entity["gaps"]))
        return certify(record)
    before_calls, global_limit = len(session.receipts), session.limits["model_calls"]
    cap = min(bound(global_limit), before_calls + session.call_offset + bound(config["limits"]["candidate_calls"]))
    session.limits["model_calls"] = None if cap == float("inf") else cap
    previous_scope = session.call_limit_scope
    session.call_limit_scope = "candidate" if cap < bound(global_limit) else "run"
    previous, feedback, signature, last_delivery = None, [], None, None
    proposals_seen = set()
    try:
        for attempt in iterations(config["limits"]["repair_rounds"]):
            record["repair_rounds"] = attempt
            artifact = author(session, config, entity, directory, feedback, previous)
            previous = artifact
            if artifact.get("candidate_update"):
                update = artifact["candidate_update"]
                if not update.get("reason") or not update.get("evidence"):
                    raise ValueError("Scope adjustment requires reason and evidence")
                session.sources.validate_evidence(update["evidence"])
                record.setdefault("plan_adjustments", []).append(update)
                for key in ("scope", "task", "entrypoint", "construction", "evidence"):
                    if key in update:
                        entity[key] = update[key]
            record.update(basis=artifact["basis"], issues=artifact.get("issues", []),
                          notes=artifact.get("notes", []), additional_candidates=artifact.get("additional_candidates", []))
            proposals = artifact.get("additional_candidates", [])
            if proposals and hash_object(proposals) not in proposals_seen:
                proposals_seen.add(hash_object(proposals))
                changed, mapping = reconcile(session, config, entity, proposals)
                record.setdefault("proposal_decisions", []).append(mapping)
                if changed:
                    feedback = [{"name": "package_scope", "findings": [entity],
                                 "action": "Implement the reconciled common core and modes before review"}]
                    continue
            reports = static_checks(directory, entity["name"])
            delivery_key = hash_object({"files": manifest(directory), "basis": artifact["basis"],
                                        "sources": session.sources.manifest(), "issues": artifact.get("issues", [])})
            if delivery_key == last_delivery:
                record.update(status="incomplete", stopped_reason="Author returned unchanged files and evidence; review not repeated")
                break
            last_delivery = delivery_key
            initial = manifest(bundle)
            if not any(r["status"] == "fail" for r in reports):
                reports.append(review(session, entity, artifact, reports, config))
                if initial != manifest(bundle):
                    reports.append({"name": "artifact_immutability", "status": "fail", "required": True,
                                    "findings": ["Review modified delivered files"]})
                session.sources.verify()
            unresolved = [i["description"] for i in artifact.get("issues", []) if i["blocking"]]
            if unresolved:
                reports.append({"name": "blocking_issues", "status": "fail", "required": True, "findings": unresolved})
            record.update(status=classify(reports), checks=reports,
                          review_context=hash_object({"specs": specifications(), "basis": artifact["basis"],
                                                      "sources": session.sources.manifest()}))
            if record["status"] == "ready":
                break
            feedback = [r for r in reports if r["status"] != "pass"]
            record["repair_summary"].append({"attempt": attempt, "problems": [
                {k: f.get(k) for k in ("location", "problem", "action")}
                if isinstance(f, dict) else str(f)
                for r in feedback for f in r.get("findings", [])]})
            current = hash_object({"files": manifest(directory), "basis": artifact["basis"], "feedback": feedback})
            if current == signature:
                record.update(status="incomplete", stopped_reason="Repeated unchanged content failure")
                break
            signature = current
            if any(r["status"] == "not_run" for r in reports):
                record["status"] = "incomplete"
                # One author opportunity to supply additional evidence; unchanged loop stops above.
        else:
            record["stopped_reason"] = "Explicit development repair limit reached"
    except (ModelCallError, IncompleteError, BlockedError) as exc:
        record.update(status="incomplete", error=redact(exc))
        if isinstance(exc, BudgetError):
            if exc.scope in ("run", "group"):
                record["dispatch_stopped"] = "budget" if exc.scope == "run" else "group_budget"
        elif isinstance(exc, ModelCallError):
            record["dispatch_stopped"] = "backend"
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        record.update(status="failed", error=redact(exc))
        if isinstance(exc, (OSError, KeyError, TypeError, subprocess.SubprocessError)):
            record["dispatch_stopped"] = "pipeline"
    finally:
        session.limits["model_calls"] = global_limit
        session.call_limit_scope = previous_scope
        record["model_calls"] = session.receipts[before_calls:]
        if directory.exists():
            record["files"] = manifest(directory)
    return certify(record)


def _build(config_path=None, state_root=None, *, plan_only=False, keep_debug=False,
          _session_factory=None, notify=lambda message: None,
          library_root=None, no_adopt=False, resume_id=None, rediscover=False, extra_turns=0, _build_id=None,
          _config=None, _queue=None):
    state = Path(state_root or ROOT / ".pipeline").absolute()
    if has_link(state):
        raise ValueError("State root must not contain linked paths")
    build_id = resume_id or _build_id or (time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
    work = safe_relative(state, "runs/" + build_id)
    output = safe_relative(state, "outputs/" + build_id)
    if resume_id and (not (work / "checkpoint.json").is_file()):
        raise ValueError("No resumable checkpoint for this build")
    if _queue and work.exists() and not resume_id:
        marker = work / "workspace.json"
        if (not marker.exists() or read_json(marker) != {"build_id": build_id, "workspace": str(work.resolve())}
                or any(p.name != "workspace.json" for p in work.iterdir())):
            raise ValueError("Allocated child has unrecognized work without a checkpoint")
    work.mkdir(parents=True, exist_ok=bool(resume_id or _queue))
    output.mkdir(parents=True, exist_ok=bool(resume_id or _queue))
    write_json(work / "workspace.json", {"build_id": build_id, "workspace": str(work.resolve())})
    record = {"schema_version": 3, "pipeline_version": __version__, "build_id": build_id,
              "started_at": now(), "status": "failed", "entities": [], "errors": [],
              "agent_efficacy": "not_evaluated_separate_work", "replay": _session_factory is not None}
    implementation = [p for p in sorted((ROOT / "creation_pipeline").rglob("*")) if p.suffix in (".py", ".md")]
    record["implementation_sha256"] = hash_object({p.relative_to(ROOT).as_posix(): digest(p.read_bytes())
                                                  for p in implementation})
    session, sources, plan, config = None, None, None, None
    prior_output = None
    prior_implementation = None
    try:
        if resume_id:
            checkpoint = read_json(work / "checkpoint.json")
            config = checkpoint["config"]
            config.setdefault("research_access", "known_only")
            if "execution" not in config or any(k in config for k in ("checks", "execute_generated_checks")):
                raise ValueError("Legacy checkpoint: start a source/content-review build using existing resources")
            if (output / "summary.json").is_file():
                previous_summary = read_json(output / "summary.json")
                prior_implementation = previous_summary.get("implementation_sha256")
                config["_previous_run_errors"] = previous_summary.get("errors", [])
                history = output / "attempt-history"
                index = len(list(history.glob("*.json"))) + 1
                write_json(history / f"{index:03d}-summary.json", previous_summary)
            if config["model"]["backend"] != "codex_cli":
                raise ValueError("Native resume requires codex_cli")
            if checkpoint["specifications"] != specifications() and not rediscover:
                raise ValueError("Specifications changed; start a new build")
            if checkpoint.get("sources") is not None:
                sources = Sources.__new__(Sources)
                sources.config, sources.limits, sources.cache = config, config["limits"], state / "cache"
                sources.acquisition = Acquisition(config, sources.cache)
                sources.restore(checkpoint["sources"], checkpoint["evidence"], checkpoint["source_errors"])
            if (output / "plan.json").exists() and not rediscover:
                document = read_json(output / "plan.json")
                lock = read_json(output / "sources.lock.json")
                if hash_object({k: document[k] for k in ("config", "sources", "evidence", "source_errors", "specifications", "network_requests")}) != lock["source_context_sha256"]:
                    raise ValueError("Saved plan source context changed; refuse resume")
                config, sources = _restore(document, state)
                plan, prior_output = document["discovery"], output
        else:
            config = copy.deepcopy(_config) if _config is not None else load_config(config_path)
            write_json(work / "checkpoint.json", {"config": {k: v for k, v in config.items() if not k.startswith("_")},
                "sources": None, "evidence": [], "source_errors": [], "specifications": specifications()})
            config["_deadline"] = time.monotonic() + bound(config["limits"]["total_seconds"])
            if _session_factory is None and not _queue:
                notify("Checking selected Agent connection before acquiring resources")
                record["preflight_receipts"] = NativeSession.preflight(config, work, notify)
        if resume_id and _session_factory is None and not _queue:
            record["preflight_receipts"] = NativeSession.preflight(config, work, notify)
        if sources is None:
            notify("Acquiring and snapshotting sources")
            sources = Sources(config, state / "cache")
        if _queue:
            config["limits"]["model_calls"] = _queue["model_calls"]
        if type(extra_turns) is not int or extra_turns < 0 or (extra_turns and not resume_id):
            raise ValueError("extra_turns must be nonnegative and requires resume")
        if extra_turns:
            if config["limits"]["model_calls"] is None:
                raise ValueError("No finite turn budget to extend")
            config["limits"]["model_calls"] += extra_turns
            record["budget_extension"] = {"extra_turns": extra_turns, "new_turn_limit": config["limits"]["model_calls"]}
        write_json(work / "checkpoint.json", {"config": {k: v for k, v in config.items() if not k.startswith("_")},
            "sources": sources.manifest(), "evidence": sources.evidence, "source_errors": sources.errors,
            "specifications": specifications()})
        config.setdefault("_deadline", time.monotonic() + bound(config["limits"]["total_seconds"]))
        if config["model"]["backend"] != "codex_cli":
            raise ValueError("Saved API/Ollama runs are not executable in the Agent-only pipeline")
        session = (_session_factory or NativeSession)(config, sources, copy.deepcopy(config["limits"]), work, keep_debug)
        session.started = time.monotonic() if config["limits"]["total_seconds"] is None else config["_deadline"] - config["limits"]["total_seconds"]
        if resume_id:
            session.started -= sum(r.get("elapsed_seconds", 0) for r in session.receipts)
            config["_deadline"] = session.started + bound(config["limits"]["total_seconds"])
        session.notify = notify
        if _queue:
            session.call_offset = _queue["calls_before"]
            session.started = _queue["started"]
            config["_deadline"] = session.started + bound(config["limits"]["total_seconds"])
            if _queue.get("max_builds") is not None:
                config["_build_allowance"] = _queue["max_builds"]
        if rediscover:
            (work / "discovery-state.json").unlink(missing_ok=True)
            (work / "group-plan.json").unlink(missing_ok=True)
        if plan is None:
            notify("Discovering capabilities and choosing packaging directions")
            plan = analyze(session, config)
        if (work / "group-plan.json").exists() and not rediscover:
            plan = read_json(work / "group-plan.json")
            validate_discovery(plan, config, sources)
        config["_group_plan"] = plan
        config["_approved_plans"] = []
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
            bundle.mkdir(exist_ok=bool(resume_id))
            selected = [e for e in ordered(plan) if e["selected"]]
            reusable = {}
            if prior_output:
                for peer in selected:
                    saved = safe_relative(prior_output, "records/" + peer["name"] + ".json")
                    if not saved.exists():
                        continue
                    old = read_json(saved)
                    if old["status"] != "ready":
                        continue
                    require_ready(old)
                    if manifest(safe_relative(prior_output, "bundle/skills/" + peer["name"])) != old["files"]:
                        raise ValueError("Previously approved package changed: " + peer["name"])
                    old_path = safe_relative(prior_output, "bundle/skills/" + peer["name"])
                    if (cache_matches(old, peer, clean_config, sources, prior_implementation)
                            and all(c["status"] == "pass" for c in static_checks(old_path, peer["name"]))):
                        config["_approved_plans"].append(copy.deepcopy(peer))
                        reusable[peer["name"]] = old
            outcomes = {}
            record["builds_started"] = 0
            while True:
                pending = [e for e in ordered(plan) if e["selected"] and e["name"] not in outcomes]
                if not pending or record["builds_started"] >= min(bound(config["limits"]["max_builds"]), bound(config.get("_build_allowance"))):
                    record["deferred"] = [e["name"] for e in pending]
                    if pending:
                        record["dispatch_stopped"] = "budget"
                    break
                entity = pending[0]
                name = entity["name"]
                fingerprint = candidate_fingerprint(entity, clean_config, sources)
                entity_record = None
                if name in reusable:
                    notify("Reusing approved skill: " + name)
                    old = reusable[name]
                    old_path = safe_relative(prior_output, "bundle/skills/" + name)
                    if old_path.resolve() != (bundle / "skills" / name).resolve():
                        shutil.copytree(old_path, bundle / "skills" / name, dirs_exist_ok=True)
                    entity_record = dict(old, reused_from=prior_output.name, model_calls=[])
                if entity_record is None:
                    notify("Building skill: " + name)
                    record["builds_started"] += 1
                    entity_record = _candidate(session, config, entity, bundle, work)
                entity_record["fingerprint"] = fingerprint
                certify(entity_record)
                outcomes[name] = entity_record
                if entity_record["status"] == "ready" and not any(c["name"] == name for c in config["_approved_plans"]):
                    config["_approved_plans"].append(copy.deepcopy(entity))
                write_json(output / "records" / (name + ".json"), sanitized(entity_record))
                record["entities"].append({"name": name, "kind": "skill", "status": entity_record["status"], "needs": [],
                    **({"reason": entity_record.get("error") or entity_record.get("stopped_reason") or "Content review requires changes; see review record"}
                       if entity_record["status"] != "ready" else {})})
                if entity_record.get("dispatch_stopped"):
                    record["dispatch_stopped"] = entity_record["dispatch_stopped"]
                    record["errors"].append(entity_record["error"])
                    record["deferred"] = [e["name"] for e in ordered(plan) if e["name"] not in outcomes]
                    break

            # Later checks must not alter any previously validated skill.
            for name, entity_record in outcomes.items():
                directory = bundle / "skills" / name
                if directory.exists() and manifest(directory) != entity_record["files"]:
                    raise ValueError("Bundle entity changed after validation: " + name)
            sources.verify()
            # Later supplemental reads do not require rebuilding an unchanged approved package.
            for name, result in outcomes.items():
                result["fingerprint"] = candidate_fingerprint(result["plan"], clean_config, sources)
                write_json(output / "records" / (name + ".json"), sanitized(result))
            if any(bundle.iterdir()):
                existing_bundle = safe_relative(output, "bundle")
                if existing_bundle.exists():
                    if has_link(existing_bundle):
                        raise ValueError("Linked output bundle")
                    shutil.rmtree(existing_bundle)
                shutil.copytree(bundle, output / "bundle")
            else:
                (output / "bundle").mkdir(exist_ok=True)
            write_json(output / "bundle/manifest.json", {"build_id": build_id, "entities": record["entities"],
                "files": manifest(bundle), "agent_efficacy": "not_evaluated"})
            document.update(sources=sources.manifest(), evidence=sources.evidence, source_errors=sources.errors, network_requests=sources.acquisition.requests)
            write_json(output / "plan.json", sanitized(document))
            adoption_enabled = config["adoption"]["enabled"] and not no_adopt
            if any(r["status"] == "ready" for r in outcomes.values()) and adoption_enabled:
                record["adoption"] = adopt(output, list(outcomes.values()), config, library_root or ROOT / "skills")
            else:
                record["adoption"] = [{"name": n, "status": "not_eligible" if adoption_enabled else "disabled"} for n in outcomes]
            states = [r["status"] for r in record["entities"]]
            record["status"] = ("no_candidates" if not states else "ready" if all(s == "ready" for s in states)
                                else "partial" if "ready" in states else "incomplete" if "incomplete" in states else "failed")
            if any(a["status"] == "conflict" for a in record.get("adoption", [])):
                record["status"] = "partial"
            if record.get("deferred") and record["status"] in ("ready", "no_candidates"):
                record["status"] = "partial" if states else "incomplete"
    except KeyboardInterrupt:
        record["status"] = "interrupted"
        record["errors"].append("User interrupted; local workspace and agent session retained")
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        record["status"] = "blocked" if isinstance(exc, BlockedError) else "incomplete" if isinstance(exc, (IncompleteError, BudgetError)) else "failed"
        record["errors"].append(redact(exc))
        if isinstance(exc, BudgetError):
            record["dispatch_stopped"] = "budget" if exc.scope == "run" else "group_budget"
        elif isinstance(exc, ModelCallError):
            record["dispatch_stopped"] = "backend"
        elif not isinstance(exc, (BlockedError, IncompleteError, LocalPathError)):
            record["dispatch_stopped"] = "pipeline"
    record["finished_at"] = now()
    record["counts"] = dict(Counter(e["status"] for e in record["entities"]))
    if (work / "preflight-receipts.json").exists() and not record.get("preflight_receipts"):
        record["preflight_receipts"] = read_json(work / "preflight-receipts.json")
    receipts = session.receipts if session else []
    record["model_metrics"] = {"calls_attempted": len(receipts) + len(record.get("preflight_receipts", [])), "usage_fully_reported": bool(receipts) and all(r.get("usage") for r in receipts),
                               "receipts": receipts, "monetary_cost": None}
    from creation_pipeline.agent.metrics import summarize_usage
    record["model_metrics"].update(summarize_usage(record.get("preflight_receipts", []) + receipts))
    if plan is not None:
        record["accepted_plan_sha256"] = hash_object(plan)
        record["discovery_summary"] = plan["summary"]
        record["candidate_count"] = len(plan["candidates"])
        record["discovery"] = plan
    discovery_state = work / "discovery-state.json"
    if discovery_state.exists():
        record["packaging"] = read_json(discovery_state)
    if sources:
        record["sources"] = sources.index()
        record["source_errors"] = sources.errors
        record["evidence"] = sources.compact_evidence()
        # Preserve reads and new acquisitions made by authors/reviewers for continuation.
        if plan is not None and (output / "plan.json").exists() :
            document.update(discovery=plan, sources=sources.manifest(), evidence=sources.evidence,
                            source_errors=sources.errors, network_requests=sources.acquisition.requests)
            context_hash = hash_object({k: document[k] for k in
                ("config", "sources", "evidence", "source_errors", "specifications", "network_requests")})
            write_json(output / "plan.json", sanitized(document))
            write_json(output / "sources.lock.json", {"source_context_sha256": context_hash})
            record["source_context_sha256"] = context_hash
    record["temporary_workspace"] = str(work)
    write_json(output / "summary.json", sanitized(record))
    from creation_pipeline.retention import archive, register_cache, mark, remove_registered
    try:
        entries = sources.manifest() if sources else []
        cache = register_cache(state, entries)
        archive_path = archive(state, output, record, config, entries)
        mark(state, build_id, last_activity=time.time(), cache=cache, status=record["status"])
        record["archive"] = str(archive_path)
        successful = record["status"] in ("ready", "planned", "no_candidates")
        if successful and not keep_debug and not plan_only:
            clean_run(state, build_id)
            remove_registered(state, "outputs/" + build_id)
            record["temporary_workspace"] = None
        write_json(archive_path / "summary.json", sanitized({k: v for k, v in record.items()
            if k not in ("evidence", "sources", "model_metrics")} | {"model_metrics": {k: v for k, v in record["model_metrics"].items() if k != "receipts"}}))
    except (OSError, ValueError, KeyError) as exc:
        record.setdefault("warnings", []).append("Archive/cleanup incomplete; workspace retained where possible: " + redact(exc))
        write_json(output / "summary.json", sanitized(record))
    return {"build_id": build_id, "status": record["status"], "output": record.get("archive", str(output)),
            "counts": record["counts"], "entities": record["entities"],
            "discovery_summary": record.get("discovery_summary"), "candidate_count": record.get("candidate_count", 0),
            "adoption": record.get("adoption", []), "deferred": record.get("deferred", []),
            "dispatch_stopped": record.get("dispatch_stopped"),
            "builds_started": record.get("builds_started", 0),
            "archive_complete": bool(record.get("archive")),
            "model_metrics": {k: v for k, v in record["model_metrics"].items() if k != "receipts"},
            "model_calls": len(receipts) + len(record.get("preflight_receipts", [])), "errors": record["errors"], "warnings": record.get("warnings", [])}


def _run_group(config_path=None, state_root=None, **kwargs):
    from creation_pipeline.retention import lease, sweep, mark, initialize
    state = Path(state_root or ROOT / ".pipeline").absolute()
    if has_link(state):
        raise ValueError("State root must not contain linked paths")
    state.mkdir(parents=True, exist_ok=True)
    notify = kwargs.get("notify", lambda message: None)
    try:
        initialize(state)
        report = sweep(state) if not kwargs.get("_queue") else {"removed": [], "warnings": []}
    except (OSError, ValueError, KeyError) as exc:
        report = {"removed": [], "warnings": [redact(exc)]}
    if report["removed"] or report["warnings"]:
        notify(f"Retention: {len(report['removed'])} temporary paths removed; {len(report['warnings'])} warnings")
    assigned = kwargs.pop("_build_id", None)
    bid = kwargs.get("resume_id") or assigned or (time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
    with ExitStack() as stack:
        with lease(state, "retention-sweep"):
            stack.enter_context(lease(state, bid))
            mark(state, bid, last_activity=time.time(), **({"queue_id": kwargs["_queue"]["id"]} if kwargs.get("_queue") else {}))
        try:
            return _build(config_path, state, _build_id=bid, **kwargs)
        finally:
            mark(state, bid, last_activity=time.time())


def build(config_path=None, state_root=None, **kwargs):
    state = Path(state_root or ROOT / ".pipeline").absolute()
    resume_id = kwargs.get("resume_id")
    config = load_config(config_path) if config_path is not None else None
    if (config and "resource_groups" in config) or (resume_id and safe_relative(state, "queues/" + resume_id + ".json").exists()):
        from creation_pipeline.groups import run
        return run(config, state, **kwargs)
    return _run_group(config_path, state, _config=config, **kwargs)
