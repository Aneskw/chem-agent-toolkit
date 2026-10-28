"""File manifests, output integrity and explicit installation."""
from __future__ import annotations

import shutil
from pathlib import Path

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


def install(output, destination):
    if (Path(output) / "summary.json").exists():
        return install_bundle(output, destination)
    raise ValueError("Only integrated, frozen and qualified outputs may be installed; legacy approval is not inherited")


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
        from creation_pipeline.artifacts.evidence import verify
        ref = record["durable_evidence"]
        frozen = verify(safe_relative(output, ref["path"]), ref["freeze_sha256"])
        if frozen["delivery"] != record["delivery"] or record["status"] != entity["status"]:
            raise ValueError("Entity result differs from frozen delivery")
        relative = ("skills/" if entity["kind"] == "skill" else "tools/") + name
        package = safe_relative(bundle, relative)
        if package.exists() and manifest(package) != record["files"]:
            raise ValueError("Entity changed since validation: " + name)
    return summary, bundle


def install_bundle(output, destination):
    summary, bundle = verify_bundle(output)
    ready = [e for e in summary["entities"] if e["status"] == "ready" and e["kind"] == "skill"]
    from creation_pipeline.contracts import qualify
    for entity in ready:
        record = read_json(safe_relative(Path(output), "records/" + entity["name"] + ".json"))
        ref = record['durable_evidence']
        if (record['delivery']['inputs']['requirement']['status'] == 'required'
                and record.get('execution_location') != str(Path(output).resolve())):
            raise ValueError('Executable output moved or has no location binding; explicitly revalidate via the durable library')
        if not qualify(record['delivery'], runtime_root=Path(output), runtime_ref=record.get('runtime'),
                       frozen_directory=safe_relative(Path(output), ref['path']), freeze_sha256=ref['freeze_sha256'])[0]:
            raise ValueError("Recorded ready status is not formal delivery qualification")
    if not ready:
        raise ValueError("No ready skills to install")
    target = Path(destination).absolute() / summary["build_id"]
    if target.exists() or has_link(target):
        raise ValueError("Installation destination exists or contains a linked path")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True)
    try:
        for entity in ready:
            relative = "skills/" + entity["name"]
            shutil.copytree(safe_relative(bundle, relative), safe_relative(target, relative))
            if manifest(safe_relative(target, relative)) != manifest(safe_relative(bundle, relative)):
                raise ValueError("Installed files differ")
            record = read_json(safe_relative(Path(output), 'records/' + entity['name'] + '.json'))
            if record.get('runtime'):
                from creation_pipeline.runtime.installation import install_envelope
                install_envelope(Path(output), record['durable_evidence']['path'], record['runtime']['path'], target / 'runtime' / entity['name'])
    except Exception:
        shutil.rmtree(target)
        raise
    return {"installed": str(target), "skills": str(target / "skills"), "build_id": summary["build_id"]}
