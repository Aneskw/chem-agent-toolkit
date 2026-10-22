"""Budgeted source acquisition. Downloading never executes repository programs."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import time
import io
import zipfile
import urllib.parse
import urllib.request
from pathlib import Path

from .documents import HTMLText, table_rows
from .models import BlockedError
from .records import digest, has_link, safe_relative


def https_url(value):
    url = urllib.parse.urlsplit(value)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("Source URL requires HTTPS without embedded credentials")
    return value


class Acquisition:
    def __init__(self, config, cache):
        self.config, self.cache = config, Path(cache)
        self.requests = 0

    def charge(self):
        if time.monotonic() >= self.config.get("_deadline", float("inf")):
            raise BlockedError("Acquisition time budget exhausted")
        if not self.config["network"]:
            raise BlockedError("Network acquisition is disabled")
        if self.requests >= self.config["limits"]["network_requests"]:
            raise BlockedError("Network request budget exhausted")
        self.requests += 1

    def download(self, url, depth=0):
        https_url(url)
        self.charge()
        limit = self.config["limits"]["source_bytes"]
        request = urllib.request.Request(url, headers={"User-Agent": "resource-skill-pipeline/2"})
        with urllib.request.urlopen(request, timeout=self.config["limits"]["network_timeout"]) as response:
            final = https_url(response.url)
            data = response.read(limit + 1)
            mime = response.headers.get("Content-Type", "")
        if len(data) > limit:
            raise BlockedError("Downloaded source exceeds source_bytes")
        suffix = Path(urllib.parse.urlsplit(final).path).suffix.lower()
        if data.startswith(b"%PDF"):
            suffix = ".pdf"
        elif "xml" in mime:
            suffix = ".xml"
        elif "html" in mime or data.lstrip().lower().startswith((b"<!doctype html", b"<html")):
            suffix = ".html"
            text = data.decode("utf-8", errors="replace")
            parser = HTMLText()
            parser.feed(text)
            if depth < 2:
                pdfs = [urllib.parse.urljoin(final, h) for h in parser.links if ".pdf" in h.lower()]
                if pdfs:
                    return self.download(pdfs[0], depth + 1)
        if suffix not in (".pdf", ".html", ".md", ".txt", ".xml", ".json", ".py", ".yaml", ".yml", ".csv", ".docx", ".ipynb"):
            suffix = ".txt"
        target = safe_relative(self.cache, f"downloads/{digest(data)}/document{suffix}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target, {"requested_url": url, "resolved_url": final}

    def paper(self, identifier):
        identifier = identifier.strip()
        if identifier.startswith("arxiv:"):
            key = identifier[6:]
            if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?", key):
                raise ValueError("Invalid arXiv identifier")
            return self.download("https://arxiv.org/pdf/" + key)
        doi = identifier.removeprefix("doi:").removeprefix("https://doi.org/")
        if not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
            raise ValueError("paper accepts doi:10... or arxiv:...; title search is not configured")
        self.charge()
        url = "https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(doi, safe="/")
        with urllib.request.urlopen(url, timeout=self.config["limits"]["network_timeout"]) as response:
            raw = response.read(self.config["limits"]["source_bytes"] + 1)
        if len(raw) > self.config["limits"]["source_bytes"]:
            raise ValueError("Metadata exceeds source_bytes")
        metadata = json.loads(raw)
        for location in [metadata.get("best_oa_location"), *(metadata.get("locations") or [])]:
            if location and location.get("pdf_url"):
                path, origin = self.download(location["pdf_url"])
                return path, dict(origin, paper=identifier, metadata_url=url)
        raise BlockedError("No public PDF resolved; provide the actual full-text source")

    def repository(self, address, ref=None):
        https_url(address)
        parsed = urllib.parse.urlsplit(address)
        if parsed.hostname == "github.com":
            parts = parsed.path.strip("/").removesuffix(".git").split("/")
            if len(parts) == 2 and all(re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in parts):
                return self.github_export(parts[0], parts[1], ref)
        self.charge()
        parent = safe_relative(self.cache, "repositories")
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as tmp:
            checkout = Path(tmp) / "repo"
            def git(*args):
                proc = subprocess.run(["git", "-c", "core.hooksPath=", "-c", "protocol.file.allow=never", *args],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=self.config["limits"]["network_timeout"])
                if proc.returncode:
                    raise BlockedError("Git source acquisition failed: " + proc.stderr[-600:])
                return proc.stdout.strip()
            named_ref = ref and not re.fullmatch(r"[a-fA-F0-9]{40,64}", ref)
            if ref and (ref.startswith("-") or any(c.isspace() for c in ref)):
                raise ValueError("Invalid repository ref")
            clone_options = ["clone", "--no-checkout", "--filter=blob:none", "--depth=1", "--single-branch"]
            if named_ref:
                clone_options += ["--branch", ref]
            git(*clone_options, "--", address, str(checkout))
            if ref and not named_ref:
                if ref.startswith("-") or any(c.isspace() for c in ref):
                    raise ValueError("Invalid repository ref")
                git("-C", str(checkout), "fetch", "--filter=blob:none", "--depth=1", "origin", ref)
            commit = git("-C", str(checkout), "rev-parse", "--verify", ("FETCH_HEAD" if ref and not named_ref else "HEAD") + "^{commit}")
            if not re.fullmatch(r"[a-f0-9]{40,64}", commit):
                raise ValueError("Invalid resolved Git commit")
            # Read selected Git blobs, never checkout hooks, filters or large weights.
            from .intake import permitted
            inventory = git("-C", str(checkout), "ls-tree", "-r", commit)
            exported = Path(tmp) / "export"
            exported.mkdir()
            total, count = 0, 0
            for line in inventory.splitlines():
                metadata, name = line.split("\t", 1)
                mode, kind, blob = metadata.split()
                if mode not in ("100644", "100755") or kind != "blob" or not permitted(Path(name)):
                    continue
                # --long would lazily fetch EVERY blob merely to print sizes,
                # including excluded data/weights. Query only selected text blobs.
                size = int(git("-C", str(checkout), "cat-file", "-s", blob))
                if size > self.config["limits"]["source_bytes"]:
                    continue
                total += size
                count += 1
                if total > self.config["limits"]["source_total_bytes"] or count > self.config["limits"]["source_files"]:
                    raise BlockedError("Repository text export exceeds source budget; supply a narrower local source")
                target_file = safe_relative(exported, name)
                target_file.parent.mkdir(parents=True, exist_ok=True)
                data = subprocess.run(["git", "-C", str(checkout), "cat-file", "blob", blob],
                    capture_output=True, timeout=self.config["limits"]["network_timeout"], check=True).stdout
                target_file.write_bytes(data)
            target = safe_relative(parent, digest((address + commit).encode()))
            if has_link(target):
                raise ValueError("Linked repository cache")
            if not target.exists():
                shutil.move(str(exported), target)
        return target, {"repo": address, "resolved_ref": commit, "repository_export": True}

    def github_export(self, owner, repo, ref):
        """Pinned public archive avoids lazy-Git object fetches on restricted networks."""
        self.charge()
        metadata_url = f"https://api.github.com/repos/{owner}/{repo}/commits/" + urllib.parse.quote(ref or "HEAD", safe="")
        request = urllib.request.Request(metadata_url, headers={"User-Agent": "resource-skill-pipeline/2"})
        with urllib.request.urlopen(request, timeout=self.config["limits"]["network_timeout"]) as response:
            raw = response.read(self.config["limits"]["source_bytes"] + 1)
        if len(raw) > self.config["limits"]["source_bytes"]:
            raise BlockedError("Repository metadata exceeds source_bytes")
        commit = json.loads(raw)["sha"]
        if not re.fullmatch(r"[a-f0-9]{40}", commit):
            raise ValueError("Invalid repository commit returned by host")
        parent = safe_relative(self.cache, "repositories")
        parent.mkdir(parents=True, exist_ok=True)
        address = f"https://github.com/{owner}/{repo}.git"
        target = safe_relative(parent, digest((address + commit).encode()))
        if target.exists():
            if has_link(target):
                raise ValueError("Linked repository export")
            return target, {"repo": address, "resolved_ref": commit, "repository_export": True, "acquisition": "github-pinned-archive"}
        self.charge()
        url = f"https://codeload.github.com/{owner}/{repo}/zip/{commit}"
        with urllib.request.urlopen(url, timeout=self.config["limits"]["network_timeout"]) as response:
            data = response.read(self.config["limits"]["source_total_bytes"] + 1)
        if len(data) > self.config["limits"]["source_total_bytes"]:
            raise BlockedError("Repository archive exceeds source_total_bytes; provide a narrow local source")
        from .intake import permitted
        with tempfile.TemporaryDirectory(dir=parent) as tmp:
            exported = Path(tmp) / "export"
            exported.mkdir()
            total, count = 0, 0
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for item in archive.infolist():
                    parts = item.filename.split("/", 1)
                    if len(parts) != 2 or not parts[1] or item.is_dir() or (item.external_attr >> 16) & 0o170000 == 0o120000:
                        continue
                    name = parts[1]
                    if not permitted(Path(name)) or item.file_size > self.config["limits"]["source_bytes"]:
                        continue
                    total += item.file_size
                    count += 1
                    if total > self.config["limits"]["source_total_bytes"] or count > self.config["limits"]["source_files"]:
                        raise BlockedError("Repository expanded text export exceeds source budget")
                    path = safe_relative(exported, name)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read(item))
            shutil.move(str(exported), target)
        return target, {"repo": address, "resolved_ref": commit, "repository_export": True,
                        "acquisition": "github-pinned-archive", "archive_url": url}

    def prepare(self, item):
        entry = dict(item)
        if "url" in entry:
            path, origin = self.download(entry["url"])
            entry.update(origin, path=str(path))
        elif "paper" in entry:
            path, origin = self.paper(entry["paper"])
            entry.update(origin, path=str(path))
        elif "repo" in entry:
            path, origin = self.repository(entry["repo"], entry.get("ref"))
            entry.update(origin, path=str(path), ref=origin["resolved_ref"])
        return entry

    def expand_table(self, item):
        rows = table_rows(item["table"], self.config["limits"]["source_bytes"])
        result, errors = [], []
        for index, row in enumerate(rows[:self.config["limits"]["source_files"]], 1):
            values = []
            for key in ("pdf", "url", "doi", "repository", "github", "path"):
                value = row.get(key, "").strip()
                if value:
                    field = "paper" if key == "doi" else "repo" if key in ("repository", "github") else "path" if key == "path" else "url"
                    if field == "path":
                        value = str((Path(item["table"]).parent / value).resolve())
                    values.append({"id": f"{item['id']}-{index}-{key}", field: value})
            if not values:
                errors.append({"row": index, "error": "No recognized pdf/url/doi/repository/github/path column value"})
            result.extend(values)
        return result, errors
