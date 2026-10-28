"""Versioned delivery identities and fail-closed qualification (integration v1).

Author receipts are not delivery approvals. Runtime observations never change the
frozen inputs; a changed input creates a different revision.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from creation_pipeline.records import digest, safe_relative

PROTOCOL = 1
EXECUTION_STATES = {"not_run", "runtime_blocked", "build_failed", "execution_failed", "passed"}
HOST_STATES = {"not_checked", "available", "unavailable", "not_applicable"}


def fingerprint(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


def versioned(payload, version=1):
    if type(version) is not int or version < 1:
        raise ValueError("Contract version must be a positive integer")
    return {"version": version, "payload": copy.deepcopy(payload), "sha256": fingerprint(payload)}


def source_identity(entries):
    return sorted([{k: copy.deepcopy(e[k]) for k in
                   ("id", "inventory", "resolved_ref", "url", "repo", "license", "snapshot_id", "upstream", "carrier_repository") if k in e}
                   for e in entries], key=lambda e: e["id"])


def requirement(proposal, entries, review):
    """Check concrete citations, with semantic confirmation by independent review."""
    unknown = {"status": "unknown", "reason": "No independently reviewed execution requirement", "citations": []}
    if proposal is None:
        return unknown
    if not isinstance(proposal, dict) or proposal.get("status") not in {"required", "not_required", "unknown"}:
        return dict(unknown, reason="Invalid execution requirement")
    if proposal["status"] == "unknown":
        return dict(unknown, reason=proposal.get("reason") or unknown["reason"])
    try:
        if not isinstance(proposal.get("reason"), str) or not proposal["reason"].strip() or not proposal.get("citations"):
            raise ValueError("Requirement needs a reason and exact source citations")
        by_id = {e["id"]: e for e in entries}
        for citation in proposal["citations"]:
            source_id = citation.get("source_id")
            if source_id not in by_id:
                # An evidence locator (e1) is not a source id; say so instead of
                # failing with a bare KeyError that hides the fix (run 22).
                raise ValueError("Requirement cites unknown source id %r; citations use the "
                                 "registered source ids %s, not evidence locators"
                                 % (source_id, sorted(by_id)))
            entry = by_id[source_id]
            if citation["path"] not in {f["path"] for f in entry["inventory"]}:
                raise ValueError("Requirement cites an unregistered file")
            root = Path(entry["path"])
            path = root if root.is_file() else safe_relative(root, citation["path"])
            quote = citation["quote"]
            if not isinstance(quote, str) or not quote.strip() or quote not in path.read_text(encoding="utf-8"):
                raise ValueError("Requirement quotation does not match source")
        if review.get("status") != "pass" or review.get("requirement_assessment") != "confirmed":
            raise ValueError("Execution requirement not confirmed by independent review")
        return copy.deepcopy(proposal)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        return dict(unknown, reason=str(exc))


def inputs_for(record, sources, requirement_value, *, bindings=None, environment=None, acceptance=None):
    return {"candidate": record["plan"], "files": record["files"], "sources": source_identity(sources),
            "requirement": requirement_value, "bindings": versioned(bindings),
            "environment": versioned(environment),
            "acceptance": versioned(acceptance if acceptance is not None else record.get("test_definitions", {}))}


def qualify(delivery, *, runtime_root=None, runtime_ref=None, frozen_directory=None, freeze_sha256=None, executor=None):
    """No stage-one path can fabricate Docker execution approval."""
    if delivery.get("protocol") != PROTOCOL:
        return False, "Unsupported delivery protocol"
    if delivery.get("mode") not in {"normal", "draft"}:
        return False, "Invalid delivery mode"
    if delivery.get("execution", {}).get("status") not in EXECUTION_STATES or delivery.get("host", {}).get("status") not in HOST_STATES:
        return False, "Invalid execution or host observation"
    inputs = delivery["inputs"]
    if delivery["revision_id"] != "rev-" + fingerprint(inputs):
        return False, "Frozen delivery inputs changed"
    if delivery.get("fingerprints") != {k: fingerprint(inputs[k]) for k in ("files", "sources", "bindings", "environment", "acceptance")}:
        return False, "Delivery fingerprints changed"
    for name in ("bindings", "environment", "acceptance"):
        contract = inputs[name]
        if type(contract["version"]) is not int or contract["version"] < 1 or contract["sha256"] != fingerprint(contract["payload"]):
            return False, "Invalid " + name + " contract"
    if delivery["mode"] == "draft":
        return False, "Explicit draft has no formal delivery qualification"
    if delivery["content"]["status"] != "passed":
        return False, "Content review has not passed"
    if inputs["requirement"]["status"] == "not_required":
        return True, "Reviewed source-supported no-execution delivery"
    if inputs["requirement"]["status"] == "unknown":
        return False, "Execution requirement is unresolved"
    if inputs['requirement']['status'] != 'required' or not all((runtime_root, runtime_ref, frozen_directory, freeze_sha256)):
        return False, 'Current bound Docker business evidence is required'
    try:
        from creation_pipeline.runtime.service import verify_attempt
        from creation_pipeline.runtime.execution import evidence
        from creation_pipeline.runtime.local import LocalExecutor
        from creation_pipeline.runtime.strict import reports_pass
        from creation_pipeline.records import read_json
        verified = verify_attempt(runtime_root, runtime_ref, delivery, freeze_sha256)
        if verified['status'] != 'execution_passed' or runtime_ref.get('content_revoked'):
            return False, 'Execution has not passed or content approval was revoked'
        attempt = safe_relative(Path(runtime_root), runtime_ref['path'])
        request = runtime_request(delivery, frozen_directory, freeze_sha256, attempt)
        current = evidence(executor or LocalExecutor(), request, read_json(attempt / 'receipt.json'), attempt / 'execution')
        if not reports_pass({delivery['candidate_id']: current}, 1):
            return False, 'Current acceptance verification failed'
        return True, 'Content review and current Docker business evidence passed'
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return False, str(exc)


def finalize(record, sources, proposal=None, *, draft=False):
    review = next((c for c in record.get("checks", []) if c["name"] == "content_review"), {})
    req = requirement(proposal, sources, review)
    content = ("passed" if record["status"] == "ready" and review.get("status") == "pass" else
               "failed" if record["status"] == "failed" else "not_reviewed")
    inputs = inputs_for(record, sources, req)
    delivery = {"protocol": PROTOCOL, "candidate_id": "candidate-" + fingerprint({"name": record["name"]}),
                "revision_id": "rev-" + fingerprint(inputs), "mode": "draft" if draft else "normal",
                "inputs": inputs, "content": {"status": content},
                "fingerprints": {k: fingerprint(inputs[k]) for k in ("files", "sources", "bindings", "environment", "acceptance")},
                "execution": {"status": "not_run", "attempts": [], "reason": "Execution evidence is recorded separately after final freeze"},
                "host": {"status": "not_applicable" if req["status"] == "not_required" else "not_checked", "observed_at": None},
                "evidence": []}
    accepted, reason = qualify(delivery)
    delivery["qualification"] = {"accepted": accepted, "reason": reason}
    record["delivery"] = delivery
    record["content_status"] = content
    record["status"] = ("ready" if accepted else "draft" if draft else
                        record["status"] if record["status"] != "ready" else
                        "blocked" if req["status"] == "unknown" else "not_run")
    return delivery


def runtime_request(delivery, frozen_directory, freeze_sha256, attempt_directory):
    """Bind a future executor request to every relevant immutable input."""
    from creation_pipeline.runtime.interface import RuntimeRequest
    from creation_pipeline.artifacts.evidence import verify
    from creation_pipeline.records import has_link
    frozen_directory, attempt_directory = Path(frozen_directory).absolute(), Path(attempt_directory).absolute()
    if (has_link(attempt_directory) or attempt_directory.resolve().is_relative_to(frozen_directory.resolve())
            or frozen_directory.resolve().is_relative_to(attempt_directory.resolve())):
        raise ValueError("Dynamic attempts must be outside the final frozen input tree")
    if verify(frozen_directory, freeze_sha256)["delivery"] != delivery:
        raise ValueError("Runtime request differs from durable frozen inputs")
    inputs = delivery["inputs"]
    if delivery["revision_id"] != "rev-" + fingerprint(inputs):
        raise ValueError("Cannot execute changed frozen inputs")
    return RuntimeRequest(delivery["candidate_id"], delivery["revision_id"], fingerprint(inputs["files"]),
                          fingerprint(inputs["sources"]), fingerprint(inputs["bindings"]),
                          fingerprint(inputs["environment"]), fingerprint(inputs["acceptance"]),
                          str(frozen_directory), freeze_sha256, str(attempt_directory))
