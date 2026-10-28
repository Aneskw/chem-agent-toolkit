"""Source snapshots, complete inventories and source-evidence integrity."""
from __future__ import annotations

import json
import re
import subprocess
import shutil
from pathlib import Path

from creation_pipeline.models import BlockedError, exceeded
from creation_pipeline.resources.acquisition import Acquisition
from creation_pipeline.records import digest, has_link, redact, safe_relative, file_digest


EXCLUDED = {".git", ".pipeline", ".venv", "venv", "node_modules", "__pycache__",
            ".pytest_cache", ".mypy_cache", ".ruff_cache", ".aws", ".ssh"}
SUFFIXES = set()  # No extension allowlist: parsing support is separate from retention.


def exclusion(path):
    path = Path(path)
    if any(part in EXCLUDED for part in path.parts):
        return "internal metadata, installed environment, cache or credential store"
    name = path.name.lower()
    if name in {".ds_store", "thumbs.db"} or name.startswith("~$") or name.endswith((".swp", ".swo")):
        return "system/editor temporary file"
    if name in {".env", "id_rsa", "id_ed25519"} or name.endswith((".key", ".pem")):
        return "credential-bearing file (templates/documentation are retained)"
    if name.startswith(".env.") and not name.endswith((".example", ".sample", ".template")):
        return "environment secrets file"
    return None


def permitted(path):
    return exclusion(path) is None


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
                before_bytes = self.total_bytes
                try:
                    self.add(source)
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    self.total_bytes = before_bytes
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
        omitted = []
        if root.is_file():
            if not permitted(Path(root.name)):
                raise ValueError("Unsupported source file type")
            files = [root.name]
        else:
            import os
            for directory, names, filenames in os.walk(root, followlinks=False):
                retained = []
                for n in sorted(names):
                    rel = (Path(directory) / n).relative_to(root)
                    reason = exclusion(rel) or ("linked directory; not followed" if has_link(Path(directory) / n) else None)
                    if reason:
                        omitted.append({"path": rel.as_posix(), "reason": reason})
                    else:
                        retained.append(n)
                names[:] = retained
                for name in sorted(filenames):
                    file = Path(directory) / name
                    relative = file.relative_to(root)
                    if not permitted(relative) or has_link(file):
                        omitted.append({"path": relative.as_posix(), "reason": exclusion(relative) or "linked file; not followed"})
                    if permitted(relative) and not has_link(file):
                        if exceeded(file.stat().st_size, self.limits["source_bytes"]):
                            self.errors.append({"source": sid, "path": relative.as_posix(), "error": "File exceeds source_bytes; omitted"})
                            continue
                        files.append(relative.as_posix())
                        if self.limits["source_files"] is not None and len(files) >= self.limits["source_files"]:
                            capped = True
                            break
                if capped:
                    break
            proc = None if entry.get("repository_export") else subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
            if proc is not None and not proc.returncode:
                dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True)
                top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
                entry['carrier_repository'] = {'commit': proc.stdout.strip(), 'working_tree_dirty': bool(dirty.stdout.strip()),
                    'meaning': 'Repository containing the input; not an upstream tool version'}
                if top.returncode == 0 and Path(top.stdout.strip()).resolve() == root.resolve():
                    entry['resolved_ref'] = proc.stdout.strip()
                    entry['working_tree_dirty'] = bool(dirty.stdout.strip())
            if entry.get("ref") and not entry.get("repository_export"):
                resolved = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", entry["ref"] + "^{commit}"], capture_output=True, text=True)
                if resolved.returncode or resolved.stdout.strip() != entry.get("resolved_ref") or entry.get("working_tree_dirty"):
                    raise BlockedError("Pinned local source must be a clean checkout at the requested ref")
        if not files:
            raise BlockedError("No supported files in source " + sid)
        inventory = []
        for name in files:
            path = root if root.is_file() else safe_relative(root, name)
            size = path.stat().st_size
            if exceeded(size, self.limits["source_bytes"]):
                raise BlockedError("File exceeds source_bytes")
            self.total_bytes += size
            if exceeded(self.total_bytes, self.limits["source_total_bytes"]):
                raise BlockedError("Total source snapshot budget exhausted")
            inventory.append({"path": name, "sha256": file_digest(path), "bytes": size})
        if item.get("sha256") and (not root.is_file() or inventory[0]["sha256"] != item["sha256"]):
            raise ValueError("Source hash differs from configuration")
        key = digest(json.dumps(inventory, sort_keys=True).encode())
        pinned = re.fullmatch(r'https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([a-f0-9]{40})/(.+)', entry.get('url', ''))
        if pinned and root.is_file():
            entry['upstream'] = {'repo': 'https://github.com/' + pinned[1] + '/' + pinned[2],
                'commit': pinned[3], 'path': pinned[4], 'retrieved_url': entry['url'], 'sha256': inventory[0]['sha256']}
        if item.get("storage") == "reference":
            if not root.is_file():
                raise ValueError("Reference storage supports individual files; directories use filtered snapshots")
            entry.update(path=str(root), original_path=original, files=files, inventory=inventory,
                         snapshot_id=key, index_truncated=capped, omitted_preview=omitted)
            self.entries[sid] = entry
            return {"source": sid, "index": self.index()[-1]}
        snapshot = safe_relative(self.cache, "snapshots/" + key)
        for file in inventory:
            target = safe_relative(snapshot, file["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            source = root if root.is_file() else root / file["path"]
            if target.exists() and file_digest(target) != file["sha256"]:
                raise ValueError("Existing snapshot was modified; refusing to overwrite")
            if not target.exists():
                shutil.copyfile(source, target)
            if file_digest(target) != file["sha256"]:
                raise ValueError("Source changed during snapshot copy")
        entry.update(path=str(snapshot / root.name if root.is_file() else snapshot),
                     original_path=original, files=files, inventory=inventory,
                     snapshot_id=key, index_truncated=capped, omitted_preview=omitted)
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
                if has_link(file) or not file.is_file() or file_digest(file) != item["sha256"]:
                    raise ValueError("Source snapshot changed or missing: " + entry["id"] + "/" + item["path"])

    def index(self):
        result = [{**{k: v for k, v in entry.items() if k not in ("path", "files", "inventory", "original_path")},
                 "files": entry["files"][:100], "index_preview_truncated": len(entry["files"]) > 100}
                for entry in self.entries.values()]
        for entry in result:
            if entry.get('resolved_ref') and not entry.get('repo') and not entry.get('upstream'):
                entry['local_input_reference'] = {'value': entry.pop('resolved_ref'),
                    'meaning': 'Local or legacy input repository reference; NOT verified as an upstream tool version. Use snapshot_id for reproducible input identity.'}
        return result

    def validate_evidence(self, evidence):
        known = {item["id"]: item for item in self.evidence}
        for item in evidence:
            if (not isinstance(item, dict) or item.get("id") not in known or not item.get("claim")
                    or not known[item["id"]]["excerpt"].strip()):
                raise ValueError("Invalid evidence reference " + repr(item) + "; use known nonempty evidence IDs (native locators do not prove reading): " + ",".join(known))
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
