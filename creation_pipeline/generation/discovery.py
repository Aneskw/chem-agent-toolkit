"""Resource discovery and reusable, source-locked plans."""
import copy
import json
from collections import Counter
from pathlib import Path

from creation_pipeline.models import validate_plan, bound, iterations, BlockedError, IncompleteError, BudgetError
from creation_pipeline.records import digest, read_json, write_json, safe_relative
from creation_pipeline.schemas import CANDIDATES, CONSOLIDATION

from creation_pipeline.paths import ROOT, PROMPTS
SPEC_PATHS = ("docs/skills/minimum.md", "docs/skills/packaging.md",
              "creation_pipeline/generation/prompts/analyze.md", "creation_pipeline/generation/prompts/author.md",
              "creation_pipeline/generation/prompts/review.md", "creation_pipeline/generation/prompts/consolidate.md")


def specifications():
    return {p: digest((ROOT / p).read_bytes()) for p in SPEC_PATHS}


def ordered(plan):
    entities = plan["candidates"]
    by_name = {e["name"]: e for e in entities}
    if len(by_name) != len(entities):
        raise ValueError("Duplicate candidate names")
    for entity in entities:
        if entity.get("kind", "skill") != "skill" or entity.get("needs"):
            raise ValueError("Independent tools/shared dependencies are unsupported; rediscover as skills with local scripts")
    return sorted(entities, key=lambda e: (e["priority"], e["name"]))



def validate_discovery(plan, config, sources):
    if not isinstance(plan, dict) or not isinstance(plan.get("candidates"), list):
        raise ValueError("Discovery must provide candidates")
    if len(plan["candidates"]) > bound(config["limits"]["max_candidates"]):
        raise ValueError("Discovery exceeds max_candidates")
    if not isinstance(plan.get("summary"), str) or not plan["summary"].strip():
        raise ValueError("Discovery needs a summary, including when no candidates exist")
    for key in ("omitted", "limitations"):
        if not isinstance(plan.get(key), list):
            raise ValueError("Discovery needs " + key)
    for entity in plan["candidates"]:
        try:
            validate_plan(entity, require_build=bool(entity.get("selected")))
        except ValueError as exc:
            raise ValueError(f"Candidate {entity.get('name', '<unnamed>')}: {exc}") from exc
        if entity.get("kind") != "skill" or ("construction" not in entity and entity.get("implementation") not in ("upstream", "adapter", "composition")):
            raise ValueError("Invalid candidate kind/implementation")
        for key in ("rationale", "upstream_behavior"):
            if not isinstance(entity.get(key), str) or not entity[key].strip():
                raise ValueError("Candidate needs " + key)
        if type(entity.get("selected")) is not bool or type(entity.get("priority")) is not int:
            raise ValueError("Candidate needs boolean selected and integer priority")
        if not isinstance(entity.get("needs"), list) or any(not isinstance(v, str) for v in entity["needs"]):
            raise ValueError("Candidate needs must be an empty array; shared tools are unsupported")
        if "construction" not in entity and config["intent"] != "auto" and entity["intent"] != config["intent"]:
            raise ValueError("Candidate conflicts with explicit packaging intent")
        sources.validate_evidence(entity["evidence"])
        if entity.get("intent") == "extension" and entity["added_behavior"].strip().lower() == "none":
            raise ValueError("Extension must identify added behavior")
        if entity["selected"] and entity["kind"] == "skill" and entity["readiness"] != "blocked" and not any(f.get("path") == "SKILL.md" for f in entity["files"]):
            raise ValueError("Skill plan needs SKILL.md")
    for entity in plan["candidates"]:
        if entity.get("intent") == "extension" and not entity.get("method_evidence"):
            raise ValueError("Extension needs source-backed method_evidence")
        if entity.get("method_evidence"):
            sources.validate_evidence(entity["method_evidence"])
    for fact in plan.get("handoff", []):
        sources.validate_evidence([{ "id": identifier.strip(), "claim": fact["fact"]}
                                  for identifier in (__import__("re").split(r"[,;]", fact["evidence"]) if isinstance(fact["evidence"], str) else fact["evidence"])])
    ordered(plan)
    return plan


