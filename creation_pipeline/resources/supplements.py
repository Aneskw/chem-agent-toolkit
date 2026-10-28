"""Known-resource acquisition and registry queries for native Agent tools."""
from pathlib import Path
import json
from creation_pipeline.records import read_json, write_json, digest, now, file_digest, has_link, lease


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


def supplement(run, location, reason, ref=None, related_to=None):
    from creation_pipeline.resources.workspace import prepare
    if not reason.strip():
        raise ValueError("Supplement needs a concrete uncertainty/reason")
    run = Path(run).resolve()
    with lease(run, "resources"):
        sources = restore(run)
        anchors = anchors_for(sources, related_to)
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
            sources.entries[sid].update(supplemental=True, related_to=anchors, acquired_at=now())
            result = {"status": "acquired", "source": sid}
        except Exception as exc:
            sources.errors.append({"source": sid, "reason": reason, "error": str(exc)})
            result = {"status": "unavailable", "source": sid, "error": str(exc)}
        prepare(sources, run)
        return {**result, "resource_index": str(run / "resources.json")}


def anchors_for(sources, requested=None):
    anchors = [sid for sid, entry in sources.entries.items() if not entry.get("supplemental") and not entry.get("acquisition_reason")]
    selected = anchors if requested is None else requested
    if not selected or not isinstance(selected, list) or any(s not in anchors for s in selected):
        raise ValueError("Supplement needs related_to IDs from the original input sources")
    return selected


def register(run, definition):
    """Preserve Agent-acquired content; a URL alone never creates source evidence."""
    from creation_pipeline.artifacts.delivery import inside
    from creation_pipeline.resources.acquisition import https_url
    from creation_pipeline.resources.workspace import prepare
    run = Path(run).resolve()
    data = read_json(inside(run, definition))
    for key in ("url", "reason", "path"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError("Registered resource needs " + key)
    https_url(data["url"])
    source = inside(run, data["path"])
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError("Register a saved nonempty file, not a URL/search snippet")
    with lease(run, "resources"):
        sources = restore(run)
        if not sources.config["network"]:
            raise ValueError("Remote resource registration is disabled by network=false")
        anchors = anchors_for(sources, data.get("related_to", []))
        sid = "supplement-" + digest((data["url"] + file_digest(source)).encode())[:16]
        if sid not in sources.entries:
            sources.add({"id": sid, "path": str(source)})
            sources.entries[sid].update(supplemental=True, related_to=anchors,
                acquisition_reason=data["reason"], url=data["url"], acquired_at=now(),
                version=data.get("version", ""), representation=data.get("representation", "saved_content"))
        prepare(sources, run)
        return {"status": "registered", "source": sid, "resource_index": str(run / "resources.json")}


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
