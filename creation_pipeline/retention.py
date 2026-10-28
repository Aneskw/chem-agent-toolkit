"""Registered local artifacts: archive first, then remove safe temporary copies."""
from pathlib import Path
import os
import re
import shutil
import time

from creation_pipeline.records import read_json, write_json, safe_relative, has_link, sanitized, clean_run, lease

DAY = 86400


def initialize(state):
    """Do not silently enroll pre-existing cache into automatic deletion."""
    state = Path(state).absolute()
    with lease(state, "retention-sweep"):
        path = state / "retention-cache-baseline.json"
        if not path.exists():
            existing = []
            for group in ("snapshots", "downloads", "repositories"):
                base = safe_relative(state, "cache/" + group)
                if base.exists():
                    existing += [group + "/" + p.name for p in base.iterdir()]
            write_json(path, {"unmanaged": sorted(existing)})




def active(state, build_id):
    try:
        with lease(state, build_id):
            return False
    except OSError:
        return True


def remove_registered(root, relative):
    root = Path(root).absolute()
    path = safe_relative(root, relative)
    if path.is_dir():
        if any(has_link(p) for p in path.rglob("*")):
            raise ValueError("Refusing cleanup of linked directory content")
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def mark(state, build_id, *, pinned=None, **updates):
    path = safe_relative(Path(state).absolute(), "retention/" + build_id + ".json")
    record = read_json(path) if path.exists() else {"build_id": build_id, "pinned": False}
    if pinned is not None:
        record.update(pinned=pinned, last_activity=time.time())
    record.update(updates)
    write_json(path, record)
    return record


def pin(state, build_id, value):
    with lease(state, "retention-sweep"):
        path = safe_relative(Path(state).absolute(), "retention/" + build_id + ".json")
        if not path.exists():
            raise ValueError("Unregistered historical batch; inspect/migrate explicitly before retention management")
        if active(state, build_id):
            raise ValueError("Cannot change retention of an active batch")
        return mark(state, build_id, pinned=value)


def register_cache(state, sources):
    """Register only cache units actually referenced by this build, never user inputs."""
    root = (Path(state) / "cache").absolute()
    used = set()
    for entry in sources:
        for field in ("path", "original_path"):
            path = Path(entry.get(field, "")).absolute()
            if path.is_relative_to(root):
                parts = path.relative_to(root).parts
                if len(parts) >= 2 and parts[0] in ("snapshots", "downloads", "repositories"):
                    used.add("/".join(parts[:2]))
    with lease(state, "cache-registry"):
        index_path = Path(state) / "retention-cache.json"
        index = read_json(index_path) if index_path.exists() else {}
        baseline = Path(state) / "retention-cache-baseline.json"
        unmanaged = set(read_json(baseline).get("unmanaged", [])) if baseline.exists() else set()
        for relative in used:
            safe_relative(root, relative)
            if relative not in unmanaged:
                index[relative] = time.time()
        write_json(index_path, index)
    return sorted(used)


