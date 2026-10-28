import json
from creation_pipeline.paths import ROOT, PROMPTS
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.schemas import REVIEW, DELIVERY
from creation_pipeline.generation.context import candidate_context
from creation_pipeline.models import ModelCallError
from creation_pipeline.records import digest


def author(session, config, plan, staging, feedback=None, previous=None):
    instructions = (PROMPTS / "author.md").read_text(encoding="utf-8")
    context = {**candidate_context(session, config, plan),
        "minimum": (ROOT / "docs/skills/minimum.md").read_text(encoding="utf-8"),
        "packaging": (ROOT / "docs/skills/packaging.md").read_text(encoding="utf-8"),
        "configured_checks": config["checks"], "feedback": feedback or [],
        "configured_requirement": config.get("runtime_requirements", {}).get(plan["name"]),
        "execution_policy": {"generated_checks_enabled": config.get("execute_generated_checks", False)},
        "previous_artifact": previous}
    from creation_pipeline.artifacts.delivery import delivered, finish, validate_package
    staging.mkdir(parents=True, exist_ok=True)
    token = digest(json.dumps({"plan": plan, "feedback": feedback or []}, sort_keys=True).encode())
    saved = delivered(session.work, staging, token)
    if saved is None:
        metadata = session.work / "deliveries" / (plan["name"] + "-metadata.json")
        context.update(_phase="author", output_directory=str(staging.resolve()),
            metadata_path=str(metadata), delivery_token=token)
        instructions += "\nWrite files directly. Save checks/issues/notes and runtime_requirement as metadata_path JSON. Use workspace helper finish with run, package, token and metadata. The helper computes the file manifest. If the helper executable is unavailable, do not repeatedly retry it: once ALL intended files and metadata are fully written, return completed=true and state that host finalization is needed. The host then performs the SAME finish validation and writes the receipt; completed never grants content/runtime acceptance. If files or metadata are unfinished, return completed=false. Do not return file content or coverage."
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


def review(session, plan, artifact, checks, config=None):
    instructions = (PROMPTS / "review.md").read_text(encoding="utf-8")
    execution_policy = {
        "generated_checks_enabled": config.get("execute_generated_checks", False),
        "review_scope": "source_fidelity_package_content_and_declared_checks",
        "business_execution": ("deferred_to_bound_docker" if config.get('_docker_checks')
                               else "only_when_explicitly_enabled"),
        "runtime_evidence_required_for_content_approval": False,
        "content_pass_grants_runtime_qualification": False,
    }
    import copy
    stage_schema = copy.deepcopy(REVIEW)
    stage_schema["properties"]["oracle_changes_verified"] = {"type": "boolean"}
    stage_schema["required"].append("oracle_changes_verified")
    stage_schema["properties"]["execution_gaps"] = {"type": "array", "items": {"type": "string"}}
    stage_schema["required"].append("execution_gaps")
    stage_schema["properties"]["requirement_assessment"] = {"type": "string", "enum": ["confirmed", "unknown", "conflict"]}
    stage_schema["required"].append("requirement_assessment")
    execution_requirement = (config or {}).get('runtime_requirements', {}).get(
        plan['name'], artifact.get('runtime_requirement'))
    if isinstance(execution_requirement, dict) and 'file_output' in execution_requirement:
        stage_schema['properties']['file_output_assessment'] = {
            'type': 'string', 'enum': ['confirmed', 'unknown', 'conflict']}
        stage_schema['required'].append('file_output_assessment')
        instructions += ('\nIndependently assess execution_requirement.file_output against the actual '
            'upstream documentation AND delivered code. Return file_output_assessment=confirmed only '
            'when the cited read_only_stdout contract is exact, inputs are read-only and the business '
            'tool reports on stdout without a promised tool-written output. A documented output-file '
            'flag or write obligation conflicts with this mode: return conflict, even if some tests use '
            'stdout. Never infer absence of a write obligation from omitted tests or proposer claims. '
            'Otherwise return unknown. Content approval still requires the declared read-only scope '
            'and original script to be correct; runtime must later exercise actual file input, retain '
            'the stdout report and verify its business content in Docker.')
    if (config or {}).get('_binding_review') is not None:
        stage_schema['properties']['binding_verified'] = {'type': 'boolean'}
        stage_schema['required'].append('binding_verified')
        instructions += ('\nIndependently verify artifact.entry_binding against exact delivery and upstream source. '
            'binding_verified=true requires a real API/source relationship, exact source quote, correct invocation and scope, '
            'standalone code or a clearly callable function with all context/supports present. Do not accept name similarity '
            'or the proposer claim alone. Inspect the code and source. Markdown extraction must not rewrite business code. '
            'Distinguish carrier_repository from upstream and use snapshot identity when upstream version is unknown. '
            'binding_verified judges only the source-to-entry relationship and its invocation. A licence, attribution '
            'or documentation observation is a non-blocking content finding: report it, but it must not clear '
            'binding_verified and must not by itself make the review fail.')
    instructions += "\nIndependently assess the supplied execution_requirement against actual source and delivered behavior. Return requirement_assessment=confirmed only when status and citations support it without conflicting execution needs. Missing declaration is unknown. An empty test list is never proof that execution is unnecessary."
    instructions += "\nReturn execution_gaps as test names only for confirmed external prerequisite gaps, never missing delivered modules or incorrect results. Return oracle_changes_verified. When oracle_changes exist, independently check each old/new assertion against original sources. True only for justified source-backed corrections, never observed-output matching. Explain the evidence in findings. With no changes return false."
    result = session.stage(instructions, {"oracle_changes": (config or {}).get("_oracle_changes", []), "_phase": "review",
        "execution_requirement": execution_requirement,
        "authored_execution_requirement": artifact.get("runtime_requirement"),
        "minimum": (ROOT / "docs/skills/minimum.md").read_text(encoding="utf-8"),
        "packaging": (ROOT / "docs/skills/packaging.md").read_text(encoding="utf-8"),
        **candidate_context(session, config, plan), "artifact": artifact, "checks": checks,
        "evidence": session.sources.validate_evidence(plan["evidence"]),
        "sources": session.sources.index(), "user_guidance": (config or {}).get("prompt", ""),
        "constraints": (config or {}).get("constraints", {}),
        "execution_policy": execution_policy,
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
