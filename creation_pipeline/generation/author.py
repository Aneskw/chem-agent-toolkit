import json
from creation_pipeline.paths import ROOT, PROMPTS
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.schemas import REVIEW, DELIVERY
from creation_pipeline.generation.context import candidate_context
from creation_pipeline.models import ModelCallError, iterations
from creation_pipeline.records import digest


def _author_once(session, config, plan, staging, feedback=None, previous=None):
    instructions = (PROMPTS / "author.md").read_text(encoding="utf-8")
    context = {**candidate_context(session, config, plan),
        "minimum": (ROOT / "docs/skills/minimum.md").read_text(encoding="utf-8"),
        "packaging": (ROOT / "docs/skills/packaging.md").read_text(encoding="utf-8"),
        "feedback": feedback or [], "previous_artifact": previous}
    from creation_pipeline.artifacts.delivery import delivered, finish, validate_package
    staging.mkdir(parents=True, exist_ok=True)
    token = digest(json.dumps({"plan": plan, "feedback": feedback or []}, sort_keys=True).encode())
    saved = delivered(session.work, staging, token)
    if saved is None:
        metadata = session.work / "deliveries" / (plan["name"] + "-metadata.json")
        context.update(_phase="author", output_directory=str(staging.resolve()),
            metadata_path=str(metadata), delivery_token=token)
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
    from creation_pipeline.validation.basis import validate_basis
    saved["basis"] = validate_basis(saved.get("basis"), session.sources)
    return {**saved, "files": [{**item, "purpose": "Delivered capability resource"} for item in manifest(staging)]}


def author(session, config, plan, staging, feedback=None, previous=None):
    last = None
    for _ in iterations(config["limits"]["repair_rounds"]):
        try:
            return _author_once(session, config, plan, staging, feedback, previous)
        except ModelCallError:
            raise
        except (ValueError, KeyError, TypeError) as exc:
            error = str(exc)
            if error == last:
                from creation_pipeline.models import IncompleteError
                raise IncompleteError("Repeated unchanged author delivery error: " + error) from exc
            last = error
            feedback = [{"name": "author_delivery", "findings": [error],
                "action": "Correct only your files/metadata using retained observations; no execution"}]
    from creation_pipeline.models import IncompleteError
    raise IncompleteError("Author delivery repair limit reached: " + str(last))


def review(session, plan, artifact, checks, config=None):
    instructions = (PROMPTS / "review.md").read_text(encoding="utf-8")
    context = {**candidate_context(session, config, plan, independent_review=True), "_phase": "review",
        "minimum": (ROOT / "docs/skills/minimum.md").read_text(encoding="utf-8"),
        "packaging": (ROOT / "docs/skills/packaging.md").read_text(encoding="utf-8"),
        "artifact": artifact, "checks": checks}
    previous_error = None
    while True:
        result = session.stage(instructions, context, schema=REVIEW)
        try:
            if not isinstance(result, dict) or result.get("status") not in ("pass", "fail", "not_run"):
                raise ValueError("status must be pass/fail/not_run")
            if result.get("resolution") not in ("none", "revise_files", "supply_evidence"):
                raise ValueError("resolution must be none/revise_files/supply_evidence")
            if not isinstance(result.get("findings"), list):
                raise ValueError("findings must be an array")
            for index, finding in enumerate(result["findings"]):
                if not isinstance(finding, dict) or type(finding.get("blocking")) is not bool:
                    raise ValueError(f"findings[{index}] requires an object and boolean blocking")
                for key in ("location", "problem", "evidence", "impact", "action", "category"):
                    if not isinstance(finding.get(key), str) or not finding[key].strip():
                        raise ValueError(f"findings[{index}].{key} requires text")
            blocking = any(f["blocking"] for f in result["findings"])
            if result["status"] == "fail" and not blocking:
                raise ValueError("fail requires an actionable blocking finding")
            if blocking:
                result["status"] = "fail"
                if result["resolution"] == "none":
                    result["resolution"] = "revise_files"
            if result["resolution"] == "supply_evidence":
                result["status"] = "not_run"
            if result["status"] == "pass" and result["resolution"] != "none":
                raise ValueError("pass requires resolution=none")
            return {**result, "name": "content_review", "required": True,
                    "evidence_kind": "source_and_content_review_only"}
        except (ValueError, TypeError, KeyError) as exc:
            error = str(exc)
            if error == previous_error:
                from creation_pipeline.models import IncompleteError
                raise IncompleteError("Repeated review record format error: " + error) from exc
            previous_error = error
            context = {**context, "previous_review": result, "record_format_error": error,
                       "correction": "Correct only your review record. Do not change Skill files or repeat broad exploration."}
