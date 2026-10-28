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
from creation_pipeline.resources.acquisition import Acquisition
from creation_pipeline.generation.discovery import ROOT, analyze, ordered, specifications, validate_discovery
from creation_pipeline.generation.author import author, review
from creation_pipeline.validation.checks import classify, run_checks, static_checks
from creation_pipeline.resources.intake import Sources
from creation_pipeline.models import BlockedError, BudgetError, IncompleteError, ModelCallError, load_config, bound, iterations
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.artifacts.library import adopt
from creation_pipeline.schemas import CANDIDATES
from creation_pipeline.agent.backend import NativeSession
from creation_pipeline.generation.discovery import normalize
from creation_pipeline.records import clean_run, digest, has_link, now, read_json, redact, sanitized, write_json, safe_relative
from creation_pipeline.contracts import finalize
from creation_pipeline.artifacts.evidence import seal, verify as verify_evidence


def hash_object(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def _restore(document, state, replan=False):
    if document.get("schema_version") != 3:
        raise ValueError("Legacy plan schema: rediscover with the skill-only pipeline")
    config = copy.deepcopy(document["config"])
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



def _agent_reports(session, directory):
    ledger = session.work / "agent-checks.jsonl"
    if not ledger.exists():
        return []
    current = manifest(directory)
    reports = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        report = json.loads(line)
        if Path(report["package"]).resolve() == directory.resolve() and report["files"] == current:
            reports.append(report)
    return reports


def runtime_spec_for(config, name):
    """Per-candidate runtime preparation settings with the shared defaults underneath.

    ``runtime_defaults`` exists so a normal creation can fix provider options before
    discovery names the candidate. Per-candidate keys win; nested maps are merged one
    level so one option cannot silently erase the rest.
    """
    merged = copy.deepcopy(config.get("runtime_defaults") or {})
    override = config.get("runtime", {}).get(name) or {}
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **copy.deepcopy(value)}
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def runtime_gate_stops(config, runtime_receipt):
    """True when this batch forbids continuing past a failed Docker stage.

    The gate covers the runtime stage only: it stops before any contract
    correction or second build, and leaves author-phase repair rounds alone.
    """
    return bool(config.get("execution", {}).get("stop_on_runtime_failure")
                and runtime_receipt and runtime_receipt.get("status") in ("build_failed", "execution_failed"))