def archive(state, output, summary, config, sources):
    """Idempotent compact archive. No cleanup until complete.json is written."""
    from creation_pipeline.artifacts.package import manifest
    state, output = Path(state).absolute(), Path(output).absolute()
    build_id = summary["build_id"]
    dest = safe_relative(state, "records/" + build_id)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "complete.json").unlink(missing_ok=True)
    write_json(dest / "input.json", sanitized({k: v for k, v in (config or {}).items() if not k.startswith("_")}))
    write_json(dest / "sources.json", sanitized(sources))
    compact = {k: v for k, v in summary.items() if k not in ("evidence", "sources", "model_metrics")}
    compact["model_metrics"] = {k: v for k, v in summary.get("model_metrics", {}).items() if k != "receipts"}
    adoption = {a["name"]: a for a in summary.get("adoption", [])}
    for entity in summary.get("entities", []):
        name = entity["name"]
        path = safe_relative(output, "records/" + name + ".json")
        if not path.exists():
            continue
        data = read_json(path)
        skill = safe_relative(dest, "skills/" + name)
        write_json(skill / "basis.json", data.get("basis", []))
        write_json(skill / "review.json", {"name": name, "status": data["status"], "checks": data.get("checks", []),
            "issues": data.get("issues", []), "error": data.get("error"), "stopped_reason": data.get("stopped_reason"),
            "repair_summary": data.get("repair_summary", []),
            "scope": data.get("plan", {}).get("scope"),
            "plan_adjustments": data.get("plan_adjustments", []),
            "acceptance_version": data.get("acceptance_version"), "acceptance_sha256": data.get("acceptance_sha256"),
            "review_context": data.get("review_context"),
            "acceptance_scope": data.get("acceptance_scope"), "files": data.get("files", [])})
        adopted = adoption.get(name, {})
        source = safe_relative(output, "bundle/skills/" + name)
        if adopted.get("status") in ("adopted", "already_present"):
            if manifest(adopted["path"]) != data["files"]:
                raise ValueError("Formal skill differs before archive: " + name)
            write_json(skill / "package.json", {"path": adopted["path"], "files": data["files"]})
            for stale in ("draft", "package"):
                if (skill / stale).exists():
                    remove_registered(skill, stale)
        elif source.exists():
            # A passed no-adopt package must remain available, not become a failed draft.
            target = skill / ("package" if data["status"] == "ready" else "draft")
            stale = "draft" if data["status"] == "ready" else "package"
            if (skill / stale).exists():
                remove_registered(skill, stale)
            (skill / "package.json").unlink(missing_ok=True)
            if target.exists():
                remove_registered(skill, target.name)
            shutil.copytree(source, target)
            if manifest(target) != data["files"]:
                raise ValueError("Archive package mismatch: " + name)
    # A process can stop before candidate metadata reaches the batch summary.
    # Preserve directly written files as unfinished drafts before any expiry cleanup.
    recorded = {e["name"] for e in summary.get("entities", [])}
    for base in (output / "bundle/skills", state / "runs" / build_id / "bundle/skills"):
        if not base.exists():
            continue
        for source in base.iterdir():
            if not source.is_dir() or source.name in recorded:
                continue
            manifest(source)  # Reject links and unsafe source trees.
            target = safe_relative(dest, "skills/" + source.name + "/draft")
            if target.exists():
                remove_registered(target.parent, "draft")
            shutil.copytree(source, target)
            if manifest(target) != manifest(source):
                raise ValueError("Interrupted draft archive mismatch")
            write_json(target.parent / "review.json", {"status": "incomplete", "reason": "Interrupted before candidate finalization"})
            recorded.add(source.name)
    write_json(dest / "summary.json", sanitized(compact))
    write_json(dest / "complete.json", {"build_id": build_id, "archived_at": time.time()})
    return dest


def sweep(state, *, dry_run=False, clock=None):
    state = Path(state).absolute()
    stamp = time.time() if clock is None else clock
    removed, skipped, warnings = [], [], []
    if has_link(state):
        raise ValueError("Linked state root")
    with lease(state, "retention-sweep"):
        registrations = []
        for path in (state / "retention").glob("*.json"):
            if has_link(path):
                raise ValueError("Linked retention record")
            record = read_json(path)
            bid = record["build_id"]
            if not isinstance(bid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", bid):
                raise ValueError("Invalid registered batch ID")
            try:
                safe_relative(state, "runs/" + bid)
            except ValueError as exc:
                warnings.append(str(exc))
                continue
            registrations.append(record)
            if record.get("pinned") or active(state, bid):
                skipped.append(bid)
                continue
            if stamp - record["last_activity"] < 7 * DAY:
                continue
            archived = safe_relative(state, "records/" + bid + "/complete.json")
            if not archived.exists():
                warnings.append("Not archived; retained: " + bid)
                continue
            try:
                with lease(state, bid):
                    for base in ("runs", "outputs"):
                        target = safe_relative(state, base + "/" + bid)
                        if target.exists():
                            if not dry_run:
                                if base == "runs":
                                    clean_run(state, bid)
                                else:
                                    remove_registered(state, base + "/" + bid)
                            removed.append(str(target))
            except (OSError, ValueError) as exc:
                warnings.append(str(exc))
        # Active runs may acquire new cache units not yet registered: defer cache GC conservatively.
        if not any(active(state, r["build_id"]) for r in registrations):
            protected = {p for r in registrations if r.get("pinned") for p in r.get("cache", [])}
            with lease(state, "cache-registry"):
                index_path = state / "retention-cache.json"
                index = read_json(index_path) if index_path.exists() else {}
                for relative, accessed in list(index.items()):
                    if relative in protected or stamp - accessed < 30 * DAY:
                        continue
                    try:
                        target = safe_relative(state / "cache", relative)
                        if not dry_run:
                            remove_registered(state / "cache", relative)
                            del index[relative]
                        removed.append(str(target))
                    except (OSError, ValueError) as exc:
                        warnings.append(str(exc))
                if not dry_run:
                    write_json(index_path, index)
    return {"removed": removed, "skipped": skipped, "warnings": warnings, "dry_run": dry_run}