def discovery_context(session, config):
    return {
        "minimum": (ROOT / "docs/skills/minimum.md").read_text(encoding="utf-8"),
        "packaging": (ROOT / "docs/skills/packaging.md").read_text(encoding="utf-8"),
        "user_guidance": config["prompt"], "notes": config["notes"], "constraints": config["constraints"],
        "intent": config["intent"], "limits": {k: config["limits"][k] for k in ("max_candidates", "max_builds")},
        "sources": session.sources.index(), "source_errors": session.sources.errors,
    }


def decision(session, config, step, context, validate):
    """One decision with recoverable format repairs in the existing discovery session."""
    instructions = (PROMPTS / ("analyze.md" if step == "explore" else "consolidate.md")).read_text(encoding="utf-8")
    context = {**discovery_context(session, config), **context, "_discovery_step": step}
    last_invalid = None
    for attempt in iterations(config["limits"]["repair_rounds"]):
        old_timeout = session.limits["model_timeout"]
        spent = sum(r.get("elapsed_seconds", 0) for r in session.receipts if r.get("phase") == "discovery")
        remaining = bound(config["limits"]["discovery_seconds"]) - spent
        if remaining <= 0:
            raise BudgetError("Group discovery time budget exhausted", scope="group")
        stage_cap = min(bound(old_timeout), remaining)
        session.limits["model_timeout"] = None if stage_cap == float("inf") else stage_cap
        try:
            plan = session.stage(instructions, context, schema=CANDIDATES if step == "explore" else CONSOLIDATION)
        finally:
            session.limits["model_timeout"] = old_timeout
        if plan.get("outcome") in ("incomplete", "blocked"):
            write_json(session.work / "discovery-partial.json", plan)
            error = IncompleteError if plan["outcome"] == "incomplete" else BlockedError
            raise error("Discovery " + plan["outcome"] + ": " + plan["summary"])
        try:
            if step == "explore" and plan.get("outcome") == "candidates" and not plan.get("candidates"):
                plan["candidates"] = [read_json(safe_relative(session.work, "candidates/" + n + ".json"))
                                      for n in plan.get("saved_candidates", [])]
            elif step != "explore" and plan.get("saved_candidates"):
                raise ValueError("Consolidation must return the complete final candidates, not saved_candidates")
            if plan.get("outcome") not in ("candidates", "no_suitable_candidates") or bool(plan.get("candidates")) != (plan.get("outcome") == "candidates"):
                raise ValueError("Discovery outcome contradicts candidate list")
            plan = normalize(plan)
            validate_discovery(plan, config, session.sources)
            validate(plan)
            return plan
        except (ValueError, KeyError, TypeError) as exc:
            signature = digest(json.dumps([plan, str(exc)], sort_keys=True).encode())
            if signature == last_invalid:
                raise ValueError("Repeated unchanged discovery validation failure: " + str(exc)) from exc
            last_invalid = signature
            if config["limits"]["repair_rounds"] is not None and attempt == config["limits"]["repair_rounds"]:
                raise
            context.update(previous_decision=plan, validation_error=str(exc),
                           read_evidence=session.sources.compact_evidence())
    raise ValueError("Discovery could not be validated")


def validate_mapping(draft, final):
    before = {c["name"] for c in draft["candidates"]}
    after = {c["name"] for c in final["candidates"]}
    seen, targets = [], set()
    if not isinstance(final.get("mapping"), list):
        raise ValueError("Consolidation requires mapping")
    omissions = {o["capability"] for o in final["omitted"] if o.get("reason", "").strip()}
    for item in final["mapping"]:
        origins, destinations = item["from"], item["to"]
        if (not isinstance(origins, list) or not isinstance(destinations, list)
                or any(not isinstance(n, str) for n in origins + destinations)
                or not item.get("reason", "").strip() or not (origins or destinations)):
            raise ValueError("Mapping needs name arrays and a concrete reason")
        if not set(origins) <= before or not set(destinations) <= after:
            raise ValueError("Mapping references unknown candidate names")
        if len(set(destinations)) != len(destinations):
            raise ValueError("Mapping repeats a final name")
        if not destinations and not set(origins) <= omissions:
            raise ValueError("Removed draft names require explicit omitted entries")
        seen.extend(origins)
        targets.update(destinations)
    if Counter(seen) != Counter({name: 1 for name in before}) or targets != after:
        raise ValueError("Mapping must account for every draft exactly once and every final candidate")


