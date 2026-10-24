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
               "prompt", "constraints", "execution", "network", "execute_generated_checks", "batch", "adoption"}
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
    if any(type(config[k]) is not bool for k in ("network", "execute_generated_checks")):
        raise ValueError("network and execute_generated_checks must be booleans")
    for key, defaults in (("batch", {"label": "skills", "tags": []}), ("adoption", {"enabled": True})):
        config.setdefault(key, defaults.copy())
        if not isinstance(config[key], dict) or set(config[key]) - set(defaults):
            raise ValueError("Unsupported " + key + " configuration")
        for field, value in defaults.items():
            config[key].setdefault(field, value)
    from .library import slug
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
    if not isinstance(model, dict) or set(model) - {"backend", "name", "base_url", "api_key_env", "structured"}:
        raise ValueError("Unsupported model configuration")
    model.setdefault("backend", "codex_cli")
    for key in ("name", "base_url", "api_key_env"):
        if key in model and not isinstance(model[key], str):
            raise ValueError("model." + key + " must be text")
    if "structured" in model and type(model["structured"]) is not bool:
        raise ValueError("model.structured must be boolean")
    if model["backend"] not in ("codex_cli", "chat_completions", "ollama"):
        raise ValueError("Unsupported model backend")
    if model["backend"] != "codex_cli" and not model.get("name"):
        raise ValueError("API backends require model.name")
    if "api_key_env" in model and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", model["api_key_env"]):
        raise ValueError("api_key_env must be an environment variable name")
    if model["backend"] != "codex_cli":
        raise ValueError("Only codex_cli Agent execution is supported; direct API/Ollama backends are temporarily closed")
    if set(model) & {"base_url", "api_key_env", "structured"}:
        raise ValueError("Direct API model settings are not supported by the Agent-only pipeline")
    config["model"] = model
    execution = config.setdefault("execution", {"profile": "production"})
    if not isinstance(execution, dict) or set(execution) - {"profile"}:
        raise ValueError("execution supports profile only")
    profile = execution.setdefault("profile", "production")
    if profile not in ("production", "development"):
        raise ValueError("execution.profile must be production or development")
    limits = {k: None for k in ("model_calls", "candidate_calls", "model_timeout", "total_seconds",
        "discovery_seconds", "agent_events", "max_candidates", "max_builds", "source_bytes",
        "source_total_bytes", "source_files", "package_bytes", "network_requests", "repair_rounds")}
    limits.update(check_timeout=120, converter_timeout=60, network_timeout=60, read_lines=160, view_chars=12000,
                  context_chars=160000)
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
    for k in ("network_timeout", "read_lines", "view_chars", "context_chars"):
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
