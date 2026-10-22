"""Resource discovery and reusable, source-locked plans."""
import json
from pathlib import Path

from .models import validate_plan
from .records import digest
from .schemas import DISCOVERY

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATHS = ("docs/skills/minimum.md", "docs/skills/packaging.md",
              "creation_pipeline/prompts/analyze.md", "creation_pipeline/prompts/author.md",
              "creation_pipeline/prompts/review.md")


def specifications():
    return {p: digest((ROOT / p).read_bytes()) for p in SPEC_PATHS}


def ordered(plan):
    entities = plan["candidates"]
    by_name = {e["name"]: e for e in entities}
    if len(by_name) != len(entities):
        raise ValueError("Duplicate candidate names")
    result, visiting, visited = [], set(), set()
    def visit(name):
        if name in visiting:
            raise ValueError("Cyclic shared tool dependency")
        if name in visited:
            return
        visiting.add(name)
        for need in by_name[name]["needs"]:
            if need not in by_name or by_name[need]["kind"] != "tool":
                raise ValueError("Unresolved shared tool dependency: " + need)
            visit(need)
        visiting.remove(name)
        visited.add(name)
        result.append(by_name[name])
    for entity in sorted(entities, key=lambda e: (e["priority"], e["name"])):
        visit(entity["name"])
    return result


def validate_discovery(plan, config, sources):
    if not isinstance(plan, dict) or not isinstance(plan.get("candidates"), list):
        raise ValueError("Discovery must provide candidates")
    if len(plan["candidates"]) > config["limits"]["max_candidates"]:
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
        if entity.get("kind") not in ("tool", "skill") or entity.get("implementation") not in ("upstream", "adapter", "composition"):
            raise ValueError("Invalid candidate kind/implementation")
        for key in ("rationale", "upstream_behavior"):
            if not isinstance(entity.get(key), str) or not entity[key].strip():
                raise ValueError("Candidate needs " + key)
        if type(entity.get("selected")) is not bool or type(entity.get("priority")) is not int:
            raise ValueError("Candidate needs boolean selected and integer priority")
        if not isinstance(entity.get("needs"), list) or any(not isinstance(v, str) for v in entity["needs"]):
            raise ValueError("Candidate needs shared tool names")
        if config["intent"] != "auto" and entity["intent"] != config["intent"]:
            raise ValueError("Candidate conflicts with explicit packaging intent")
        sources.validate_evidence(entity["evidence"])
        if entity["intent"] == "extension" and entity["added_behavior"].strip().lower() == "none":
            raise ValueError("Extension must identify added behavior")
        if entity["selected"] and entity["kind"] == "skill" and entity["readiness"] != "blocked" and not any(f.get("path") == "SKILL.md" for f in entity["files"]):
            raise ValueError("Skill plan needs SKILL.md")
    ordered(plan)
    return plan


def analyze(session, config):
    instructions = (ROOT / "creation_pipeline/prompts/analyze.md").read_text(encoding="utf-8")
    initial = []
    for sid, entry in session.sources.entries.items():
        path = Path(entry["path"])
        if path.is_file() and len(initial) < 2:
            initial.append(session.sources.request({"action": "read", "source": sid,
                "path": path.name, "start": 1, "limit": 120}))
    context = {
        "user_guidance": config["prompt"], "notes": config["notes"], "constraints": config["constraints"],
        "intent": config["intent"], "limits": {k: config["limits"][k] for k in ("max_candidates", "max_builds")},
        "sources": session.sources.index(), "source_errors": session.sources.errors,
        "initial_source_views": initial,
    }
    for attempt in range(config["limits"]["repair_rounds"] + 1):
        plan = session.stage(instructions, context, schema=DISCOVERY)
        try:
            return validate_discovery(plan, config, session.sources)
        except ValueError as exc:
            if attempt == config["limits"]["repair_rounds"]:
                raise
            context.update(previous_discovery=plan, validation_error=str(exc),
                           read_evidence=session.sources.compact_evidence())
    raise ValueError("Discovery could not be validated")
