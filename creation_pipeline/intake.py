"""Bounded source indexing and model-requested reading, with retained evidence."""
from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from pathlib import Path

from .models import BlockedError
from .records import digest, has_link, redact, safe_relative


EXCLUDED = {".git", ".pipeline", ".venv", "venv", "node_modules", "__pycache__", ".aws", ".ssh", ".codex"}
SUFFIXES = {".md", ".txt", ".rst", ".py", ".toml", ".json", ".yaml", ".yml", ".csv", ".smi", ".jsonl", ".sh", ".pdf", ".html", ".xml", ".ini", ".cfg", ".ts", ".js", ".cpp", ".h"}


def permitted(path):
    return (not any(part in EXCLUDED or part.startswith(".env") for part in path.parts)
            and not any(word in path.name.lower() for word in ("credential", "private_key", "id_rsa"))
            and (path.suffix.lower() in SUFFIXES or path.name in {"LICENSE", "Dockerfile", "Makefile"}))


class Sources:
    def __init__(self, config, cache):
        self.limits = config["limits"]
        self.entries = {}
        self.evidence = []
        self.cache = Path(cache)
        for item in config["sources"]:
            entry = dict(item)
            if "url" in item:
                url = item["url"]
                if not url.startswith("https://") or "@" in url.split("/", 3)[2]:
                    raise ValueError("Remote sources require HTTPS without embedded credentials")
                # A content hash identifies the cache object; URL alone is not immutable.
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": "task-skill-pipeline/1"})
                    with urllib.request.urlopen(request, timeout=30) as response:
                        data = response.read(self.limits["source_bytes"] + 1)
                except OSError as exc:
                    raise BlockedError(f"Cannot fetch source {item['id']}: {redact(exc)}") from exc
                if len(data) > self.limits["source_bytes"]:
                    raise BlockedError("Remote document exceeds source_bytes; supply a local source")
                sha = digest(data)
                if item.get("sha256") and item["sha256"] != sha:
                    raise ValueError("Downloaded source hash differs from configuration")
                suffix = ".pdf" if data.startswith(b"%PDF") else ".txt"
                cached = self.cache / (sha + suffix)
                cached.parent.mkdir(parents=True, exist_ok=True)
                if has_link(cached):
                    raise ValueError("Cache paths must not contain links")
                cached.write_bytes(data)
                entry["path"] = str(cached)
            root = Path(entry["path"])
            if not root.exists():
                raise BlockedError(f"Missing source: {item['id']}")
            if has_link(root):
                raise ValueError("Linked sources are not supported; provide their actual path")
            if root.is_file():
                if not permitted(Path(root.name)):
                    raise ValueError("Source file is excluded or has an unsupported type")
                data = root.read_bytes() if root.stat().st_size <= self.limits["source_bytes"] else None
                if data is None:
                    raise BlockedError("Source file exceeds source_bytes")
                sha = digest(data)
                if item.get("sha256") and sha != item["sha256"]:
                    raise ValueError("Local source hash differs from configuration")
                entry["sha256"] = sha
                entry["files"] = [root.name]
            else:
                files = []
                # Prune before descent: do not enumerate all dependencies or hidden stores.
                import os
                capped = False
                for directory, names, filenames in os.walk(root, followlinks=False):
                    names[:] = sorted(n for n in names if n not in EXCLUDED and not n.startswith(".")
                                      and not has_link(Path(directory) / n))
                    for name in sorted(filenames):
                        file = Path(directory) / name
                        relative = file.relative_to(root)
                        if permitted(relative) and not has_link(file):
                            files.append(relative.as_posix())
                            if len(files) >= self.limits["source_files"]:
                                capped = True
                                break
                    if capped:
                        break
                entry["files"] = files
                entry["index_truncated"] = capped
                proc = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
                if proc.returncode == 0:
                    entry["resolved_ref"] = proc.stdout.strip()
                    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True)
                    entry["working_tree_dirty"] = bool(dirty.stdout.strip())
                if item.get("ref"):
                    resolved = subprocess.run(["git", "-C", str(root), "rev-parse", item["ref"]], capture_output=True, text=True)
                    if resolved.returncode or resolved.stdout.strip() != entry.get("resolved_ref"):
                        raise BlockedError("Requested ref is not checked out; provide a separate checkout at that ref")
                    if entry.get("working_tree_dirty"):
                        raise BlockedError("Pinned source has uncommitted changes; provide a clean checkout")
            self.entries[item["id"]] = entry

    def index(self):
        return [{**{k: v for k, v in entry.items() if k not in ("path", "files")},
                 "files": entry["files"][:100], "index_preview_truncated": len(entry["files"]) > 100}
                for entry in self.entries.values()]

    def _file(self, sid, name):
        entry = self.entries.get(sid)
        if entry is None:
            raise ValueError("Unknown source ID")
        root = Path(entry["path"])
        if root.is_file():
            if name != root.name:
                raise ValueError("Unknown source file")
            return root
        path = safe_relative(root, name)
        if not permitted(Path(name)) or not path.is_file():
            raise ValueError("Source path is unavailable or excluded")
        return path

    def _text(self, path):
        if path.stat().st_size > self.limits["source_bytes"]:
            raise ValueError("File exceeds source_bytes; narrow the supplied source")
        data = path.read_bytes()
        if path.suffix.lower() == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise BlockedError("PDF reading needs pypdf; provide extracted text or install pypdf") from exc
            text = "\n".join(f"[page {i + 1}]\n{page.extract_text() or ''}" for i, page in enumerate(PdfReader(path).pages))
            if not text.strip():
                raise BlockedError("PDF has no extractable text; OCR is not provided")
        else:
            text = data.decode("utf-8-sig")
        return redact(text), digest(data)

    def request(self, action):
        sid, name = action.get("source"), action.get("path", "")
        start = max(1, int(action.get("start", 1)))
        offset = max(0, int(action.get("offset", 0)))
        limit = min(self.limits["read_lines"], max(1, int(action.get("limit", 80))))
        if action["action"] == "list":
            entry = self.entries[sid]
            root = Path(entry["path"])
            directory = root if not name else safe_relative(root, name)
            if has_link(directory) or not directory.is_dir():
                raise ValueError("Not a readable directory")
            files = [p.name + ("/" if p.is_dir() else "") for p in sorted(directory.iterdir())
                     if not has_link(p) and not any(part.startswith(".") or part in EXCLUDED for part in p.relative_to(root).parts)]
            return {"items": files[start - 1:start - 1 + limit], "total": len(files)}
        path = self._file(sid, name)
        text, sha = self._text(path)
        lines = text.splitlines()
        if action["action"] == "search":
            query = action.get("query", "")
            matches = []
            for i, line in enumerate(lines, 1):
                column = line.lower().find(query.lower())
                if column >= 0:
                    left = max(0, column - 100)
                    matches.append({"line": i, "column": column + 1, "text": line[left:left + 800]})
            selected, used = [], 0
            for item in matches[start - 1:start - 1 + limit]:
                if used + len(item["text"]) > self.limits["view_chars"]:
                    break
                selected.append(item)
                used += len(item["text"])
            return {"matches": selected, "total": len(matches), "sha256": sha,
                    "next_start": start + len(selected) if start - 1 + len(selected) < len(matches) else None}
        end = min(len(lines), start - 1 + limit)
        window = "\n".join(lines[start - 1:end])
        excerpt = window[offset:offset + self.limits["view_chars"]]
        record = {"source": sid, "path": name, "start": start, "end": end, "sha256": sha,
                  "offset": offset, "excerpt": excerpt, "id": f"e{len(self.evidence) + 1}",
                  "next_offset": offset + len(excerpt) if offset + len(excerpt) < len(window) else None}
        self.evidence.append(record)
        return record

    def validate_evidence(self, evidence):
        known = {item["id"]: item for item in self.evidence}
        for item in evidence:
            if (not isinstance(item, dict) or item.get("id") not in known or not item.get("claim")
                    or not known[item["id"]]["excerpt"].strip()):
                raise ValueError("Evidence must cite an actual read ID and describe the supported claim")
        return [dict(known[item["id"]], claim=item["claim"]) for item in evidence]

    def compact_evidence(self):
        seen, result = {}, []
        for item in self.evidence:
            key = (item["source"], item["path"], item["sha256"], item["start"], item["end"], item["offset"])
            if key in seen:
                result.append({k: v for k, v in item.items() if k != "excerpt"} | {"excerpt_ref": seen[key]})
            else:
                seen[key] = item["id"]
                result.append(item)
        return result

    def manifest(self):
        return [{k: v for k, v in entry.items() if k != "files"} for entry in self.entries.values()]
