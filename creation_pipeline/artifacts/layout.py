"""Caller-owned, frozen file paths; model review cannot waive a layout obligation.

The prose grammar is deliberately finite. Explicit file lists and root-file
requirements are compiled locally; other wording remains subject to content
review. Structured constraints.delivery_layout covers arbitrary file names.
"""
from __future__ import annotations

import json
import re
from pathlib import PurePosixPath, PureWindowsPath


def _path(value):
    if (not isinstance(value, str) or not value or value != value.strip()
            or "\\" in value or ":" in value or any(ord(c) < 32 for c in value)
            or PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()
            or any(p in {"", ".", ".."} for p in value.split("/"))
            or any(p.endswith((".", " ")) or PureWindowsPath(p).is_reserved() for p in value.split("/"))
            or any(c in value for c in "*?<>|")):
        raise ValueError("Delivery layout needs literal package-relative file paths: " + repr(value))
    from creation_pipeline.resources.intake import exclusion
    if exclusion(PurePosixPath(value)):
        raise ValueError("Delivery layout requires an excluded file: " + value)
    return value


def _list(text, field):
    # Sentence periods are terminators; periods within a file name are not.
    text = re.split(r"\.(?=\s|$)|[。；;\r\n]", text, maxsplit=1)[0].strip()
    text = re.sub(r"^(?:(?:two|three|four|five|\d+)\s+)?files?\s*:\s*", "", text, flags=re.I)
    result = []
    for token in re.split(r",\s*(?:and\s+)?|\s+and\s+|[、，]|以及|和|及", text):
        token = token.strip()
        if not token:
            continue
        quoted = len(token) >= 2 and token[0] == token[-1] and token[0] in "`\"'"
        value = token[1:-1] if quoted else token
        if not quoted and re.search(r"\s", value):
            raise ValueError("delivery_layout_unresolved at " + field
                             + ": expected a literal file list; actual=" + repr(text))
        result.append(_path(value))
    if not result or len(result) != len(set(result)):
        raise ValueError("delivery_layout_unresolved at " + field + ": empty or duplicate file list")
    return result


# Do not infer a required location from a mere mention of a dependency/source.
_EXACT = re.compile(r"\b(?:deliver|ship|package)\s+(?:exactly|only)\s+([^;\r\n]+)", re.I)
_REQUIRED = re.compile(r"\brequired\s+(?:delivered\s+)?files\s*:\s*([^;\r\n]+)", re.I)
_CHINESE_EXACT = re.compile(r"(?:交付|打包)(?:文件)?(?:仅包含|必须恰好包含|恰好包含)\s*[:：]?\s*([^；;。\r\n]+)")
_ROOT = re.compile(
    r"(?P<path>`[^`\n]+`|\"[^\"\n]+\"|'[^'\n]+'|[\w./-]+)\s+"
    r"(?:must\s+be|is\s+required|shall\s+be)\s+(?:located\s+)?(?:at|in)\s+"
    r"(?:the\s+)?package\s+root\b", re.I)
_CHINESE_ROOT = re.compile(r"(?P<path>`[^`\n]+`|[\w./-]+)\s*(?:必须|须)(?:位于|放在)包根(?:目录)?")


