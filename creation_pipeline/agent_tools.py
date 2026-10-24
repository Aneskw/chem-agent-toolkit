"""Small native-Agent helpers; no model calls, package installation or search."""
from pathlib import Path
import argparse
import base64
import json
import sys
import uuid

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "creation_pipeline"

from .records import read_json, write_json, safe_relative, has_link, digest, sanitized
from .package import manifest, ROLES
from .models import exceeded


def inside(run, path):
    root, target = Path(run).resolve(), Path(path).absolute()
    if has_link(target) or not target.resolve().is_relative_to(root):
        raise ValueError("Helper target must be an unlinked path inside this run")
    return target


def restore(run):
    from .intake import Sources
    from .acquisition import Acquisition
    state = read_json(Path(run) / "resource-state.json")
    sources = Sources.__new__(Sources)
    sources.config, sources.limits = state["config"], state["config"]["limits"]
    sources.cache = Path(state["cache"])
    sources.acquisition = Acquisition(sources.config, sources.cache)
    sources.restore(state["sources"], state["evidence"], state["errors"])
    sources.acquisition.requests = state.get("network_requests", 0)
    return sources


def supplement(run, location, reason, ref=None):
    from .workspace import prepare
    if not reason.strip():
        raise ValueError("Supplement needs a concrete uncertainty/reason")
    run = Path(run).resolve()
    lock = run / ".resource.lock"
    with lock.open("x") as handle:
        handle.close()
        try:
            sources = restore(run)
            identity = json.dumps([location, ref], sort_keys=True)
            sid = "supplement-" + digest(identity.encode())[:16]
            if sid in sources.entries:
                return {"status": "cached", "source": sid, "resource_index": str(run / "resources.json")}
            item = dict(location, id=sid)
            if ref:
                item["ref"] = ref
            try:
                sources.add(item)
                sources.entries[sid]["acquisition_reason"] = reason
                result = {"status": "acquired", "source": sid}
            except Exception as exc:
                sources.errors.append({"source": sid, "reason": reason, "error": str(exc)})
                result = {"status": "unavailable", "source": sid, "error": str(exc)}
            prepare(sources, run)
            return {**result, "resource_index": str(run / "resources.json")}
        finally:
            lock.unlink(missing_ok=True)


def validate_package(package, limit=None):
    package = Path(package)
    files = manifest(package)
    if not any(f["path"] == "SKILL.md" for f in files):
        raise ValueError("Missing SKILL.md")
    if exceeded(sum(f["bytes"] for f in files), limit):
        raise ValueError("Package exceeds explicit package_bytes limit")
    for f in files:
        parts = Path(f["path"]).parts
        if f["path"] != "SKILL.md" and (len(parts) < 2 or parts[0] not in ROLES):
            raise ValueError("Unsupported file role: " + f["path"])
        from .intake import exclusion
        if exclusion(Path(f["path"])):
            raise ValueError("Excluded runtime file: " + f["path"])
        if f["path"] == "SKILL.md" and not f["bytes"]:
            raise ValueError("Empty SKILL.md")
        if Path(f["path"]).suffix.lower() in {".md", ".py", ".txt", ".json", ".yaml", ".yml", ".sh"}:
            import re
            carry = ""
            with (package / f["path"]).open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    text = carry + chunk.decode("utf-8", errors="ignore")
                    if re.search(r"\b(?:sk-[\w-]{12,}|nvapi-[\w-]{12,})", text):
                        raise ValueError("Possible credential literal in " + f["path"])
                    import os
                    if any(len(v) >= 8 and re.search(r"(?i)(token|secret|password|api_?key)", k) and v in text for k, v in os.environ.items()):
                        raise ValueError("Environment credential literal in " + f["path"])
                    carry = text[-256:]
    return files


def finish(run, package, token, metadata=None):
    phase_path = Path(run) / "active-phase.json"
    if phase_path.exists() and read_json(phase_path)["phase"] != "author":
        raise ValueError("Only the author stage may finalize runtime packages")
    package = inside(run, package)
    state = read_json(Path(run) / "resource-state.json")
    data = read_json(inside(run, metadata)) if metadata else {}
    for key in ("tests", "issues", "notes"):
        data.setdefault(key, [])
        if not isinstance(data[key], list):
            raise ValueError(key + " must be an array")
    for test in data["tests"]:
        from .runtime import validate_test
        validate_test(test)
        if not test.get("evidence") or not test.get("purpose"):
            raise ValueError("Checks need source evidence and purpose")
    for issue in data["issues"]:
        if not isinstance(issue, dict) or type(issue.get("blocking")) is not bool or not issue.get("description"):
            raise ValueError("Issues need description and blocking boolean")
    data.update(completed=True, token=token, package=str(package),
                files=validate_package(package, state["config"]["limits"]["package_bytes"]))
    path = safe_relative(Path(run), "deliveries/" + package.name + ".json")
    write_json(path, sanitized(data))
    return {"status": "saved", "delivery": str(path), "files": len(data["files"])}