def _candidate(session, config, entity, bundle, work, allow_generated, initial_feedback=None):
    directory = safe_relative(bundle, "skills/" + entity["name"])
    record = {"name": entity["name"], "kind": entity["kind"], "plan": entity, "status": "failed",
              "checks": [], "repair_rounds": 0, "files": [], "repair_history": []}
    if entity["readiness"] == "blocked":
        record.update(status="blocked", error="; ".join(entity["gaps"]))
        return record
    before_calls, global_limit = len(session.receipts), session.limits["model_calls"]
    candidate_limit = min(bound(global_limit), config.get('_candidate_start', before_calls) + bound(config["limits"]["candidate_calls"]))
    session.limits["model_calls"] = None if candidate_limit == float("inf") else candidate_limit
    previous, feedback, signature = None, initial_feedback or [], None
    failed_oracles = {}
    scoped = copy.deepcopy(config)
    scoped["execute_generated_checks"] = allow_generated
    scoped["checks"] = [t for t in config["checks"] if t.get("candidate") == entity["name"]]
    try:
        for attempt in iterations(config["limits"]["repair_rounds"]):
            record["repair_rounds"] = attempt
            try:
                scoped["_previous_issues"] = previous.get("issues", []) if previous else []
                artifact = author(session, scoped, entity, directory, feedback, previous)
                previous = artifact
                if artifact.get("candidate_update"):
                    update = artifact["candidate_update"]
                    if not update.get("reason") or not update.get("evidence"):
                        raise ValueError("Scope adjustments need reason and source evidence")
                    session.sources.validate_evidence(update["evidence"])
                    record.setdefault("plan_adjustments", []).append({"before": copy.deepcopy(entity), "update": update})
                    for key in ("scope", "task", "entrypoint", "construction", "evidence"):
                        if key in update:
                            entity[key] = update[key]
                record.update(
                    runtime_requirement=artifact.get("runtime_requirement"),
                    entry_declaration=artifact.get("entry"),
                    test_definitions={"configured": scoped["checks"], "generated": artifact["tests"]},
                    issues=artifact.get("issues", []), notes=artifact.get("notes", []),
                    additional_candidates=artifact.get("additional_candidates", []),
                    file_purposes=[{"path": f["path"], "purpose": f["purpose"]} for f in artifact["files"]])
                write_json(work / entity["name"] / "authored-metadata.json", sanitized({k: record[k] for k in
                    ("test_definitions", "issues", "notes", "file_purposes", "entry_declaration")}))
                reports = static_checks(directory, entity["name"], bundle=bundle)
                initial = manifest(bundle)
                if not any(r["status"] == "fail" for r in reports):
                    scoped["_oracle_changes"] = []
                    pre_review = review(session, entity, artifact, reports, scoped)
                    if pre_review:
                        reports.append(pre_review)
                    if pre_review is None or pre_review["status"] == "pass":
                        reports += run_checks(scoped, artifact, directory, session.sources,
                                              work / entity["name"] / f"attempt-{attempt}-{uuid.uuid4().hex[:8]}", allow_generated,
                                              prior=_agent_reports(session, directory))
                    if initial != manifest(bundle):
                        reports.append({"name": "artifact_immutability", "status": "fail", "required": True,
                                        "findings": ["Execution modified bundle files"]})
                    session.sources.verify()
                    proposed_tests = {t["name"]: t for t in artifact["tests"]}
                    scoped["_oracle_changes"] = [{"name": n, "previous": old, "proposed": proposed_tests.get(n)}
                        for n, old in failed_oracles.items() if n not in proposed_tests or old != {
                            k: proposed_tests[n].get(k) for k in ("expected_exit", "stdout_contains", "json_equals", "artifacts")}]
                    record["checks"] = reports
                    if any(r["status"] == "fail" for r in reports) or scoped["_oracle_changes"]:
                        # A second review is only worth a model call when new evidence
                        # appeared after the first one (checks ran, immutability failed).
                        # When the first review itself failed, re-reviewing the same
                        # state adds nothing and used to double the cost of every
                        # author repair cycle (run 25 spent its whole budget that way).
                        fresh_evidence = (pre_review is None or pre_review.get("status") == "pass"
                                          or len(_agent_reports(session, directory)) > 0)
                        if fresh_evidence:
                            final_review = review(session, entity, artifact, reports, scoped)
                            seen = {r.get("verification_id") for r in reports if r.get("verification_id")}
                            reports += [r for r in _agent_reports(session, directory) if r.get("verification_id") not in seen]
                            reports = [r for r in reports if r["name"] != "content_review"] + [final_review]
                        else:
                            final_review = pre_review
                        if final_review["status"] == "pass":
                            for report in reports:
                                if report.get("possible_environment_gap") and report["name"] in final_review.get("execution_gaps", []):
                                    report.update(status="not_run", required=False, unverified=True)
                                    report["findings"].append("Review confirmed an external prerequisite gap; execution remains unverified")
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
                oracle_review = next((r for r in reports if r["name"] == "content_review"), {})
                verified_correction = bool(oracle_review.get("status") == "pass"
                    and oracle_review.get("oracle_changes_verified"))
                if changed and verified_correction:
                    reports.append({"name": "source_backed_oracle_correction", "status": "pass", "required": False,
                                    "findings": oracle_review["findings"], "changed_checks": changed})
                if changed and not verified_correction:
                    reports.append({"name": "changed_failed_oracles", "status": "not_run", "required": True,
                        "findings": ["Previously failed checks removed/expected results changed; requires independent oracle review: " + ", ".join(changed)]})
                record.update(status=classify(reports), checks=reports,
                    test_definitions={"configured": scoped["checks"], "generated": artifact["tests"]},
                    entry_declaration=artifact.get("entry"),
                    issues=issues, notes=artifact.get("notes", []), file_purposes=[{"path": f["path"], "purpose": f["purpose"]} for f in artifact["files"]])
                # Reviewer-requested checks are declarations too: disabled host
                # execution must not silently drop them from the frozen contract.
                reviewed = {}
                for report in reports:
                    if report.get('origin') == 'review_agent' and report.get('definition'):
                        test = report['definition']
                        if test['name'] in reviewed and reviewed[test['name']] != test:
                            raise ValueError('Reviewer check name has conflicting definitions')
                        reviewed[test['name']] = test
                if reviewed:
                    record['test_definitions']['reviewed'] = list(reviewed.values())
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
                    record.update(status="incomplete" if isinstance(exc, BudgetError) else "failed", error=redact(exc), stopped_reason="Model execution stopped; no file-repair retry")
                    break
                if isinstance(exc, BlockedError):
                    record.update(status="blocked", error=redact(exc))
                    break
                feedback = [{"name": "author_or_validation", "status": "fail", "required": True, "findings": [redact(exc)]}]
                record.update(status="failed", checks=feedback, error=redact(exc))
            current = hash_object({"issues": [{"name": r.get("name"), "status": r.get("status"), "findings": r.get("findings")} for r in feedback],
                                   "files": manifest(directory) if directory.exists() else []})
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
          execute_generated=False, _session_factory=None, notify=lambda message: None, feedback=None,
          library_root=None, no_adopt=False, resume_id=None, rediscover=False, extra_turns=0, draft_only=False):
    state = Path(state_root or ROOT / ".pipeline").absolute()
    if has_link(state):
        raise ValueError("State root must not contain linked paths")
    build_id = resume_id or (time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
    work = safe_relative(state, "runs/" + build_id)
    output = safe_relative(state, "outputs/" + build_id)
    if resume_id and (not (work / "checkpoint.json").is_file()):
        raise ValueError("No resumable checkpoint for this build")
    work.mkdir(parents=True, exist_ok=bool(resume_id))
    output.mkdir(parents=True, exist_ok=bool(resume_id))
    write_json(work / "workspace.json", {"build_id": build_id, "workspace": str(work.resolve())})
    record = {"schema_version": 3, "pipeline_version": __version__, "build_id": build_id,
              "started_at": now(), "status": "failed", "entities": [], "errors": [],
              "agent_efficacy": "not_evaluated_separate_work", "replay": _session_factory is not None}
    implementation = [p for p in sorted((ROOT / "creation_pipeline").rglob("*")) if p.suffix in (".py", ".md")]
    record["implementation_sha256"] = hash_object({p.relative_to(ROOT).as_posix(): digest(p.read_bytes())
                                                  for p in implementation})
    session, sources, plan, config = None, None, None, None
    prior_output = None
    try:
        if resume_id:
            checkpoint = read_json(work / "checkpoint.json")
            config = checkpoint["config"]
            if "execution" not in config:
                raise ValueError("Legacy checkpoint: start a v5 build and reuse cached resources; old session rules cannot be resumed safely")
            if (output / "summary.json").is_file():
                previous_summary = read_json(output / "summary.json")
                config["_previous_run_errors"] = previous_summary.get("errors", [])
                history = output / "attempt-history"
                index = len(list(history.glob("*.json"))) + 1
                write_json(history / f"{index:03d}-summary.json", previous_summary)
            if config["model"]["backend"] != "codex_cli":
                raise ValueError("Native resume requires codex_cli")
            if checkpoint["specifications"] != specifications() and not rediscover:
                raise ValueError("Specifications changed; start a new build")
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
        elif plan_path:
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
            config["_deadline"] = time.monotonic() + bound(config["limits"]["total_seconds"])
            notify("Acquiring and snapshotting sources")
            sources = Sources(config, state / "cache")
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
        if config["model"]["backend"] not in ("codex_cli", "deepseek_api"):
            raise ValueError("Saved API/Ollama runs are not executable in the Agent-only pipeline")
        config["draft_only"] = draft_only or config.get("draft_only", False)
        config['_docker_checks'] = True
        config["execute_generated_checks"] = False  # native checks are mapped to Docker, never run on the host
        session = (_session_factory or NativeSession)(config, sources, copy.deepcopy(config["limits"]), work, keep_debug)
        # Resumed sessions restore earlier receipts. Every per-build number below
        # (budget, metrics, summary) must ignore those or a continuation looks
        # like it spent the whole previous build's model calls again.
        build_call_start = len(session.receipts)
        session.started = time.monotonic() if config["limits"]["total_seconds"] is None else config["_deadline"] - config["limits"]["total_seconds"]
        if resume_id:
            session.started -= sum(r.get("elapsed_seconds", 0) for r in session.receipts)
            config["_deadline"] = session.started + bound(config["limits"]["total_seconds"])
        session.notify = notify
        if feedback is not None:
            if plan is None:
                raise ValueError("Revision requires --plan")
            context = {"previous_discovery": plan, "feedback": feedback, "sources": sources.index(),
                       "read_evidence": sources.compact_evidence(), "user_guidance": config["prompt"],
                       "constraints": config["constraints"], "user_notes": config["notes"]}
            revised = session.stage((ROOT / "creation_pipeline/generation/prompts/revise.md").read_text(encoding="utf-8"), context,
                                    schema=CANDIDATES)
            plan = validate_discovery(normalize(revised), config, sources)
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
            bundle.mkdir(exist_ok=bool(resume_id))
            selected = [e for e in ordered(plan) if e["selected"]]
            roots = selected[:config["limits"]["max_builds"]]
            record["deferred"] = [e["name"] for e in selected[len(roots):]]
            outcomes = {}
            for entity in roots:
                config['_candidate_start'] = len(session.receipts)
                name = entity["name"]
                notify("Building skill: " + name)
                fingerprint = hash_object({"entity": entity, "config": clean_config, "sources": sources.manifest(),
                                           "specs": specifications(), "code": record["implementation_sha256"]})
                entity_record = None
                continuation_feedback, continuation_tests = None, None
                if prior_output and (prior_output / "records" / (name + ".json")).exists():
                    old = read_json(prior_output / "records" / (name + ".json"))
                    old_path = safe_relative(prior_output, "bundle/skills/" + name)
                    if old.get("fingerprint") == fingerprint and old["status"] == "ready" and manifest(old_path) == old["files"]:
                        ref = old["durable_evidence"]
                        verify_evidence(safe_relative(prior_output, ref["path"]), ref["freeze_sha256"])
                        if old_path.resolve() != (bundle / "skills" / name).resolve():
                            shutil.copytree(old_path, bundle / "skills" / name, dirs_exist_ok=True)
                        entity_record = dict(old, reused_from=prior_output.name, model_calls=[])
                    elif (old.get('content_status') == 'passed' and old.get('status') in {'blocked', 'not_run'}
                          and manifest(old_path) == old['files'] and old.get('plan') == entity
                          and [(s['id'], s['inventory']) for s in old.get('delivery', {}).get('inputs', {}).get('sources', [])]
                              == [(s['id'], s['inventory']) for s in sorted(sources.manifest(), key=lambda s: s['id'])]):
                        # Explicit saved-plan continuation: reuse reviewed bytes, not old runtime approval.
                        ref = old['durable_evidence']
                        verify_evidence(safe_relative(prior_output, ref['path']), ref['freeze_sha256'])
                        if old_path.resolve() != (bundle / 'skills' / name).resolve():
                            shutil.copytree(old_path, bundle / 'skills' / name, dirs_exist_ok=True)
                        entity_record = copy.deepcopy(old)
                        entity_record.update(status='ready', reused_from=prior_output.name, model_calls=[])
                        write_json(work / 'deliveries' / (name + '-metadata.json'), {
                            'tests': old.get('test_definitions', {}).get('generated', []),
                            'issues': old.get('issues', []), 'notes': old.get('notes', []),
                            'runtime_requirement': old.get('runtime_requirement')})
                        for key in ('runtime', 'pending_runtime', 'durable_evidence'):
                            entity_record.pop(key, None)
                if prior_output and library_root and (Path(library_root) / 'catalog.json').is_file():
                    # A newer durable reviewer rejection outranks an older saved-plan approval.
                    from creation_pipeline.artifacts import store
                    current = next((e for e in store.entries(library_root, include_candidates=True) if e['name'] == name), None)
                    if current and current['zone'] == 'candidates':
                        current_frozen = safe_relative(Path(library_root), current['evidence'])
                        current_record = verify_evidence(current_frozen, current['freeze_sha256'])
                        review_path = current_frozen / 'runtime/association/independent-review.json'
                        if (review_path.is_file() and entity_record is not None
                                and current_record['files'] == entity_record['files']
                                and current_record['delivery']['inputs']['sources'] == old['delivery']['inputs']['sources']):
                            rejected = read_json(review_path)['review']
                            if rejected['status'] != 'pass':
                                continuation_tests = copy.deepcopy(current_record.get('test_definitions', {}))
                                continuation_feedback = [rejected, {'name': 'locked_author_checks', 'status': 'fail',
                                    'findings': ['Resolve the recorded review issue; preserve existing business code and correct tests. Do not reinterpret a later approval as overriding this rejection.'],
                                    'locked_acceptance': current_record['delivery']['inputs']['acceptance']}]
                                config['revision_parents'][name] = current['revision_id']
                                entity_record = None
                if entity_record is None:
                    entity_record = _candidate(session, config, entity, bundle, work,
                                              config["execute_generated_checks"], initial_feedback=continuation_feedback)
                    if continuation_tests is not None and hash_object(entity_record.get('test_definitions', {})) != hash_object(continuation_tests):
                        entity_record.update(status='failed', content_status='failed')
                        entity_record.setdefault('checks', []).append({'name': 'continuation_locked_checks', 'status': 'fail',
                            'required': True, 'findings': ['Repair changed locked author checks; independent versioned oracle correction required']})
                entity_record["fingerprint"] = fingerprint
                # Run the delivered files from a different directory before readiness.
                if entity_record["status"] == "ready" and not entity_record.get("reused_from"):
                    relocated = work / "relocated" / name
                    shutil.copytree(bundle / "skills" / name, relocated, dirs_exist_ok=bool(resume_id))
                    artifact = {"tests": entity_record["test_definitions"]["generated"]}
                    scoped = copy.deepcopy(config)
                    scoped["checks"] = entity_record["test_definitions"]["configured"]
                    checks = run_checks(scoped, artifact, relocated, sources, work / "relocation-checks" / name,
                                        config["execute_generated_checks"])
                    if manifest(relocated) != entity_record["files"]:
                        checks.append({"name": "relocation_immutability", "status": "fail", "required": True, "findings": ["Relocated files changed"]})
                    entity_record["checks"] += checks
                    entity_record["status"] = classify(entity_record["checks"])
                runtime_history, runtime_seen = [], set()
                runtime_override, runtime_existing, runtime_round = None, False, 0
                while True:
                    runtime_receipt = None
                    entity_record.setdefault("files", [])
                    entity_record.setdefault("plan", entity)
                    sources.verify()
                    proposal = config.get("runtime_requirements", {}).get(name, entity_record.get("runtime_requirement"))
                    authored = entity_record.get("runtime_requirement") or {}
                    if not isinstance(authored, dict):
                        authored = {}
                    if (isinstance(proposal, dict) and authored.get("status") in {"required", "not_required"}
                            and proposal.get("status") in {"required", "not_required"} and authored["status"] != proposal["status"]):
                        proposal = {"status": "unknown", "reason": "Configured and authored execution requirements conflict", "citations": []}
                    if not runtime_existing:
                        finalize(entity_record, sources.manifest(), proposal, draft=config["draft_only"])
                    from creation_pipeline.runtime.preparation import prepare
                    from creation_pipeline.runtime.local import LocalExecutor
                    from creation_pipeline.runtime.service import execute_prepared
                    runtime_spec = copy.deepcopy(runtime_override if runtime_override is not None else runtime_spec_for(config, name))
                    # The caller's own wording is an obligation source for the
                    # invalid-input classification, not only the upstream source.
                    runtime_spec.setdefault('requirements', [config.get('prompt', '')] + list(config.get('constraints') or []))
                    # The association review is an independent model stage too; give
                    # runtime preparation the batch's native provider (no secrets).
                    runtime_spec.setdefault('native_model', {key: config['model'].get(key) for key in
                        ('backend', 'name', 'api_model', 'transport', 'reasoning_effort', 'service_tier')})
                    runtime_spec.setdefault("options", {}).setdefault("model", session.model_name)
                    runtime_spec["options"].setdefault("transport", config["model"].get("transport", "default"))
                    runtime_spec["options"].setdefault("progress_watch", config["execution"].get("progress_watch", "terminate"))
                    for key, source in (("reasoning_effort", "reasoning_effort"), ("service_tier", "service_tier")):
                        value = config["model"].get(source)
                        if value is not None:
                            runtime_spec["options"].setdefault(key, value)
                    if config["limits"]["model_timeout"] is not None:
                        runtime_spec["options"]["model_timeout"] = min(runtime_spec["options"].get("model_timeout", 600), config["limits"]["model_timeout"])
                    executor = LocalExecutor(runtime_spec.get("resource_refs"), deadline=config.get("_deadline"))
                    def runtime_call_guard():
                        from creation_pipeline.runtime.preparation import RuntimeBlocked
                        if (len(session.receipts) >= bound(config["limits"]["model_calls"])
                                or len(session.receipts) - config['_candidate_start'] >= bound(config["limits"]["candidate_calls"])
                                or time.monotonic() >= config["_deadline"]):
                            raise RuntimeBlocked("explicit_budget", "Explicit run model/time limit reached")
                        call = {"phase": "runtime_planning", "model": session.model_name, "status": "attempted", "usage": None}
                        session.receipts.append(call)
                        entity_record.setdefault("model_calls", []).append(call)
                    materials = prepare(entity_record, bundle / "skills" / name, sources.manifest(),
                                        work / "runtime-preparation" / name / uuid.uuid4().hex, runtime_spec, executor, runtime_call_guard)
                    # Final freeze is distinct from the author's durable completion receipt.
                    entity_record.pop("durable_evidence", None)
                    relative = "evidence/" + name + "/" + uuid.uuid4().hex
                    freeze_hash = seal(safe_relative(output, relative), bundle / "skills" / name,
                                       entity_record, sources.manifest(), materials)
                    entity_record["durable_evidence"] = {"path": relative, "freeze_sha256": freeze_hash}
                    if materials is not None:
                        runtime_receipt = execute_prepared(output, entity_record, executor, persist_record=True)
                    if runtime_gate_stops(config, runtime_receipt):
                        entity_record['runtime_failure_gate'] = {
                            'status': runtime_receipt['status'],
                            'reason': 'First Docker build or business acceptance failure stops this batch; '
                                      'no contract correction and no second build'}
                        entity_record['stopped_reason'] = entity_record['runtime_failure_gate']['reason']
                        break
                    entry_defect = next((g for g in entity_record.get('runtime_preparation', {}).get('gaps', [])
                        if g.get('repair_lane') == 'content' and g.get('blocker_kind') == 'content_defect'), None)
                    if not entry_defect and (not runtime_receipt or runtime_receipt['status'] not in {'build_failed', 'execution_failed'}):
                        break
                    lane = 'content' if entry_defect else runtime_receipt.get('execution', {}).get('repair_lane', 'environment')
                    if entry_defect:
                        entity_record['content_status'] = 'failed'
                        runtime_receipt['diagnosis'] = entry_defect
                    if lane in {'unknown', 'contract'}:
                        from creation_pipeline.runtime.service import automatic_correction
                        prior = {k: copy.deepcopy(entity_record[k]) for k in ('delivery', 'durable_evidence', 'runtime')}
                        decision = automatic_correction(output, entity_record, runtime_spec,
                            runtime_receipt.get('execution', {}), executor, runtime_call_guard)
                        lane = decision['attribution']
                        if entity_record['delivery']['revision_id'] != prior['delivery']['revision_id']:
                            runtime_history.append(prior)
                        if lane == 'contract' or decision['status'] == 'review_required' and lane == 'unknown':
                            break
                        runtime_receipt['diagnosis'] = decision
                    if lane not in {'environment', 'content'}:
                        break
                    signature = hash_object({'files': entity_record['files'], 'plan': entity_record['delivery']['inputs']['environment']['payload'].get('plan'),
                        'status': runtime_receipt['status'], 'lane': lane,
                        'failed': [c['name'] for c in runtime_receipt.get('execution', {}).get('cases', []) if c['status'] != 'passed']})
                    if signature in runtime_seen or runtime_round >= bound(config['limits']['repair_rounds']):
                        entity_record['stopped_reason'] = 'No runtime progress or explicit repair limit reached'
                        break
                    runtime_seen.add(signature)
                    runtime_history.append({k: copy.deepcopy(entity_record[k]) for k in
                        ('delivery', 'durable_evidence', 'runtime', 'runtime_diagnosis') if k in entity_record})
                    runtime_round += 1
                    old = entity_record['delivery']
                    feedback = [{'name': 'docker_execution', 'status': 'fail', 'required': True,
                                 'findings': [lane + ' repair required'], 'receipt': runtime_receipt,
                                 'locked_acceptance': old['inputs']['acceptance']}]
                    runtime_override = copy.deepcopy(runtime_spec)
                    runtime_override['locked_cases'] = old['inputs']['acceptance']['payload'].get('cases', [])
                    if lane == 'environment':
                        runtime_override.pop('plan', None)
                        runtime_override['previous_plan'] = old['inputs']['environment']['payload'].get('plan')
                        runtime_override['feedback'] = {'phase': runtime_receipt['status'], 'diagnostic': runtime_receipt,
                                                       'policy': 'Fix environment only; source and tests are immutable'}
                        runtime_existing = True
                    else:
                        prior_author_tests = copy.deepcopy(entity_record.get('test_definitions', {}))
                        entity_record = _candidate(session, config, entity, bundle, work, False, initial_feedback=feedback)
                        if entry_defect and hash_object(entity_record.get('test_definitions', {})) != hash_object(prior_author_tests):
                            entity_record.update(status='failed', content_status='failed')
                            entity_record.setdefault('checks', []).append({'name': 'entry_repair_locked_checks',
                                'status': 'fail', 'required': True,
                                'findings': ['Entry/content repair changed existing checks; independently versioned oracle correction required']})
                        entity_record['fingerprint'] = fingerprint
                        runtime_existing = False
                entity_record['runtime_history_records'] = runtime_history
                outcomes[name] = entity_record
                write_json(output / "records" / (name + ".json"), sanitized(entity_record))
                record["entities"].append({"name": name, "kind": "skill", "status": entity_record["status"], "needs": []})
                if entity_record["content_status"] == "passed" and entity_record.get("additional_candidates"):
                    for raw in entity_record["additional_candidates"]:
                        addition = normalize({"candidates": [raw]})["candidates"][0]
                        candidate_plan = {"summary": "Source-supported scope adjustment", "candidates": [addition], "omitted": [], "limitations": []}
                        validate_discovery(candidate_plan, config, sources)
                        if any(e["name"] == addition["name"] for e in plan["candidates"]):
                            entity_record.setdefault("notes", []).append("Additional candidate name already exists: " + addition["name"])
                            continue
                        if len(plan["candidates"]) >= bound(config["limits"]["max_candidates"]):
                            record.setdefault("deferred_candidates", []).append(addition)
                            continue
                        plan["candidates"].append(addition)
                        if len(roots) < bound(config["limits"]["max_builds"]):
                            roots.append(addition)
                        else:
                            record["deferred"].append(addition["name"])

            # Later checks must not alter any previously validated skill.
            for name, entity_record in outcomes.items():
                directory = bundle / "skills" / name
                if directory.exists() and manifest(directory) != entity_record["files"]:
                    raise ValueError("Bundle entity changed after validation: " + name)
            sources.verify()
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
            adoption_enabled = config["adoption"]["enabled"] and not no_adopt
            if outcomes and adoption_enabled:
                record["adoption"] = adopt(output, list(outcomes.values()), config, library_root or ROOT / "skills")
            else:
                record["adoption"] = [{"name": n, "status": "not_eligible" if adoption_enabled else "disabled"} for n in outcomes]
            states = [r["status"] for r in record["entities"]]
            record["status"] = ("no_candidates" if not states else "ready" if all(s == "ready" for s in states)
                                else "partial" if "ready" in states else "failed" if "failed" in states
                                else "blocked" if "blocked" in states else "incomplete" if "incomplete" in states
                                else "not_run" if "not_run" in states else "draft")
            if any(a["status"] == "conflict" for a in record.get("adoption", [])):
                record["status"] = "partial"
    except KeyboardInterrupt:
        record["status"] = "interrupted"
        record["errors"].append("User interrupted; local workspace and agent session retained")
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        record["status"] = "blocked" if isinstance(exc, BlockedError) else "incomplete" if isinstance(exc, (IncompleteError, BudgetError)) else "failed"
        record["errors"].append(redact(exc))
    record["finished_at"] = now()
    record["counts"] = dict(Counter(e["status"] for e in record["entities"]))
    receipts = session.receipts if session else []
    # model_calls is what this build spent; model_metrics keeps the full session
    # trail because resumed turns reuse earlier receipts and the audit needs them.
    this_build = receipts[build_call_start:] if session else []
    record["model_calls"] = this_build
    record["model_metrics"] = {"calls_attempted": len(receipts), "usage_fully_reported": bool(receipts) and all(r.get("usage") for r in receipts),
                               "receipts": receipts, "monetary_cost": None}
    usages = [r["usage"] for r in receipts if isinstance(r.get("usage"), dict)]
    usage_keys = {k for u in usages for k, v in u.items() if type(v) is int}
    record["model_metrics"]["reported_totals"] = {k: sum(u.get(k, 0) for u in usages if type(u.get(k, 0)) is int)
                                                   for k in usage_keys} if usages else None
    if plan is not None:
        record["accepted_plan_sha256"] = hash_object(plan)
        record["discovery_summary"] = plan["summary"]
        record["candidate_count"] = len(plan["candidates"])
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
    successful = record["status"] in ("ready", "planned", "no_candidates")
    record["temporary_workspace"] = str(work) if not successful or keep_debug else None
    write_json(output / "summary.json", sanitized(record))
    if successful and not keep_debug:
        clean_run(state, build_id)
    return {"build_id": build_id, "status": record["status"], "output": str(output),
            "counts": record["counts"], "entities": record["entities"],
            "discovery_summary": record.get("discovery_summary"), "candidate_count": record.get("candidate_count", 0),
            "adoption": record.get("adoption", []), "deferred": record.get("deferred", []), "model_calls": len(this_build), "errors": record["errors"]}
