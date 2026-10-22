"""Configuration parsing and validation, independent of model-generated prose."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path


class BlockedError(ValueError):
    pass


class ModelCallError(ValueError):
    """Transport/backend failure, not a defect in authored files."""


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
               "prompt", "constraints", "network", "execute_generated_checks"}
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
    sources = config.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("At least one source is required")
    ids = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError("Each source must be an object")
        if set(source) - {"id", "path", "url", "repo", "paper", "table", "ref", "sha256", "license"}:
            raise ValueError("Unsupported source field")
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
    config["model"] = model
    limits = {"model_calls": 40, "repair_rounds": 2, "model_timeout": 300,
              "check_timeout": 60, "source_bytes": 2_000_000, "read_lines": 160,
              "source_files": 1500, "package_bytes": 1_000_000, "total_seconds": 1800,
              "source_total_bytes": 30_000_000, "network_requests": 12, "network_timeout": 60,
              "max_candidates": 8, "max_builds": 4, "candidate_calls": 10}
    limits["view_chars"] = 12000
    overrides = config.get("limits", {})
    if not isinstance(overrides, dict) or set(overrides) - set(limits):
        raise ValueError("Unknown limit setting")
    limits.update(overrides)
    if any(type(v) is not int or v < 0 for v in limits.values()):
        raise ValueError("Limits must be nonnegative integers")
    if any(limits[k] == 0 for k in limits if k != "repair_rounds"):
        raise ValueError("Only repair_rounds may be zero")
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
    for key in ("name", "task", "scope", "entrypoint", "readiness", "intent", "added_behavior"):
        if not isinstance(plan.get(key), str) or not plan[key].strip():
            raise ValueError(f"Plan needs {key}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", plan["name"]):
        raise ValueError("Skill name must use lowercase words separated by hyphens")
    if plan["readiness"] not in ("callable", "adapter_needed", "blocked"):
        raise ValueError("Unknown readiness")
    if plan["intent"] not in ("direct", "extension"):
        raise ValueError("Unknown packaging intent")
    for key in ("dependencies", "files", "checks", "evidence", "gaps"):
        if not isinstance(plan.get(key), list):
            raise ValueError(f"Plan needs array {key}")
    if require_build and plan["readiness"] != "blocked" and (not plan["files"] or not plan["evidence"]):
        raise ValueError("Plan must identify intended files and actual source evidence")
    return plan
