"""Ordered resource groups using flat, independently recoverable child builds."""
from __future__ import annotations

import copy
from contextlib import ExitStack
import time
import uuid
from pathlib import Path

from creation_pipeline.agent.backend import NativeSession
from creation_pipeline.agent.metrics import summarize_usage
from creation_pipeline.artifacts.package import archive_packages
from creation_pipeline.generation.discovery import specifications
from creation_pipeline.models import BudgetError, bound
from creation_pipeline.records import has_link, lease, now, read_json, redact, safe_relative, sanitized, write_json
from creation_pipeline.retention import initialize, mark, sweep
from creation_pipeline.validation.acceptance import require_ready


def _verify_completed(result):
    marker = Path(result["output"]) / "complete.json"
    if not marker.exists() or read_json(marker).get("build_id") != result["build_id"]:
        raise ValueError("Group archive has no valid completion marker")
    summary, packages = archive_packages(result["output"])
    for record, _ in packages:
        if record["status"] == "ready":
            require_ready(record)
    expected = {e["name"] for e in summary.get("entities", []) if e["status"] == "ready"}
    if expected != {r["name"] for r, _ in packages if r["status"] == "ready"}:
        raise ValueError("Completed group is missing an approved package")
    if summary["build_id"] != result["build_id"] or summary["status"] != result["status"]:
        raise ValueError("Completed group differs from its retained record")


def _finished(group, plan_only):
    result = group.get("result") or {}
    allowed = {"ready", "no_candidates", "planned"} if plan_only else {"ready", "no_candidates"}
    return bool(result.get("archive_complete") and result.get("status") in allowed
                and group.get("status") == result.get("status"))


def _metrics(queue):
    probes = queue.get("preflight_receipts", [])
    children = [g["result"] for g in queue["groups"] if g.get("result")]
    totals = dict(summarize_usage(probes).get("reported_totals") or {})
    unknown = summarize_usage(probes)["usage_unknown_calls"]
    for child in children:
        metrics = child.get("model_metrics", {})
        for key, value in (metrics.get("reported_totals") or {}).items():
            totals[key] = totals.get(key, 0) + value
        unknown += metrics.get("usage_unknown_calls", child.get("model_calls", 0))
    calls = len(probes) + sum(r.get("model_calls", 0) for r in children)
    return {"calls_attempted": calls, "reported_totals": totals or None, "usage_unknown_calls": unknown,
            "usage_fully_reported": calls > 0 and not unknown, "monetary_cost": None,
            "usage_note": "CLI-reported observations across groups and preflights; not a billing estimate"}


def run(config, state, *, resume_id=None, plan_only=False, keep_debug=False, _session_factory=None,
        notify=lambda message: None, library_root=None, no_adopt=False, rediscover=False, extra_turns=0):
    state = Path(state).absolute()
    if has_link(state):
        raise ValueError("State root must not contain linked paths")
    state.mkdir(parents=True, exist_ok=True)
    qid = resume_id or "q-" + time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    path = safe_relative(state, "queues/" + qid + ".json")
    initialize(state)
    cleanup = sweep(state)
    if cleanup["warnings"]:
        notify("Retention warnings: " + str(cleanup["warnings"]))
    with ExitStack() as ownership:
        with lease(state, "retention-sweep"):
            ownership.enter_context(lease(state, qid))
            mark(state, qid, kind="queue", last_activity=time.time())
        return _execute(config, state, qid, path, resume_id=resume_id, plan_only=plan_only,
            keep_debug=keep_debug, _session_factory=_session_factory, notify=notify,
            library_root=library_root, no_adopt=no_adopt, rediscover=rediscover, extra_turns=extra_turns)


