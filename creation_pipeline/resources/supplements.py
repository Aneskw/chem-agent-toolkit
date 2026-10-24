"""Known-resource acquisition and registry queries for native Agent tools."""
from pathlib import Path
import json
from creation_pipeline.records import read_json, write_json, digest


def restore(run):
    from creation_pipeline.resources.intake import Sources
    from creation_pipeline.resources.acquisition import Acquisition
    state = read_json(Path(run) / "resource-state.json")
    sources = Sources.__new__(Sources)
    sources.config, sources.limits = state["config"], state["config"]["limits"]
    sources.cache = Path(state["cache"])
    sources.acquisition = Acquisition(sources.config, sources.cache)
    sources.restore(state["sources"], state["evidence"], state["errors"])
    sources.acquisition.requests = state.get("network_requests", 0)
    return sources


def supplement(run, location, reason, ref=None):
    from creation_pipeline.resources.workspace import prepare
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
