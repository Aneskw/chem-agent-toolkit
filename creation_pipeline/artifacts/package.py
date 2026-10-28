"""File manifests, output integrity and explicit installation."""
from __future__ import annotations

import shutil
from pathlib import Path

from creation_pipeline.validation.acceptance import require_ready
from creation_pipeline.records import has_link, read_json, safe_relative, file_digest


ROLES = {"scripts", "references", "examples", "resources", "assets"}


def manifest(package):
    package = Path(package)
    if not package.is_dir() or has_link(package):
        raise ValueError("Package must be a real directory")
    result = []
    for path in sorted(package.rglob("*")):
        if has_link(path):
            raise ValueError("Runtime package contains linked paths")
        if path.is_file():
            result.append({"path": path.relative_to(package).as_posix(), "sha256": file_digest(path), "bytes": path.stat().st_size})
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
    if (Path(output) / "complete.json").exists():
        return install_archive(output, destination)
    if (Path(output) / "summary.json").exists():
        return install_bundle(output, destination)
    record, package = verify_output(output)
    require_ready(record)
    target = Path(destination).absolute() / package.name
    if has_link(target) or target.exists():
        raise ValueError("Installation destination exists or contains a linked path")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(package, target)
    if manifest(target) != record["files"]:
        raise ValueError("Installed files do not match validated manifest")
    return {"installed": str(target), "build_id": record["build_id"]}


def verify_bundle(output):
    output = Path(output).absolute()
    if has_link(output):
        raise ValueError("Linked build output")
    summary = read_json(output / "summary.json")
    bundle = output / "bundle"
    recorded = read_json(bundle / "manifest.json")
    current = [f for f in manifest(bundle) if f["path"] != "manifest.json"]
    if current != recorded["files"] or recorded["entities"] != summary["entities"]:
        raise ValueError("Bundle changed since validation")
    for entity in recorded["entities"]:
        name = entity["name"]
        path = safe_relative(output, "records/" + name + ".json")
        record = read_json(path)
        relative = ("skills/" if entity["kind"] == "skill" else "tools/") + name
        package = safe_relative(bundle, relative)
        if package.exists() and manifest(package) != record["files"]:
            raise ValueError("Entity changed since validation: " + name)
    return summary, bundle


def install_bundle(output, destination):
    summary, bundle = verify_bundle(output)
    ready = [e for e in summary["entities"] if e["status"] == "ready" and e["kind"] == "skill"]
    if not ready:
        raise ValueError("No ready skills to install")
    target = Path(destination).absolute() / summary["build_id"]
    if target.exists() or has_link(target):
        raise ValueError("Installation destination exists or contains a linked path")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True)
    try:
        for entity in ready:
            require_ready(read_json(safe_relative(Path(output), "records/" + entity["name"] + ".json")))
            relative = "skills/" + entity["name"]
            shutil.copytree(safe_relative(bundle, relative), safe_relative(target, relative))
            if manifest(safe_relative(target, relative)) != manifest(safe_relative(bundle, relative)):
                raise ValueError("Installed files differ")
    except Exception:
        shutil.rmtree(target)
        raise
    return {"installed": str(target), "skills": str(target / "skills"), "build_id": summary["build_id"]}


def archive_packages(output):
    """Resolve compact records without requiring the removed staging bundle."""
    output = Path(output).absolute()
    if has_link(output):
        raise ValueError("Linked archive")
    summary = read_json(output / "summary.json")
    packages = []
    for entity in summary.get("entities", []):
        name = entity["name"]
        root = safe_relative(output, "skills/" + name)
        if not (root / "review.json").exists():
            continue
        record = read_json(root / "review.json")
        record["basis"] = read_json(root / "basis.json")
        if (root / "package.json").exists():
            path = Path(read_json(root / "package.json")["path"])
        else:
            path = root / ("package" if record["status"] == "ready" else "draft")
        if path.exists():
            if manifest(path) != record["files"]:
                raise ValueError("Archived package changed: " + name)
            packages.append((record, path))
    return summary, packages


def install_archive(output, destination):
    summary, packages = archive_packages(output)
    selected = [(r, p) for r, p in packages if r["status"] == "ready"]
    if not selected:
        raise ValueError("No content-approved packages")
    destination = Path(destination).absolute()
    if has_link(destination):
        raise ValueError("Linked destination")
    # Validate the whole operation before copying; never overwrite existing skills.
    for record, package in selected:
        require_ready(record)
        if safe_relative(destination, record["name"]).exists():
            raise ValueError("Installation destination exists: " + record["name"])
    destination.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        for record, package in selected:
            target = safe_relative(destination, record["name"])
            created.append(target)
            shutil.copytree(package, target)
            if manifest(target) != record["files"]:
                raise ValueError("Installed files differ")
    except Exception:
        for target in created:
            if target.exists():
                shutil.rmtree(target)
        raise
    return {"installed": [str(p) for p in created], "build_id": summary["build_id"]}
