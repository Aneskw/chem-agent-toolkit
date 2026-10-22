from pathlib import Path

from .analyze import ROOT
from .package import save_files
from .schemas import AUTHOR, REVIEW


def author(session, config, plan, staging, feedback=None, previous=None):
    instructions = (ROOT / "creation_pipeline/prompts/author.md").read_text(encoding="utf-8")
    result = session.stage(instructions, {
        "plan": plan, "sources": session.sources.index(),
        "evidence": session.sources.validate_evidence(plan["evidence"]),
        "minimum": (ROOT / "docs/skills/minimum.md").read_text(encoding="utf-8"),
        "packaging": (ROOT / "docs/skills/packaging.md").read_text(encoding="utf-8"),
        "configured_checks": config["checks"], "feedback": feedback or [],
        "user_guidance": config["prompt"], "constraints": config["constraints"],
        "user_notes": config["notes"], "shared_tools": config.get("_shared_tools", []),
        "execution_policy": {"generated_checks_enabled": config.get("execute_generated_checks", False),
                             "propose_checks_when_none_configured": True},
        "previous_artifact": previous,
    }, schema=AUTHOR)
    if isinstance(result, dict):
        result.setdefault("tests", [])
    if not isinstance(result, dict) or not isinstance(result.get("tests"), list):
        raise ValueError("Author response must provide files, tests and coverage")
    if not isinstance(result.get("coverage"), dict):
        raise ValueError("Author response must locate the four minimum requirements")
    save_files(staging, result.get("files"), config["limits"]["package_bytes"], tool=plan.get("kind") == "tool")
    return result


def review(session, plan, artifact, checks, config=None):
    instructions = (ROOT / "creation_pipeline/prompts/review.md").read_text(encoding="utf-8")
    result = session.stage(instructions, {"plan": plan, "artifact": artifact, "checks": checks,
        "evidence": session.sources.validate_evidence(plan["evidence"]),
        "sources": session.sources.index(), "user_guidance": (config or {}).get("prompt", ""),
        "constraints": (config or {}).get("constraints", {})}, schema=REVIEW)
    if not isinstance(result, dict) or result.get("status") not in ("pass", "fail", "not_run"):
        raise ValueError("Invalid content review response")
    if not isinstance(result.get("findings"), list):
        raise ValueError("Review requires findings")
    if result.get("resolution") not in ("none", "revise_files", "supply_evidence"):
        raise ValueError("Review must distinguish file repair from missing evidence")
    if result["resolution"] == "supply_evidence":
        result["status"] = "not_run"
    return {"name": "content_review", "required": True, **result,
            "evidence_kind": "model_review_not_independent_scientific_validation"}
