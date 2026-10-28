"""Small records and cleanup restricted to registered pipeline workspaces."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data: bytes):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def redact(value):
    """Redact common credential forms; never archive process environments."""
    value = str(value)
    value = re.sub(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,\"']+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)((?:api[_-]?key|access[_-]?token|password|secret)\s*[=:]\s*)[^\s,\"']+", r"\1[REDACTED]", value)
    value = re.sub(r"\b(?:sk-[\w-]{12,}|nvapi-[\w-]{12,})", "[REDACTED]", value)
    value = re.sub(r"(https?://)[^/@\s]+:[^/@\s]+@", r"\1[REDACTED]@", value)
    for key, secret in os.environ.items():
        if re.search(r"(?i)(token|secret|password|api_?key)", key) and len(secret) >= 8:
            value = value.replace(secret, "[REDACTED]")
    return value


def sanitized(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {key: sanitized(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitized(item) for item in value]
    return value


def safe_relative(root, relative):
    """Refuse escapes, Windows drive/ADS syntax, and symlinks at every level."""
    root = Path(root).absolute()
    relative = str(relative)
    parts = relative.replace("\\", "/").split("/")
    if not relative or any(p in ("", ".", "..") or ":" in p or p.endswith((".", " "))
                           or PureWindowsPath(p).is_reserved() for p in parts):
        raise ValueError(f"Invalid relative path: {relative}")
    if PureWindowsPath(relative).drive or Path(relative).is_absolute():
        raise ValueError("Absolute paths are not allowed here")
    candidate = root
    for part in parts:
        candidate = candidate / part
        if has_link(candidate):
            raise ValueError(f"Linked paths are not allowed: {relative}")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path leaves its workspace")
    return candidate


def has_link(path):
    path = Path(path).absolute()
    for candidate in [path, *path.parents]:
        if candidate.is_symlink():
            return True
        try:
            # Python 3.11 has no Path.is_junction; Windows reparse points cover junctions.
            if getattr(candidate.lstat(), "st_file_attributes", 0) & 0x400:
                return True
        except FileNotFoundError:
            continue
    return False


def clean_run(state_root, run_id, dry_run=False):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("Invalid build ID")
    state_root = Path(state_root).absolute()
    if has_link(state_root):
        raise ValueError("State root must not contain linked paths")
    run = safe_relative(state_root, f"runs/{run_id}")
    if not run.exists():
        return {"removed": [], "dry_run": dry_run}
    marker = read_json(run / "workspace.json")
    if marker != {"build_id": run_id, "workspace": str(run.resolve())}:
        raise ValueError("Unregistered workspace; refusing cleanup")
    # Inspect before recursive removal, including Windows directory junctions.
    for path in run.rglob("*"):
        if has_link(path):
            raise ValueError("Refusing cleanup of a workspace containing links")
    if not dry_run:
        shutil.rmtree(run)
    return {"removed": [str(run)], "dry_run": dry_run}


def file_digest(path):
    """Hash a file without loading it into memory."""
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@contextmanager
def lease(state, name):
    """OS locks expire on process death; stale lock files do not pin a run forever."""
    path = safe_relative(Path(state).absolute(), "leases/" + name + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
            yield
        finally:
            if acquired:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
