"""Resource discovery and reusable, source-locked plans."""
import json
from pathlib import Path

from creation_pipeline.models import validate_plan, bound, iterations
from creation_pipeline.records import digest
from creation_pipeline.schemas import CANDIDATES

from creation_pipeline.paths import ROOT, PROMPTS
SPEC_PATHS = ("docs/skills/minimum.md", "docs/skills/packaging.md",
              "creation_pipeline/generation/prompts/analyze.md", "creation_pipeline/generation/prompts/author.md",
              "creation_pipeline/generation/prompts/review.md")


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


def analyze(session, config):
    instructions = (PROMPTS / "analyze.md").read_text(encoding="utf-8")
    context = {
        "user_guidance": config["prompt"], "notes": config["notes"], "constraints": config["constraints"],
        "intent": config["intent"], "limits": {k: config["limits"][k] for k in ("max_candidates", "max_builds")},
        "sources": session.sources.index(), "source_errors": session.sources.errors,
    }
    previous_result = session.state.get("completed", {}).get("discovery")
    if previous_result and Path(previous_result).is_file():
        from creation_pipeline.records import read_json
        context["previous_discovery"] = read_json(previous_result)
        context["previous_run_errors"] = config.get("_previous_run_errors", [])
        context["continuation_instruction"] = "Correct the recorded result using current instructions and errors; avoid repeating source exploration."
    last_invalid = None
    for attempt in iterations(config["limits"]["repair_rounds"]):
        stage_schema = CANDIDATES
        old_timeout = session.limits["model_timeout"]
        stage_cap = min(bound(old_timeout), bound(config["limits"]["discovery_seconds"]))
        session.limits["model_timeout"] = None if stage_cap == float("inf") else stage_cap
        try:
            plan = session.stage(instructions, context, schema=stage_schema)
        finally:
            session.limits["model_timeout"] = old_timeout
        if plan.get("outcome") == "candidates" and not plan.get("candidates"):
            from creation_pipeline.records import read_json
            from creation_pipeline.records import safe_relative
            names = plan.get("saved_candidates", [])
            plan["candidates"] = [read_json(safe_relative(session.work, "candidates/" + n + ".json")) for n in names]
        if plan.get("outcome") in ("incomplete", "blocked"):
            from creation_pipeline.records import write_json
            write_json(session.work / "discovery-partial.json", plan)
            from creation_pipeline.models import BlockedError, IncompleteError
            error = IncompleteError if plan["outcome"] == "incomplete" else BlockedError
            raise error("Discovery " + plan["outcome"] + ": " + plan["summary"])
        if bool(plan.get("candidates")) != (plan.get("outcome") == "candidates"):
            raise ValueError("Discovery outcome contradicts candidate list")
        plan = normalize(plan)
        try:
            return validate_discovery(plan, config, session.sources)
        except ValueError as exc:
            signature = digest(json.dumps([plan, str(exc)], sort_keys=True).encode())
            if signature == last_invalid:
                raise ValueError("Repeated unchanged discovery validation failure: " + str(exc)) from exc
            last_invalid = signature
            if config["limits"]["repair_rounds"] is not None and attempt == config["limits"]["repair_rounds"]:
                raise
            context.update(previous_discovery=plan, validation_error=str(exc),
                           read_evidence=session.sources.compact_evidence())
    raise ValueError("Discovery could not be validated")


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