def delivered(run, package, token):
    path = safe_relative(Path(run), "deliveries/" + Path(package).name + ".json")
    if not path.exists():
        return None
    data = read_json(path)
    if data.get("completed") and data.get("token") == token and data.get("files") == manifest(package):
        return data
    return None


def write_chunk(package, relative, encoded, append=False):
    root = Path(package).absolute()
    registered = next((p for p in (root, *root.parents) if (p / "resource-state.json").is_file()), None)
    if registered is None:
        raise ValueError("Chunk writer requires a registered run workspace")
    inside(registered, root)
    phase = read_json(registered / "active-phase.json").get("phase") if (registered / "active-phase.json").exists() else None
    if phase in ("discovery", "review") and root.is_relative_to(registered / "bundle"):
        raise ValueError("This stage must not write official skill files")
    # Package path comes from the supplied run context; symlink escapes are refused.
    target = safe_relative(root, relative)
    raw = base64.b64decode(encoded, validate=True)
    raw.decode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    if append:
        with target.open("ab") as stream:
            stream.write(raw)
    else:
        temporary = target.with_name(target.name + ".writing")
        temporary.write_bytes(raw)
        temporary.replace(target)
    return {"path": str(target), "bytes": target.stat().st_size}


def check(run, package, definition):
    from .runtime import execute
    sources = restore(run)
    package = inside(run, package)
    test = read_json(inside(run, definition))
    before = manifest(package)
    if not sources.config["execute_generated_checks"]:
        report = {"name": test.get("name", "agent-check"), "status": "not_run", "required": False,
                  "findings": ["Generated execution is disabled"]}
    else:
        report = execute(test, package, sources, Path(run) / "agent-checks" / uuid.uuid4().hex,
                         sources.limits["check_timeout"], sources.config["environment"].get("allow", []))
        if before != manifest(package):
            raise ValueError("Check changed delivered files")
        sources.verify()
    report.update(origin="review_agent", package=str(package), files=before, definition=test,
                  signature=digest(json.dumps(test, sort_keys=True).encode()), verification_id=uuid.uuid4().hex)
    with (Path(run) / "agent-checks.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(sanitized(report), ensure_ascii=False) + "\n")
    return report



def save_candidate(run, definition):
    candidate = read_json(inside(run, definition))
    from .analyze import normalize
    from .models import validate_plan
    normalized = normalize({"candidates": [candidate]})["candidates"][0]
    validate_plan(normalized)
    sources = restore(run)
    sources.validate_evidence(candidate["evidence"])
    target = safe_relative(Path(run), "candidates/" + candidate["name"] + ".json")
    write_json(target, candidate)
    return {"status": "saved", "candidate": candidate["name"]}


def inventory(run, query="", source=None, limit=30, offset=0):
    if limit < 1 or offset < 0:
        raise ValueError("Inventory limit must be positive; offset nonnegative")
    document = read_json(Path(run) / "resources.json")
    entries = [e for e in document["files"] if (not source or e["source"] == source)
               and query.lower() in e["path"].lower()]
    end = offset + limit
    return {"items": entries[offset:end], "total": len(entries),
            "next_offset": end if end < len(entries) else None,
            "note": "Display pagination only; all retained originals remain accessible"}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("inventory")
    p.add_argument("--run", required=True)
    p.add_argument("--query", default="")
    p.add_argument("--source")
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--offset", type=int, default=0)
    p = commands.add_parser("candidate")
    p.add_argument("--run", required=True)
    p.add_argument("--definition", required=True)
    p = commands.add_parser("supplement")
    p.add_argument("--run", required=True)
    locations = p.add_mutually_exclusive_group(required=True)
    for key in ("url", "repo", "paper"):
        locations.add_argument("--" + key)
    p.add_argument("--reason", required=True)
    p.add_argument("--ref")
    p = commands.add_parser("write")
    p.add_argument("--package", required=True)
    p.add_argument("--path", required=True)
    p.add_argument("--base64", required=True)
    p.add_argument("--append", action="store_true")
    p = commands.add_parser("finish")
    for key in ("run", "package", "token"):
        p.add_argument("--" + key, required=True)
    p.add_argument("--metadata")
    p = commands.add_parser("check")
    for key in ("run", "package", "definition"):
        p.add_argument("--" + key, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            result = inventory(args.run, args.query, args.source, args.limit, args.offset)
        elif args.command == "candidate":
            result = save_candidate(args.run, args.definition)
        elif args.command == "supplement":
            result = supplement(args.run, {k: getattr(args, k) for k in ("url", "repo", "paper") if getattr(args, k)}, args.reason, args.ref)
        elif args.command == "write":
            result = write_chunk(args.package, args.path, args.base64, args.append)
        elif args.command == "finish":
            result = finish(args.run, args.package, args.token, args.metadata)
        else:
            result = check(args.run, args.package, args.definition)
        print(json.dumps(sanitized(result), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
