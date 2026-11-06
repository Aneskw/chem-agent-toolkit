"""Resolve compact source-backed writing notes without executing source code."""
from pathlib import Path


def resolve(sources, reference):
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("Source reference must be nonempty text")
    matches = []
    for item in sources.evidence:
        entry = sources.entries.get(item["source"], {})
        root = Path(entry.get("path", "."))
        original = root if root.is_file() else root / item["path"]
        aliases = {item["id"], f"{item['source']}/{item['path']}", item["path"], str(original), original.as_posix()}
        if reference in aliases or reference == entry.get("url") or reference == entry.get("repo"):
            matches.append(item)
    # URL identifies a file only when unique, never an arbitrary file in a repo.
    if len(matches) > 1:
        unique = {(m["source"], m["path"], m.get("sha256")): m for m in matches}
        matches = list(unique.values())
    if len(matches) != 1:
        raise ValueError(f"Source {reference!r} is {'ambiguous' if matches else 'unknown'}; use a registered eN or source-id/path")
    return matches[0]


def validate_basis(items, sources):
    if not isinstance(items, list) or not items:
        raise ValueError("basis must contain concise source-backed writing notes")
    normalized = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"basis[{index}] must be an object")
        for key in ("location", "claim", "source", "locator", "origin"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"basis[{index}].{key} requires text")
        source = resolve(sources, item["source"])
        normalized.append({**item, "source": source["id"], "source_path": source["path"],
                           "source_id": source["source"], "sha256": source.get("sha256")})
    return normalized
