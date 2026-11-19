"""Known-resource acquisition and registry queries for native Agent tools."""
from pathlib import Path
from http.client import HTTPException
import json
import ssl
import subprocess
from urllib.error import URLError
from creation_pipeline.models import BlockedError
from creation_pipeline.resources.acquisition import SourceContentError
from creation_pipeline.records import read_json, write_json, digest, now, file_digest, has_link, lease


class SourceHandoffError(ValueError):
    """A committed inbox item needs Agent repair, not connection troubleshooting."""


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


def relate(entry, anchors, reason):
    """Cache reuse must retain each original input's acquisition purpose."""
    entry["related_to"] = sorted(set(entry.get("related_to", [])) | set(anchors))
    uses = entry.setdefault("acquisition_uses", [])
    use = {"related_to": sorted(anchors), "reason": reason}
    if use not in uses:
        uses.append(use)


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
            relate(sources.entries[sid], anchors, reason)
            prepare(sources, run)
            return {"status": "cached", "source": sid, "resource_index": str(run / "resources.json")}
        item = dict(location, id=sid)
        if ref:
            item["ref"] = ref
        before_bytes = sources.total_bytes
        try:
            sources.add(item)
            sources.entries[sid]["acquisition_reason"] = reason
            sources.entries[sid].update(supplemental=True, related_to=anchors, acquired_at=now())
            relate(sources.entries[sid], anchors, reason)
            result = {"status": "acquired", "source": sid}
        except (URLError, TimeoutError, ConnectionError, ssl.SSLError, HTTPException,
                subprocess.SubprocessError, BlockedError, SourceContentError) as exc:
            # Input mistakes, local filesystem failures and programming errors
            # propagate to the helper's error response, never remote-unavailable.
            kind = ("content" if isinstance(exc, SourceContentError) else
                    "constraint" if isinstance(exc, BlockedError) else
                    "acquisition" if isinstance(exc, subprocess.SubprocessError) else "transport")
            sources.total_bytes = before_bytes
            failure = {"error": str(exc), "error_kind": kind}
            sources.errors.append({"source": sid, "reason": reason, **failure})
            result = {"status": "unavailable", "source": sid, **failure}
        prepare(sources, run)
        return {**result, "resource_index": str(run / "resources.json")}


def anchors_for(sources, requested=None):
    anchors = [sid for sid, entry in sources.entries.items() if not entry.get("supplemental") and not entry.get("acquisition_reason")]
    selected = anchors if requested is None else requested
    if requested is None and len(anchors) != 1:
        raise ValueError("Multiple original inputs: supply explicit related_to IDs")
    if not selected or not isinstance(selected, list) or any(s not in anchors for s in selected):
        raise ValueError("Supplement needs related_to IDs from the original input sources")
    return selected


def register(run, definition):
    """Preserve Agent-acquired content; a URL alone never creates source evidence."""
    from creation_pipeline.artifacts.delivery import inside
    from creation_pipeline.resources.acquisition import https_url
    from creation_pipeline.resources.workspace import prepare
    run = Path(run).resolve()
    definition = Path(definition)
    data = read_json(inside(run, definition if definition.is_absolute() else run / definition))
    for key in ("url", "reason", "path"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError("Registered resource needs " + key)
    https_url(data["url"])
    source_path = Path(data["path"])
    source = inside(run, source_path if source_path.is_absolute() else run / source_path)
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError("Register a saved nonempty file, not a URL/search snippet")
    with lease(run, "resources"):
        sources = restore(run)
        if not sources.config["network"]:
            raise ValueError("Remote resource registration is disabled by network=false")
        anchors = anchors_for(sources, data.get("related_to", []))
        sid = "supplement-" + digest((data["url"] + file_digest(source)).encode())[:16]
        representation = data.get("representation", "saved_content")
        if representation not in ("saved_content", "excerpt"):
            raise ValueError("representation must be saved_content or excerpt")
        if not isinstance(data.get("version", ""), str):
            raise ValueError("version must be text when supplied")
        if sid not in sources.entries:
            sources.add({"id": sid, "path": str(source)})
            sources.entries[sid].update(supplemental=True, related_to=anchors,
                acquisition_reason=data["reason"], url=data["url"], acquired_at=now(),
                version=data.get("version", ""), representation=representation)
        entry = sources.entries[sid]
        if entry.get("version") and data.get("version") and entry["version"] != data["version"]:
            raise ValueError("Same source content has conflicting version claims; clarify the saved evidence")
        if data.get("version"):
            entry["version"] = data["version"]
        relate(entry, anchors, data["reason"])
        aliases = entry.setdefault("acquired_paths", [])
        for alias in (str(source), str(source.relative_to(run))):
            if alias not in aliases:
                aliases.append(alias)
        prepare(sources, run)
        return {"status": "registered", "source": sid, "resource_index": str(run / "resources.json")}


def receive(run):
    """Ingest committed native evidence before any source-reference validation.

    The content is written first; only *.source.json files are commit markers.
    Receipts avoid repeated snapshot work and are invalidated by content edits.
    """
    from creation_pipeline.artifacts.delivery import inside
    run = Path(run).resolve()
    inbox = inside(run, run / "research/inbox")
    if not inbox.exists():
        return {"status": "received", "sources": []}
    with lease(run, "research-inbox"):
        receipt_path = run / "research/receipts.json"
        receipts = read_json(receipt_path) if receipt_path.exists() else {}
        results, errors = [], []
        for definition in sorted(inbox.glob("*.source.json")):
            key = definition.name
            try:
                data = read_json(inside(run, definition))
                content = Path(data["path"])
                content = inside(run, content if content.is_absolute() else run / content)
                signature = digest((file_digest(definition) + file_digest(content)).encode())
                if receipts.get(key, {}).get("signature") == signature:
                    results.append(receipts[key]["result"])
                    continue
                result = register(run, definition)
                receipts[key] = {"signature": signature, "result": result}
                results.append(result)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append({"definition": str(definition), "error": str(exc)})
        write_json(receipt_path, receipts)
        if errors:
            raise SourceHandoffError("Repair committed research sidecars: " + json.dumps(errors))
        return {"status": "received", "sources": results}


def inventory(run, query="", source=None, limit=30, offset=0):
    if limit < 1 or offset < 0:
        raise ValueError("Inventory limit must be positive; offset nonnegative")
    receive(run)
    document = read_json(Path(run) / "resources.json")
    entries = [e for e in document["files"] if (not source or e["source"] == source)
               and query.lower() in e["path"].lower()]
    end = offset + limit
    return {"items": entries[offset:end], "total": len(entries),
            "next_offset": end if end < len(entries) else None,
            "note": "Display pagination only; all retained originals remain accessible"}
