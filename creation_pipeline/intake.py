"""Bounded source indexing and model-requested reading, with retained evidence."""
from __future__ import annotations

import json
import re
import subprocess
import shutil
import urllib.request
from pathlib import Path

from .models import BlockedError
from .acquisition import Acquisition
from .documents import read_text
from .records import digest, has_link, redact, safe_relative


EXCLUDED = {".git", ".pipeline", ".venv", "venv", "node_modules", "__pycache__", ".aws", ".ssh", ".codex"}
SUFFIXES = {".md", ".txt", ".rst", ".py", ".toml", ".json", ".yaml", ".yml", ".csv", ".smi", ".jsonl", ".sh", ".pdf", ".html", ".xml", ".ini", ".cfg", ".ts", ".js", ".cpp", ".h", ".htm", ".docx", ".ipynb", ".tsv", ".sql", ".sqlite", ".sqlite3", ".db", ".xyz", ".mol", ".sdf", ".pdb", ".smarts"}


def permitted(path):
    return (not any(part in EXCLUDED or part.startswith(".env") for part in path.parts)
            and not any(word in path.name.lower() for word in ("credential", "private_key", "id_rsa"))
            and (path.suffix.lower() in SUFFIXES or path.name in {"LICENSE", "Dockerfile", "Makefile"}))


class Sources:
    def __init__(self, config, cache):
        self.config, self.limits = config, config["limits"]
        self.entries, self.evidence, self.errors = {}, [], []
        self.cache = Path(cache).absolute()
        if has_link(self.cache):
            raise ValueError("Linked source cache")
        self.acquisition = Acquisition(config, self.cache)
        self.total_bytes = 0
        for item in config["sources"]:
            if "table" in item:
                expanded, errors = self.acquisition.expand_table(item)
                self.errors.extend(errors)
            else:
                expanded = [item]
            for source in expanded:
                try:
                    self.add(source)
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    self.errors.append({"source": source["id"], "error": redact(exc)})
        if not self.entries:
            raise BlockedError("No readable sources: " + str(self.errors)[:2000])

    def add(self, item):
        sid = item["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", sid) or sid in self.entries:
            raise ValueError("Duplicate or invalid source ID")
        entry = self.acquisition.prepare(item)
        root = Path(entry["path"]).absolute()
        if not root.exists() or has_link(root):
            raise BlockedError("Missing source or linked path: " + sid)
        original = str(root)
        files, capped = [], False
        if root.is_file():
            if not permitted(Path(root.name)):
                raise ValueError("Unsupported source file type")
            files = [root.name]
        else:
            import os
            for directory, names, filenames in os.walk(root, followlinks=False):
                names[:] = sorted(n for n in names if n not in EXCLUDED and not n.startswith(".")
                                  and not has_link(Path(directory) / n))
                for name in sorted(filenames):
                    file = Path(directory) / name
                    relative = file.relative_to(root)
                    if permitted(relative) and not has_link(file):
                        if file.stat().st_size > self.limits["source_bytes"]:
                            self.errors.append({"source": sid, "path": relative.as_posix(), "error": "File exceeds source_bytes; omitted"})
                            continue
                        files.append(relative.as_posix())
                        if len(files) >= self.limits["source_files"]:
                            capped = True
                            break
                if capped:
                    break
            proc = None if entry.get("repository_export") else subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
            if proc is not None and not proc.returncode:
                entry["resolved_ref"] = proc.stdout.strip()
                dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True)
                entry["working_tree_dirty"] = bool(dirty.stdout.strip())
            if entry.get("ref") and not entry.get("repository_export"):
                resolved = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", entry["ref"] + "^{commit}"], capture_output=True, text=True)
                if resolved.returncode or resolved.stdout.strip() != entry.get("resolved_ref") or entry.get("working_tree_dirty"):
                    raise BlockedError("Pinned local source must be a clean checkout at the requested ref")
        if not files:
            raise BlockedError("No supported files in source " + sid)
        inventory = []
        for name in files:
            path = root if root.is_file() else safe_relative(root, name)
            data = path.read_bytes()
            if len(data) > self.limits["source_bytes"]:
                raise BlockedError("File exceeds source_bytes")
            self.total_bytes += len(data)
            if self.total_bytes > self.limits["source_total_bytes"]:
                raise BlockedError("Total source snapshot budget exhausted")
            inventory.append({"path": name, "sha256": digest(data), "bytes": len(data)})
        if item.get("sha256") and (not root.is_file() or inventory[0]["sha256"] != item["sha256"]):
            raise ValueError("Source hash differs from configuration")
        key = digest(json.dumps(inventory, sort_keys=True).encode())
        snapshot = safe_relative(self.cache, "snapshots/" + key)
        for file in inventory:
            target = safe_relative(snapshot, file["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            source = root if root.is_file() else root / file["path"]
            if target.exists() and digest(target.read_bytes()) != file["sha256"]:
                raise ValueError("Existing snapshot was modified; refusing to overwrite")
            if not target.exists():
                shutil.copyfile(source, target)
            if digest(target.read_bytes()) != file["sha256"]:
                raise ValueError("Source changed during snapshot copy")
        entry.update(path=str(snapshot / root.name if root.is_file() else snapshot),
                     original_path=original, files=files, inventory=inventory,
                     snapshot_id=key, index_truncated=capped)
        self.entries[sid] = entry
        return {"source": sid, "index": self.index()[-1]}

    def restore(self, entries, evidence, errors):
        self.entries = {e["id"]: dict(e) for e in entries}
        self.evidence, self.errors = evidence, errors
        self.total_bytes = sum(i["bytes"] for e in entries for i in e["inventory"])
        self.verify()

    def verify(self):
        for entry in self.entries.values():
            root = Path(entry["path"])
            if root.is_dir():
                current = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
                if current != sorted(i["path"] for i in entry["inventory"]):
                    raise ValueError("Source snapshot file set changed: " + entry["id"])
            for item in entry["inventory"]:
                file = root if root.is_file() else safe_relative(root, item["path"])
                if has_link(file) or not file.is_file() or digest(file.read_bytes()) != item["sha256"]:
                    raise ValueError("Source snapshot changed or missing: " + entry["id"] + "/" + item["path"])

    def index(self):
        return [{**{k: v for k, v in entry.items() if k not in ("path", "files", "inventory", "original_path")},
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
        data = path.read_bytes()
        return redact(read_text(path, self.limits["source_bytes"])), digest(data)

    def request(self, action):
        if action["action"] in ("fetch", "repository", "resolve"):
            key = {"fetch": "url", "repository": "repo", "resolve": "paper"}[action["action"]]
            item = {"id": action.get("source"), key: action.get("query", "")}
            if key == "repo" and action.get("path"):
                item["ref"] = action["path"]
            return self.add(item)
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
        return [dict(entry) for entry in self.entries.values()]