def _execute(config, state, qid, path, *, resume_id, plan_only, keep_debug, _session_factory,
             notify, library_root, no_adopt, rediscover, extra_turns):
    from creation_pipeline.pipeline import _run_group, hash_object
    started = time.monotonic()
    previous_elapsed = 0
    queue = None
    active_group = None
    try:
        if resume_id:
            saved = read_json(path)
            if saved["config_sha256"] != hash_object(saved["config"]) or saved["specifications"] != specifications():
                raise ValueError("Queue configuration/specifications changed; start a new queue")
            config = saved["config"]
            if saved["queue_id"] != qid or [g["id"] for g in saved["groups"]] != [g["id"] for g in config["resource_groups"]]:
                raise ValueError("Queue group identities changed")
            for group in saved["groups"]:
                if group.get("result") and group.get("build_id") != group["result"]["build_id"]:
                    raise ValueError("Queue child identity differs from its result")
            children = [g["build_id"] for g in saved["groups"] if g.get("build_id")]
            if len(set(children)) != len(children) or qid in children:
                raise ValueError("Queue child build identities must be distinct")
            if rediscover:
                raise ValueError("Rediscovery of a grouped run requires a new queue; retained approvals are unchanged")
            queue = saved
        else:
            if extra_turns or rediscover:
                raise ValueError("extra_turns/rediscover require a saved build")
            queue = {"queue_id": qid, "config": config, "config_sha256": hash_object(config),
                     "specifications": specifications(), "started_at": now(), "elapsed_seconds": 0,
                     "groups": [{"id": g["id"], "status": "pending"} for g in config["resource_groups"]],
                     "delivery": {"library_root": str(Path(library_root).absolute()) if library_root else None,
                                  "no_adopt": no_adopt}, "preflight_receipts": []}
        if type(extra_turns) is not int or extra_turns < 0:
            raise ValueError("extra_turns must be nonnegative")
        if extra_turns:
            if config["limits"]["model_calls"] is None:
                raise ValueError("No finite turn budget to extend")
            config["limits"]["model_calls"] += extra_turns
            queue["config_sha256"] = hash_object(config)
        previous_elapsed = queue["elapsed_seconds"]
        delivery = queue["delivery"]
        if library_root and str(Path(library_root).absolute()) != delivery["library_root"]:
            raise ValueError("Use the queue's original library directory")
        library_root = delivery["library_root"]
        no_adopt = no_adopt or delivery["no_adopt"]
        queue.update(status="running", reason=None)
        write_json(path, sanitized(queue))
        origin = started - queue["elapsed_seconds"]
        def check_budget():
            if _metrics(queue)["calls_attempted"] >= bound(config["limits"]["model_calls"]):
                raise BudgetError("Queue Agent turn budget exhausted")
            if time.monotonic() - origin >= bound(config["limits"]["total_seconds"]):
                raise BudgetError("Queue total time budget exhausted")
        needs_work = any(not _finished(g, plan_only) for g in queue["groups"])
        if needs_work:
            check_budget()
        work = safe_relative(state, "runs/" + qid)
        work.mkdir(parents=True, exist_ok=True)
        write_json(work / "workspace.json", {"build_id": qid, "workspace": str(work.resolve())})
        if _session_factory is None and needs_work:
            notify("Checking selected Agent connection for resource-group queue")
            try:
                queue["preflight_receipts"].extend(NativeSession.preflight({**config, "_deadline": origin + bound(config["limits"]["total_seconds"])}, work, notify))
            except BaseException:
                receipt = work / "preflight-receipts.json"
                if receipt.exists():
                    queue["preflight_receipts"].extend(read_json(receipt))
                raise
            write_json(path, sanitized(queue))
        builds_started = 0
        for definition, group in zip(config["resource_groups"], queue["groups"]):
            previous = group.get("result")
            if _finished(group, plan_only):
                _verify_completed(previous)
                continue
            check_budget()
            if not plan_only and builds_started >= bound(config["limits"]["max_builds"]):
                raise BudgetError("Queue candidate-build budget exhausted for this invocation")
            bid = group.setdefault("build_id", time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
            group["status"] = "active"
            active_group = group
            write_json(path, sanitized(queue))
            checkpoint = safe_relative(state, "runs/" + bid + "/checkpoint.json")
            if previous and not checkpoint.exists():
                raise ValueError("No retained checkpoint for child " + bid + "; use archived material in a new queue")
            base = {k: copy.deepcopy(v) for k, v in config.items() if k != "resource_groups"}
            base["sources"] = definition["sources"]
            if checkpoint.exists():
                child = read_json(checkpoint)["config"]
                if {k: v for k, v in child.items() if k != "limits"} != {k: v for k, v in base.items() if k != "limits"}:
                    raise ValueError("Child configuration differs from its resource group")
            allowance = {"id": qid, "started": origin,
                         "calls_before": _metrics(queue)["calls_attempted"] - (previous or {}).get("model_calls", 0),
                         "max_builds": None if config["limits"]["max_builds"] is None else config["limits"]["max_builds"] - builds_started,
                         "model_calls": config["limits"]["model_calls"]}
            notify("Resource group: " + group["id"])
            result = _run_group(state_root=state, _config=base, _build_id=bid,
                resume_id=bid if checkpoint.exists() else None, plan_only=plan_only, keep_debug=keep_debug,
                _queue=allowance, _session_factory=_session_factory, notify=notify,
                library_root=library_root, no_adopt=no_adopt)
            group.update(status=result["status"], result=result)
            group.pop("reason", None)
            active_group = None
            queue["elapsed_seconds"] = previous_elapsed + time.monotonic() - started
            builds_started += result.get("builds_started", 0)
            write_json(path, sanitized(queue))
            if result["status"] == "interrupted":
                queue.update(status="interrupted", reason="Active group interrupted; later groups remain pending")
                break
            if result.get("dispatch_stopped") in ("budget", "backend", "pipeline") or not result.get("archive_complete"):
                detail = (result.get("errors") or result.get("warnings") or ["See the child build record"])[0]
                queue.update(status="incomplete", reason="Group dispatch stopped: " + str(result.get("dispatch_stopped") or "archive") + "; " + detail)
                break
        else:
            successful = {"ready", "no_candidates", "planned"} if plan_only else {"ready", "no_candidates"}
            queue["status"] = "planned" if plan_only and all(g["status"] in successful for g in queue["groups"]) else (
                "ready" if all(g["status"] in successful for g in queue["groups"]) else "partial")
    except KeyboardInterrupt:
        if queue is None:
            raise
        if active_group is not None:
            active_group.update(status="interrupted", reason="Queue interrupted before child result was saved")
        queue.update(status="interrupted", reason="Queue interrupted; retained child IDs identify recovery work")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        if queue is None:
            raise
        if active_group is not None:
            active_group.update(status="incomplete", reason=redact(exc))
        queue.update(status="incomplete", reason=redact(exc))
    finally:
        if queue is not None:
            queue["elapsed_seconds"] = previous_elapsed + time.monotonic() - started
            queue["model_metrics"] = _metrics(queue)
            queue["updated_at"] = now()
            write_json(path, sanitized(queue))
        mark(state, qid, kind="queue", last_activity=time.time(), status=queue.get("status") if queue else "failed")
    return {"build_id": qid, "status": queue["status"], "output": str(path), "groups": queue["groups"],
            "model_calls": queue["model_metrics"]["calls_attempted"], "model_metrics": queue["model_metrics"],
            "errors": [queue["reason"]] if queue.get("reason") else []}