def consolidate(session, config, draft, *, frozen=(), active=None):
    def validate(final):
        validate_mapping(draft, final)
        by_name = {c["name"]: c for c in final["candidates"]}
        if active and active not in by_name:
            raise ValueError("Retain the active package name during reconciliation")
        keys = ("task", "scope", "entrypoint", "construction", "evidence", "readiness", "gaps")
        for old in frozen:
            new = by_name.get(old["name"], {})
            if any(old.get(k) != new.get(k) for k in keys):
                raise ValueError("Approved package plan is frozen: " + old["name"])
    return decision(session, config, "reconcile" if active else "consolidate",
                    {"draft": draft, "frozen_plans": list(frozen), "active_package": active}, validate)


def analyze(session, config):
    path = session.work / "discovery-state.json"
    signature = digest(json.dumps({k: config[k] for k in ("prompt", "notes", "constraints", "intent")}, sort_keys=True).encode())
    saved = read_json(path) if path.exists() else {"specifications": specifications(), "guidance": signature}
    if saved["specifications"] != specifications() or saved["guidance"] != signature:
        raise ValueError("Discovery checkpoint changed; explicitly rediscover")
    if "draft" not in saved:
        draft = decision(session, config, "explore", {"previous_run_errors": config.get("_previous_run_errors", [])}, lambda plan: None)
        saved["draft"] = draft
        write_json(path, saved)
    draft = saved["draft"]
    validate_discovery(draft, config, session.sources)
    if "final" not in saved:
        saved["final"] = consolidate(session, config, draft) if draft["candidates"] else {**draft, "mapping": []}
        write_json(path, saved)
    final = copy.deepcopy(saved["final"])
    validate_discovery(final, config, session.sources)
    validate_mapping(draft, final)
    return final


def reconcile(session, config, entity, proposals):
    """Reconsider affected boundaries before review; never change approved package plans."""
    plan = config["_group_plan"]
    draft = {"summary": "Author proposals against this group's final boundaries", "omitted": [], "limitations": [],
             "candidates": copy.deepcopy(plan["candidates"])}
    names = {c["name"] for c in draft["candidates"]}
    for index, raw in enumerate(proposals):
        c = normalize({"candidates": [raw]})["candidates"][0]
        if c["name"] in names:
            c["name"] = f"proposal-{index + 1}-" + c["name"]
        names.add(c["name"])
        draft["candidates"].append(c)
    validate_discovery(draft, {**config, "limits": {**config["limits"], "max_candidates": None}}, session.sources)
    final = consolidate(session, config, draft, frozen=config.get("_approved_plans", []), active=entity["name"])
    updated = next(c for c in final["candidates"] if c["name"] == entity["name"])
    changed = any(entity.get(k) != updated.get(k) for k in ("task", "scope", "entrypoint", "construction"))
    entity.update(updated)
    plan["candidates"] = [entity if c["name"] == entity["name"] else c for c in final["candidates"]]
    plan.setdefault("reconciliations", []).append({"draft": draft, "final": final})
    write_json(session.work / "group-plan.json", plan)
    return changed, final["mapping"]


def normalize(discovery):
    """Retain a stable host record while allowing concise Agent decisions."""
    discovery = dict(discovery)
    normalized = []
    for index, c in enumerate(discovery["candidates"]):
        if "capability" not in c:  # read-only compatibility with older native records
            normalized.append(c)
            continue
        normalized.append({"name": c["name"], "task": c["capability"], "scope": c["boundary"],
            "entrypoint": c["usage_path"], "rationale": c["value"], "construction": c["construction"],
            "upstream_behavior": c["capability"], "added_behavior": "source-supported only",
            "kind": "skill", "needs": [], "selected": True, "priority": index,
            "readiness": "blocked" if c["blocked"] else "callable", "gaps": c["gaps"],
            "dependencies": [], "files": [{"path": "SKILL.md", "purpose": "Capability instructions"}],
            "checks": [], "evidence": c["evidence"], "method_evidence": []})
    discovery["candidates"] = normalized
    discovery.setdefault("handoff", [])
    return discovery
