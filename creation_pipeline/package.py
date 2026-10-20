"""Verbatim model files, file manifests and explicit installation."""
from __future__ import annotations

import shutil
import os
import re
from pathlib import Path

from .records import digest, has_link, read_json, safe_relative, redact


ROLES = {"scripts", "references", "examples", "resources", "assets"}


def save_files(staging, files, max_bytes):
    if not isinstance(files, list) or not files:
        raise ValueError("Model must supply a nonempty file list")
    staging = Path(staging)
    if has_link(staging):
        raise ValueError("Linked staging directory")
    validated, total = {}, 0
    for item in files:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) for k in ("path", "content", "purpose")):
            raise ValueError("Each file needs path, content and purpose")
        path = safe_relative(staging, item["path"])
        relative = path.relative_to(staging).as_posix()
        if relative in validated or any(k.casefold() == relative.casefold() for k in validated):
            raise ValueError("Duplicate or case-colliding file")
        if relative != "SKILL.md" and (len(Path(relative).parts) < 2 or Path(relative).parts[0] not in ROLES):
            raise ValueError("Unsupported runtime file role")
        if not item["purpose"].strip() or not item["content"].strip() or "\0" in item["content"]:
            raise ValueError("Empty or binary file is not a runtime resource")
        literal = re.search(r"\b(?:sk-[\w-]{12,}|nvapi-[\w-]{12,})", item["content"])
        env_secret = any(len(v) >= 8 and re.search(r"(?i)(token|secret|password|api_?key)", k) and v in item["content"]
                         for k, v in os.environ.items())
        if literal or env_secret:
            raise ValueError("Possible credential literal in generated package; use environment variable names")
        if path.suffix.lower() in {".exe", ".dll", ".pkl", ".pt", ".pem", ".key"}:
            raise ValueError("Binary artifacts and credentials do not belong in generated packages")
        data = item["content"].encode("utf-8")
        total += len(data)
        validated[relative] = data
    if "SKILL.md" not in validated or total > max_bytes:
        raise ValueError("Package missing SKILL.md or exceeds package_bytes")
    # Replace only the registered staging contents after validating the full response.
    if staging.exists():
        for path in staging.rglob("*"):
            if has_link(path):
                raise ValueError("Staging contains a linked path")
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    for relative, data in validated.items():
        path = safe_relative(staging, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def manifest(package):
    package = Path(package)
    if not package.is_dir() or has_link(package):
        raise ValueError("Package must be a real directory")
    result = []
    for path in sorted(package.rglob("*")):
        if has_link(path):
            raise ValueError("Runtime package contains linked paths")
        if path.is_file():
            data = path.read_bytes()
            result.append({"path": path.relative_to(package).as_posix(), "sha256": digest(data), "bytes": len(data)})
    return result


def verify_output(output):
    output = Path(output).absolute()
    if has_link(output):
        raise ValueError("Build output must not contain linked paths")
    record = read_json(output / "build.json")
    package = safe_relative(output, record["package"])
    if manifest(package) != record["files"]:
        raise ValueError("Package changed since validation; rebuild/revalidate before installation")
    return record, package


def install(output, destination):
    record, package = verify_output(output)
    if record["status"] != "ready":
        raise ValueError("Only ready outputs may be installed")
    target = Path(destination).absolute() / package.name
    if has_link(target) or target.exists():
        raise ValueError("Installation destination exists or contains a linked path")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(package, target)
    if manifest(target) != record["files"]:
        raise ValueError("Installed files do not match validated manifest")
    return {"installed": str(target), "build_id": record["build_id"]}
