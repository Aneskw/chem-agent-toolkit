"""Configuration parsing and validation, independent of model-generated prose."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path


class BlockedError(ValueError):
    pass


class IncompleteError(ValueError):
    """A discovery stopped before a defensible decision; not zero value."""


class ModelCallError(ValueError):
    """Transport/backend failure, not a defect in authored files."""


class BudgetError(ModelCallError):
    """An execution bound stopped work; not evidence of a defective skill."""


def load_config(path):
    path = Path(path).resolve()
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        config = json.loads(raw)
    else:
        try:
            import yaml
        except ImportError as exc:
            raise ValueError("YAML needs PyYAML; JSON configurations need no extra package") from exc
        config = yaml.safe_load(raw)
    if not isinstance(config, dict):
        raise ValueError("Configuration must be an object")
    allowed = {"task", "sources", "model", "limits", "checks", "environment", "intent", "notes", "http_only",
               "prompt", "constraints", "execution", "network", "execute_generated_checks", "batch", "adoption", "draft_only", "runtime_requirements", "revision_parents", "runtime", "runtime_defaults"}
    unknown = set(config) - allowed
    if unknown:
        raise ValueError(f"Unknown configuration fields: {sorted(unknown)}")
    for key in ("task", "prompt", "notes"):
        if key in config and not isinstance(config[key], str):
            raise ValueError(f"{key} must be text")
    config.setdefault("prompt", config.get("task", ""))
    config.setdefault("notes", "")
    config.setdefault("constraints", {})
    if not isinstance(config["constraints"], dict):
        raise ValueError("constraints must be an object")
    config.setdefault("network", True)
    config.setdefault("execute_generated_checks", False)
    config.setdefault("draft_only", False)
    config.setdefault("runtime_requirements", {})
    config.setdefault("revision_parents", {})
    config.setdefault("runtime", {})
    config.setdefault("runtime_defaults", {})
    from creation_pipeline.runtime.preparation import validate_spec
    if not isinstance(config["runtime"], dict):
        raise ValueError("runtime must map candidate names to preparation settings")
    if not isinstance(config["runtime_defaults"], dict):
        raise ValueError("runtime_defaults must be an object shared by every candidate")
    for spec in config["runtime"].values():
        if not isinstance(spec, dict) or set(spec) - {"binding", "plan", "options", "resource_refs", "constraints"}:
            raise ValueError("Unsupported runtime configuration")
        validate_spec(spec)
    # Shared defaults exist so a normal creation can fix provider options before the
    # candidate name is known; a per-candidate spec overrides them.
    validate_spec(config["runtime_defaults"])
    if not isinstance(config["revision_parents"], dict) or any(not isinstance(v, str) for v in config["revision_parents"].values()):
        raise ValueError("revision_parents must map candidate names to expected current revision IDs")
    if type(config["draft_only"]) is not bool or not isinstance(config["runtime_requirements"], dict):
        raise ValueError("draft_only must be boolean; runtime_requirements must map candidate names to declarations")
    if any(type(config[k]) is not bool for k in ("network", "execute_generated_checks")):
        raise ValueError("network and execute_generated_checks must be booleans")
    for key, defaults in (("batch", {"label": "skills", "tags": []}), ("adoption", {"enabled": True})):
        config.setdefault(key, defaults.copy())
        if not isinstance(config[key], dict) or set(config[key]) - set(defaults):
            raise ValueError("Unsupported " + key + " configuration")
        for field, value in defaults.items():
            config[key].setdefault(field, value)
    from creation_pipeline.artifacts.library import slug
    if not isinstance(config["batch"]["label"], str):
        raise ValueError("batch.label must be text")
    slug(config["batch"]["label"])
    if not isinstance(config["batch"]["tags"], list) or any(not isinstance(t, str) or not t or "|" in t or "\n" in t for t in config["batch"]["tags"]):
        raise ValueError("batch.tags must be simple text labels")
    if type(config["adoption"]["enabled"]) is not bool:
        raise ValueError("adoption.enabled must be boolean")
    sources = config.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("At least one source is required")
    ids = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError("Each source must be an object")
        if set(source) - {"id", "path", "url", "repo", "paper", "table", "ref", "sha256", "license", "storage"}:
            raise ValueError("Unsupported source field")
        if source.get("storage", "copy") not in ("copy", "reference"):
            raise ValueError("source.storage must be copy or reference")
        sid = source.setdefault("id", f"source{index + 1}")
        if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", sid) or sid in ids:
            raise ValueError("Source IDs must be unique simple identifiers")
        ids.add(sid)
        if sum(k in source for k in ("path", "url", "repo", "paper", "table")) != 1:
            raise ValueError("Each source needs exactly one path, url, repo, paper or table")
        for key in ("path", "url", "repo", "paper", "table", "ref", "sha256"):
            if key in source and (not isinstance(source[key], str) or not source[key].strip()):
                raise ValueError("Source " + key + " must be nonempty text")
        for key in ("path", "table"):
            if key in source:
                source[key] = os.path.abspath(path.parent / source[key])
    model = config.get("model", {})
    if isinstance(model, str):
        model = {"name": model}
    if not isinstance(model, dict) or set(model) - {"backend", "name", "transport", "reasoning_effort", "service_tier", "api_model", "api_connect_retries", "api_retries"}:
        raise ValueError("model supports only backend, name, transport, reasoning_effort, service_tier and api_model")
    if model.get("backend", "codex_cli") not in ("codex_cli", "deepseek_api"):
        raise ValueError("model.backend must be codex_cli (native Codex turns) or deepseek_api "
                         "(single-shot DeepSeek calls for the native stages); there is no fallback")
    if "name" in model and not isinstance(model["name"], str):
        raise ValueError("model.name must be text")
    if model.setdefault("transport", "default") not in ("default", "https"):
        raise ValueError("model.transport must be default (user provider) or https (explicit SSE)")
    for key in ("reasoning_effort", "service_tier"):
        if key in model and model[key] is not None and not re.fullmatch(r"[a-z0-9_-]{2,20}", str(model[key])):
            raise ValueError("model." + key + " must be a short lowercase token")
    if model.get("api_model") is not None and (not isinstance(model["api_model"], str)
                                               or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", model["api_model"])):
        raise ValueError("model.api_model must be a plain provider model identifier or null")
    if model.get("api_connect_retries") is not None:
        value = model["api_connect_retries"]
        if type(value) is not int or not 0 <= value <= 2:
            raise ValueError("model.api_connect_retries must be an integer between 0 and 2")
    if model.get("api_retries") is not None:
        value = model["api_retries"]
        if type(value) is not int or not 0 <= value <= 3:
            raise ValueError("model.api_retries must be an integer between 0 and 3")
    model.setdefault("backend", "codex_cli")
    config["model"] = model
    execution = config.setdefault("execution", {"profile": "production"})
    if not isinstance(execution, dict) or set(execution) - {"profile", "stop_on_runtime_failure", "progress_watch"}:
        raise ValueError("execution supports profile and stop_on_runtime_failure only")
    profile = execution.setdefault("profile", "production")
    if profile not in ("production", "development"):
        raise ValueError("execution.profile must be production or development")
    if type(execution.setdefault("stop_on_runtime_failure", False)) is not bool:
        raise ValueError("execution.stop_on_runtime_failure must be a boolean")
    if execution.setdefault("progress_watch", "terminate") not in ("observe", "terminate"):
        raise ValueError("execution.progress_watch must be observe or terminate")
    limits = {k: None for k in ("model_calls", "candidate_calls", "model_timeout", "total_seconds",
        "discovery_seconds", "agent_events", "agent_progress_timeout", "max_candidates", "max_builds", "source_bytes",
        "source_total_bytes", "source_files", "package_bytes", "network_requests", "repair_rounds")}
    limits.update(check_timeout=120, converter_timeout=60, network_timeout=60)
    # Development is an explicit opt-in preset, never a quality shortcut.
    if profile == "development":
        limits.update(model_calls=8, max_candidates=3, max_builds=1, repair_rounds=2)
    overrides = config.get("limits", {})
    if not isinstance(overrides, dict) or set(overrides) - set(limits):
        raise ValueError("Unknown limit setting")
    limits.update(overrides)
    if any(v is not None and (type(v) is not int or v < 0 or (v == 0 and k != "repair_rounds"))
           for k, v in limits.items()):
        raise ValueError("Limits must be null (disabled) or positive integers; repair_rounds may be zero")
    for k in ("network_timeout",):
        if limits[k] is None:
            raise ValueError(k + " must be a positive integer")
    config["limits"] = limits
    if type(config.get("http_only", False)) is not bool:
        raise ValueError("http_only must be a boolean")
    config.setdefault("checks", [])
    if not isinstance(config["checks"], list):
        raise ValueError("checks must be an array")
    config.setdefault("environment", {"allow": []})
    environment = config["environment"]
    if not isinstance(environment, dict) or set(environment) - {"allow"}:
        raise ValueError("environment supports only an allow list of variable names")
    if not isinstance(environment.get("allow", []), list) or any(
            not isinstance(v, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", v)
            for v in environment.get("allow", [])):
        raise ValueError("environment.allow must contain variable names, not credential values")
    config.setdefault("intent", "auto")
    if config["intent"] not in ("auto", "direct", "extension"):
        raise ValueError("intent must be auto, direct or extension")
    for test in config["checks"]:
        if not isinstance(test, dict) or not isinstance(test.get("candidate"), str) or not test["candidate"]:
            raise ValueError("Configured checks require a candidate name; autonomous builds should propose checks from sources")
    config["config_path"] = str(path)
    return config


def validate_plan(plan, require_build=True):
    if not isinstance(plan, dict):
        raise ValueError("Plan must be an object")
    required = ("name", "task", "scope", "entrypoint", "readiness") if "construction" in plan else ("name", "task", "scope", "entrypoint", "readiness", "intent", "added_behavior")
    for key in required:
        if not isinstance(plan.get(key), str) or not plan[key].strip():
            raise ValueError(f"Plan needs {key}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", plan["name"]):
        raise ValueError("Skill name must use lowercase words separated by hyphens")
    if plan["readiness"] not in ("callable", "adapter_needed", "blocked"):
        raise ValueError("Unknown readiness")
    if "construction" not in plan and plan["intent"] not in ("direct", "extension"):
        raise ValueError("Unknown packaging intent")
    for key in ("dependencies", "files", "checks", "evidence", "gaps"):
        if not isinstance(plan.get(key), list):
            raise ValueError(f"Plan needs array {key}")
    if require_build and plan["readiness"] != "blocked" and (not plan["files"] or not plan["evidence"]):
        raise ValueError("Plan must identify intended files and actual source evidence")
    return plan


def bound(value):
    """Numeric bound for internal comparisons; persisted configuration retains null."""
    return float("inf") if value is None else value


def exceeded(value, limit):
    return limit is not None and value > limit


def iterations(limit):
    import itertools
    return itertools.count() if limit is None else range(limit + 1)
