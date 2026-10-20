"""Configuration parsing and validation, independent of model-generated prose."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path


class BlockedError(ValueError):
    pass


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
    allowed = {"task", "sources", "model", "limits", "checks", "environment", "intent", "notes", "http_only"}
    unknown = set(config) - allowed
    if unknown:
        raise ValueError(f"Unknown configuration fields: {sorted(unknown)}")
    if not isinstance(config.get("task"), str) or not config["task"].strip():
        raise ValueError("A nonempty task is required")
    sources = config.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("At least one source is required")
    ids = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError("Each source must be an object")
        if set(source) - {"id", "path", "url", "ref", "sha256", "license"}:
            raise ValueError("Unsupported source field")
        sid = source.setdefault("id", f"source{index + 1}")
        if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", sid) or sid in ids:
            raise ValueError("Source IDs must be unique simple identifiers")
        ids.add(sid)
        if ("path" in source) == ("url" in source):
            raise ValueError("Each source needs exactly one path or url")
        if "path" in source:
            source["path"] = os.path.abspath(path.parent / source["path"])
    limits = {"model_calls": 16, "repair_rounds": 2, "model_timeout": 300,
              "check_timeout": 60, "source_bytes": 2_000_000, "read_lines": 160,
              "source_files": 1500, "package_bytes": 1_000_000, "total_seconds": 1800}
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
    config.setdefault("intent", "direct")
    if config["intent"] not in ("direct", "extension"):
        raise ValueError("intent must be direct or extension")
    config["config_path"] = str(path)
    return config


def validate_plan(plan):
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
    if plan["readiness"] != "blocked" and (not plan["files"] or not plan["evidence"]):
        raise ValueError("Plan must identify intended files and actual source evidence")
    return plan
