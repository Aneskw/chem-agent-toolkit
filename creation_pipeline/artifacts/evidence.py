"""Portable, immutable input snapshots and separate diagnostic records."""
import copy
import shutil
from pathlib import Path

from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import fingerprint, qualify
from creation_pipeline.records import file_digest, read_json, write_json, safe_relative, sanitized, redact, has_link


def checked_copy(source, target, expected):
    source, target = Path(source), Path(target)
    if has_link(source) or file_digest(source) != expected:
        raise ValueError("Source changed before durable snapshot")
    # Do not persist recognizable credentials even when supplied as source data.
    carry = ""
    with source.open("rb") as stream:
        for raw in iter(lambda: stream.read(1024 * 1024), b""):
            text = carry + raw.decode("utf-8", errors="ignore")
            if redact(text) != text:
                raise ValueError("Credential-like material cannot enter durable evidence")
            carry = text[-512:]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if file_digest(target) != expected:
        raise ValueError("Source changed during durable snapshot")


def seal(destination, package, record, sources, runtime_materials=None):
    """Called only after authoring/optional preparation is finished, before publication."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    frozen = copy.deepcopy(record)
    (destination / "package").mkdir()
    if package.exists():
        for item in manifest(package):
            checked_copy(safe_relative(package, item["path"]), safe_relative(destination / "package", item["path"]), item["sha256"])
    if manifest(destination / "package") != record["files"]:
        raise ValueError("Final package differs from reviewed files")
    source_refs = []
    for entry in sources:
        root = Path(entry["path"])
        for item in entry["inventory"]:
            source = root if root.is_file() else safe_relative(root, item["path"])
            checked_copy(source, safe_relative(destination / "sources", entry["id"] + "/" + item["path"]), item["sha256"])
        source_refs.append({"id": entry["id"], "path": "sources/" + entry["id"], "inventory": entry["inventory"]})
    # All actionable inputs use relative durable paths, never cache/run locators.
    write_json(destination / "sources.json", source_refs)
    if runtime_materials is not None:
        for item in manifest(runtime_materials):
            checked_copy(safe_relative(runtime_materials, item["path"]),
                         safe_relative(destination / "runtime", item["path"]), item["sha256"])
        (destination / "runtime").mkdir(exist_ok=True)
        if manifest(destination / "runtime") != record["delivery"]["inputs"]["environment"]["payload"]["materials"]:
            raise ValueError("Runtime materials changed before freeze")
    write_json(destination / "record.json", sanitized(frozen))
    write_json(destination / "freeze.json", {"version": 1, "revision_id": record["delivery"]["revision_id"],
               "files": manifest(destination)})
    return file_digest(destination / "freeze.json")


def verify(directory, freeze_sha256):
    directory = Path(directory)
    if has_link(directory) or file_digest(directory / "freeze.json") != freeze_sha256:
        raise ValueError("Evidence freeze receipt changed")
    freeze = read_json(directory / "freeze.json")
    current = [f for f in manifest(directory) if f["path"] != "freeze.json"]
    # WindowsPath and PosixPath sort case differently. Ordering is not file
    # identity; retain every path/hash/size and duplicate in the comparison.
    ordered = lambda files: sorted(files, key=lambda f: f['path'])
    if ordered(current) != ordered(freeze["files"]):
        raise ValueError("Frozen package/source/contract/evidence changed")
    record = read_json(directory / "record.json")
    delivery = record["delivery"]
    if fingerprint(delivery["inputs"]) != delivery["revision_id"][4:] or freeze["revision_id"] != delivery["revision_id"]:
        raise ValueError("Revision identity changed")
    if ordered(manifest(directory / "package")) != ordered(delivery["inputs"]["files"]):
        raise ValueError("Frozen package does not match revision")
    entries = read_json(directory / "sources.json")
    expected = {e["id"]: e["inventory"] for e in delivery["inputs"]["sources"]}
    if {e["id"]: e["inventory"] for e in entries} != expected:
        raise ValueError("Source registry differs from revision")
    for entry in entries:
        # Intake sorts relative strings; WindowsPath sorts case-insensitively.
        # Compare every path/hash/size, retaining duplicates, independently of order.
        if sorted(manifest(safe_relative(directory, entry["path"])), key=lambda f: f['path']) != sorted(
                entry["inventory"], key=lambda f: f['path']):
            raise ValueError("Durable source files differ from revision")
    environment = delivery["inputs"]["environment"]["payload"]
    if isinstance(environment, dict) and "materials" in environment:
        if ordered(manifest(directory / "runtime")) != ordered(environment["materials"]):
            raise ValueError("Frozen runtime materials differ from revision")
    qualify(delivery)
    return record
