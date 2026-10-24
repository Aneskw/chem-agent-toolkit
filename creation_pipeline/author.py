from pathlib import Path
import json
from .analyze import ROOT
from .package import save_files, manifest
from .schemas import AUTHOR, REVIEW, DELIVERY
from .context import candidate_context
from .models import ModelCallError
from .records import digest, read_json


def author(session, config, plan, staging, feedback=None, previous=None):
    instructions = (ROOT / "creation_pipeline/prompts/author.md").read_text(encoding="utf-8")
    native = getattr(session, "native", False)
    context = {**candidate_context(session, config, plan),
        "minimum": (ROOT / "docs/skills/minimum.md").read_text(encoding="utf-8"),
        "packaging": (ROOT / "docs/skills/packaging.md").read_text(encoding="utf-8"),
        "configured_checks": config["checks"], "feedback": feedback or [],
        "execution_policy": {"generated_checks_enabled": config.get("execute_generated_checks", False)},
        "previous_artifact": previous}
    if native:
        from .agent_tools import delivered, finish, validate_package
        staging.mkdir(parents=True, exist_ok=True)
        token = digest(json.dumps({"plan": plan, "feedback": feedback or []}, sort_keys=True).encode())
        saved = delivered(session.work, staging, token)
        if saved is None:
            metadata = session.work / "deliveries" / (plan["name"] + "-metadata.json")
            context.update(_phase="author", output_directory=str(staging.resolve()),
                metadata_path=str(metadata), delivery_token=token)
            instructions += "\nWrite files directly. Save checks/issues/notes as metadata_path JSON (optional if all empty). Use workspace helper finish with run, package, token and metadata. This durable receipt is the delivery; final reply is only completed/summary. The helper computes the file manifest. Do not return content or coverage."
            error = None
            try:
                result = session.stage(instructions, context, schema=DELIVERY)
            except ModelCallError as exc:
                error, result = exc, {}
            saved = delivered(session.work, staging, token)
            if saved is None and result.get("completed"):
                finish(session.work, staging, token, metadata if metadata.exists() else None)
                saved = delivered(session.work, staging, token)
            if saved is None:
                if error:
                    raise error
                raise ValueError("Author has not finalized the package; retain existing files and complete delivery")
        validate_package(staging, config["limits"]["package_bytes"])
        files = []
        for item in manifest(staging):
            path = staging / item["path"]
            f = {"path": item["path"], "purpose": "Delivered capability resource"}
            if path.suffix.lower() in {".md", ".py", ".txt", ".json", ".yaml", ".yml", ".sh"}:
                try:
                    f["content"] = path.read_bytes().decode("utf-8")
                except UnicodeError:
                    f["content"] = "[non-text resource; inspect actual file]"
            else:
                f["content"] = "[binary/structured resource; inspect actual file]"
            files.append(f)
        return {**saved, "files": files}
    # Deterministic replay compatibility only; direct API configuration is closed.
    result = dict(session.stage(instructions, context, schema=AUTHOR))
    result.setdefault("tests", [])
    save_files(staging, result.get("files"), config["limits"]["package_bytes"])
    result.pop("coverage", None)
    return result


def review(session, plan, artifact, checks, config=None):
    instructions = (ROOT / "creation_pipeline/prompts/review.md").read_text(encoding="utf-8")
    stage_schema = REVIEW
    if getattr(session, "native", False):
        import copy
        stage_schema = copy.deepcopy(REVIEW)
        stage_schema["properties"]["oracle_changes_verified"] = {"type": "boolean"}
        stage_schema["required"].append("oracle_changes_verified")
        stage_schema["properties"]["execution_gaps"] = {"type": "array", "items": {"type": "string"}}
        stage_schema["required"].append("execution_gaps")
        instructions += "\nReturn execution_gaps as test names only for confirmed external prerequisite gaps, never missing delivered modules or incorrect results. Return oracle_changes_verified. When oracle_changes exist, independently check each old/new assertion against original sources. True only for justified source-backed corrections, never observed-output matching. Explain the evidence in findings. With no changes return false."
    result = session.stage(instructions, {"oracle_changes": (config or {}).get("_oracle_changes", []), **({"_phase": "review"} if getattr(session, "native", False) else {}),
        "minimum": (ROOT / "docs/skills/minimum.md").read_text(encoding="utf-8"),
        "packaging": (ROOT / "docs/skills/packaging.md").read_text(encoding="utf-8"),
        **candidate_context(session, config, plan), "artifact": artifact, "checks": checks,
        "evidence": session.sources.validate_evidence(plan["evidence"]),
        "sources": session.sources.index(), "user_guidance": (config or {}).get("prompt", ""),
        "constraints": (config or {}).get("constraints", {}),
        "execution_policy": {"generated_checks_enabled": config.get("execute_generated_checks", False)},
        "previous_issues": (config or {}).get("_previous_issues", [])}, schema=stage_schema)
    if not isinstance(result, dict) or result.get("status") not in ("pass", "fail", "not_run"):
        raise ValueError("Invalid content review response")
    if not isinstance(result.get("findings"), list):
        raise ValueError("Review requires findings")
    if result.get("resolution") not in ("none", "revise_files", "supply_evidence"):
        raise ValueError("Review must distinguish file repair from missing evidence")
    if result.get("issues_complete") is False:
        result.update(status="not_run", resolution="supply_evidence")
        result["findings"].append("Notes/issues completeness not confirmed")
    if any(isinstance(f, dict) and f.get("blocking") for f in result["findings"]):
        result["status"] = "fail"
        if result["resolution"] == "none":
            result["resolution"] = "revise_files"
    if result["resolution"] == "supply_evidence":
        result["status"] = "not_run"
    return {"name": "content_review", "required": True, **result,
            "evidence_kind": "model_review_not_independent_scientific_validation"}