def _compile(inputs):
    # Record caller obligations only. The existing package validator independently
    # requires SKILL.md; lower-level runtime artifacts need not be Skill packages.
    required, exact, origins = set(), None, {}
    def add(paths, origin, exclusive=False):
        nonlocal exact
        paths = set(paths)
        if exclusive:
            if exact is not None and exact != paths:
                raise ValueError("Conflicting exact delivery file lists: " + str(origin))
            exact = paths
        required.update(paths)
        for path in paths:
            origins.setdefault(path, []).append(origin)

    seen = set()
    for item in inputs:
        if (not isinstance(item, dict) or not isinstance(item.get("field"), str)
                or item["field"] in seen or set(item) not in ({"field", "text"}, {"field", "value"})):
            raise ValueError("Invalid delivery layout input snapshot")
        field = item["field"]
        seen.add(field)
        if "value" in item:
            value = item["value"]
            if (not isinstance(value, dict) or set(value) - {"required_files", "exact_files"}
                    or not value):
                raise ValueError(field + " supports required_files and/or exact_files")
            for key, paths in value.items():
                if not isinstance(paths, list) or not paths or len(paths) != len(set(map(str, paths))):
                    raise ValueError(field + "." + key + " needs a nonempty unique file list")
                add([_path(p) for p in paths], {"field": field + "." + key, "value": paths}, key == "exact_files")
            continue
        text = item["text"]
        if not isinstance(text, str):
            raise ValueError("Delivery layout input must be text: " + field)
        for pattern, exclusive in ((_EXACT, True), (_CHINESE_EXACT, True), (_REQUIRED, False)):
            for match in pattern.finditer(text):
                add(_list(match[1], field), {"field": field, "quote": match[0]}, exclusive)
        for pattern in (_ROOT, _CHINESE_ROOT):
            for match in pattern.finditer(text):
                path = _path(match["path"].strip("`\"'"))
                if "/" in path:
                    raise ValueError("Conflicting package-root requirement at " + field + ": " + match[0])
                add([path], {"field": field, "quote": match[0]})
    if exact is not None and required - exact:
        raise ValueError("Exact delivery list excludes required paths: " + str(sorted(required - exact)))
    if len({p.casefold() for p in required}) != len(required):
        raise ValueError("Delivery layout has case-colliding required paths: " + str(sorted(required)))
    for path in required:
        if any(str(parent) in required for parent in PurePosixPath(path).parents):
            raise ValueError("Required delivery file is also a parent directory: " + path)
    return {"schema": 1, "inputs": inputs, "required_files": sorted(required),
            "exact_files": sorted(exact) if exact is not None else None, "origins": origins}


def extract(config, name=None):
    """Compile original caller text, never author/planner paraphrases or metadata."""
    inputs = []
    def visit(field, value):
        if field == "constraints.delivery_layout":
            inputs.append({"field": field, "value": value})
        elif isinstance(value, str):
            inputs.append({"field": field, "text": value})
        elif isinstance(value, dict):
            for key in sorted(value):
                visit(field + "." + key, value[key])
        elif isinstance(value, list):
            for index, entry in enumerate(value):
                visit(field + "." + str(index), entry)
    for key in ("prompt", "task", "constraints", "notes"):
        if key in config:
            visit(key, config[key])
    for prefix, spec in (("runtime_defaults", config.get("runtime_defaults", {})),
                         ("runtime." + str(name), config.get("runtime", {}).get(name, {}))):
        for key in ("requirements", "constraints", "skill_contract"):
            if key in spec:
                visit(prefix + "." + key, spec[key])
    return _compile(inputs)


def validate(payload):
    if not isinstance(payload, dict) or payload != _compile(payload.get("inputs", [])):
        raise ValueError("Delivery layout contract differs from its original requirement snapshots")
    return payload


def problems(files, payload):
    validate(payload)
    paths = {f["path"] for f in files}
    findings = []
    for path in sorted(set(payload["required_files"]) - paths):
        findings.append({"code": "required_delivery_file_missing", "path": path,
            "expected": {"path": path, "kind": "file", "present": True, "case": "exact"},
            "actual": {"present": False, "other_paths": sorted(p for p in paths
                if PurePosixPath(p).name.casefold() == PurePosixPath(path).name.casefold()),
                "delivered_paths": sorted(paths)}, "sources": payload["origins"].get(path, [])})
    if payload["exact_files"] is not None:
        for path in sorted(paths - set(payload["exact_files"])):
            findings.append({"code": "unexpected_delivery_file", "path": path,
                "expected": {"present": False, "allowed_paths": payload["exact_files"]},
                "actual": {"present": True, "path": path},
                "sources": [s for values in payload["origins"].values() for s in values]})
    return findings


def require(files, payload):
    findings = problems(files, payload)
    if findings:
        raise ValueError("Delivery layout mismatch: " + json.dumps(findings, ensure_ascii=False, sort_keys=True))
