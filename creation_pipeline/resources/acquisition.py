"""Known-address acquisition with streaming files and explicit provenance."""
from __future__ import annotations
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import http.client
import ssl
from pathlib import Path
from creation_pipeline.resources.documents import table_rows
from creation_pipeline.models import BlockedError, exceeded
from creation_pipeline.records import digest, has_link, safe_relative, write_json, read_json


def https_url(value):
    url = urllib.parse.urlsplit(value)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("Source URL requires HTTPS without embedded credentials")
    return value


class Acquisition:
    def __init__(self, config, cache):
        self.config, self.cache, self.requests = config, Path(cache), 0

    def charge(self):
        if time.monotonic() >= self.config.get("_deadline", float("inf")):
            raise BlockedError("Acquisition time budget exhausted")
        if not self.config["network"]:
            raise BlockedError("Network acquisition is disabled")
        cap = self.config["limits"]["network_requests"]
        if cap is not None and self.requests >= cap:
            raise BlockedError("Network request budget exhausted")
        self.requests += 1

    def _stream(self, url, target, limit):
        """Download once, retrying only transport-level failures.

        A TLS/EOF blip or a truncated body before any content was accepted is not a
        source defect; the hash gate still decides what the bytes mean. Each attempt
        charges the same request budget, so the retry is bounded by configuration.
        """
        last = None
        for attempt in range(self.config["limits"].get("download_attempts", 2)):
            try:
                return self._stream_once(url, target, limit)
            except (urllib.error.URLError, ssl.SSLError, OSError, http.client.HTTPException) as exc:
                last = exc
                if isinstance(exc, urllib.error.HTTPError):
                    raise
                if attempt + 1 >= self.config["limits"].get("download_attempts", 2):
                    break
                time.sleep(min(1.0 * (attempt + 1), 3.0))
        raise last

    def _stream_once(self, url, target, limit):
        self.charge()
        request = urllib.request.Request(https_url(url), headers={"User-Agent": "research-skill-pipeline/5"})
        total, h = 0, hashlib.sha256()
        with urllib.request.urlopen(request, timeout=self.config["limits"]["network_timeout"]) as response:
            final = https_url(response.url)
            mime = response.headers.get("Content-Type", "")
            with Path(target).open("wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if exceeded(total, limit):
                        raise BlockedError("Downloaded resource exceeds explicit source size limit")
                    h.update(chunk)
                    out.write(chunk)
        return final, mime, h.hexdigest()

    def download(self, url, depth=0):
        https_url(url)
        links = self.cache / "download-index"
        index = links / (digest(url.encode()) + ".json")
        if index.exists():
            cached = read_json(index)
            from creation_pipeline.records import file_digest
            if Path(cached["path"]).is_file() and file_digest(cached["path"]) == cached["sha256"]:
                return Path(cached["path"]), cached["origin"]
        self.cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.cache) as tmp:
            raw = Path(tmp) / "download"
            final, mime, sha = self._stream(url, raw, self.config["limits"]["source_bytes"])
            suffix = Path(urllib.parse.urlsplit(final).path).suffix.lower()
            with raw.open("rb") as stream:
                prefix = stream.read(512)
            if prefix.startswith(b"%PDF"):
                suffix = ".pdf"
            elif "html" in mime:
                suffix = ".html"
            elif "xml" in mime:
                suffix = ".xml"
            if not re.fullmatch(r"\.[a-z0-9]{1,12}", suffix or ""):
                suffix = ".bin"
            target = safe_relative(self.cache, f"downloads/{sha}/document{suffix}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(raw, target)
        origin = {"requested_url": url, "resolved_url": final, "content_type": mime}
        write_json(index, {"path": str(target.resolve()), "sha256": sha, "origin": origin})
        return target, origin

    def paper(self, identifier):
        identifier = identifier.strip()
        if identifier.startswith("arxiv:"):
            key = identifier[6:]
            if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?", key):
                raise ValueError("Invalid arXiv identifier")
            return self.download("https://arxiv.org/pdf/" + key)
        doi = identifier.removeprefix("doi:").removeprefix("https://doi.org/")
        if not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
            raise ValueError("paper accepts DOI/arXiv identifiers; autonomous search is not supported")
        self.charge()
        url = "https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(doi, safe="/")
        with urllib.request.urlopen(url, timeout=self.config["limits"]["network_timeout"]) as response:
            metadata = json.load(response)
        for location in [metadata.get("best_oa_location"), *(metadata.get("locations") or [])]:
            if location and location.get("pdf_url"):
                path, origin = self.download(location["pdf_url"])
                return path, dict(origin, paper=identifier, metadata_url=url)
        raise BlockedError("No public PDF resolved; provide or identify an actual full-text address")

    def _extract(self, archive_path, exported, zipped):
        from creation_pipeline.resources.intake import exclusion
        total, count, omitted = 0, 0, []
        archive = zipfile.ZipFile(archive_path) if zipped else tarfile.open(archive_path)
        with archive:
            for item in archive.infolist() if zipped else archive:
                name = item.filename if zipped else item.name
                if zipped:
                    parts = name.split("/", 1)
                    if len(parts) != 2 or not parts[1] or item.is_dir():
                        continue
                    name = parts[1]
                    linked = (item.external_attr >> 16) & 0o170000 == 0o120000
                    size = item.file_size
                else:
                    if item.isdir():
                        continue
                    linked, size = not item.isfile(), item.size
                reason = exclusion(Path(name)) or ("link/special file not followed" if linked else None)
                if reason:
                    omitted.append({"path": name, "reason": reason})
                    continue
                if exceeded(size, self.config["limits"]["source_bytes"]):
                    omitted.append({"path": name, "reason": "explicit single-file limit"})
                    continue
                count, total = count + 1, total + size
                if exceeded(count, self.config["limits"]["source_files"]) or exceeded(total, self.config["limits"]["source_total_bytes"]):
                    raise BlockedError("Repository exceeds explicit source limits")
                target = safe_relative(exported, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                with (archive.open(item) if zipped else archive.extractfile(item)) as stream, target.open("wb") as out:
                    shutil.copyfileobj(stream, out, 1024 * 1024)
        return omitted

    def repository(self, address, ref=None):
        https_url(address)
        parsed = urllib.parse.urlsplit(address)
        parts = parsed.path.strip("/").removesuffix(".git").split("/")
        if parsed.hostname == "github.com" and len(parts) == 2 and all(re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in parts):
            return self.github_export(parts[0], parts[1], ref)
        if ref and (ref.startswith("-") or any(c.isspace() for c in ref)):
            raise ValueError("Invalid repository ref")
        self.charge()
        parent = self.cache / "repositories"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as tmp:
            checkout = Path(tmp) / "repo"
            def git(*args):
                return subprocess.run(["git", "-c", "core.hooksPath=", "-c", "protocol.file.allow=never", *args],
                    check=True, capture_output=True, text=True, timeout=self.config["limits"]["network_timeout"]).stdout.strip()
            options = ["clone", "--no-checkout", "--depth=1", "--single-branch"]
            named = ref and not re.fullmatch(r"[a-fA-F0-9]{40,64}", ref)
            if named:
                options += ["--branch", ref]
            git(*options, "--", address, str(checkout))
            if ref and not named:
                git("-C", str(checkout), "fetch", "--depth=1", "origin", ref)
            commit = git("-C", str(checkout), "rev-parse", ("FETCH_HEAD" if ref and not named else "HEAD") + "^{commit}")
            target = safe_relative(parent, digest((address + commit + ":v5").encode()))
            omitted = []
            if not target.exists():
                archive = Path(tmp) / "source.tar"
                git("-C", str(checkout), "archive", "--format=tar", "--output=" + str(archive), commit)
                exported = Path(tmp) / "export"
                exported.mkdir()
                omitted = self._extract(archive, exported, False)
                exported.rename(target)
        return target, {"repo": address, "resolved_ref": commit, "repository_export": True, "acquisition_omissions": omitted, "acquisition_limitations": ["Submodule contents and Git LFS payloads are not automatically resolved"]}

    def github_export(self, owner, repo, ref):
        self.charge()
        metadata_url = f"https://api.github.com/repos/{owner}/{repo}/commits/" + urllib.parse.quote(ref or "HEAD", safe="")
        with urllib.request.urlopen(metadata_url, timeout=self.config["limits"]["network_timeout"]) as response:
            commit = json.load(response)["sha"]
        if not re.fullmatch(r"[a-f0-9]{40}", commit):
            raise ValueError("Invalid repository commit")
        parent = self.cache / "repositories"
        parent.mkdir(parents=True, exist_ok=True)
        address = f"https://github.com/{owner}/{repo}.git"
        target = safe_relative(parent, digest((address + commit + ":v5").encode()))
        omissions_path = parent / (target.name + ".omissions.json")
        omitted = read_json(omissions_path) if omissions_path.exists() else []
        url = f"https://codeload.github.com/{owner}/{repo}/zip/{commit}"
        if not target.exists():
            with tempfile.TemporaryDirectory(dir=parent) as tmp:
                archive = Path(tmp) / "source.zip"
                self._stream(url, archive, self.config["limits"]["source_total_bytes"])
                exported = Path(tmp) / "export"
                exported.mkdir()
                omitted = self._extract(archive, exported, True)
                exported.rename(target)
            write_json(omissions_path, omitted)
        return target, {"repo": address, "resolved_ref": commit, "repository_export": True,
                        "archive_url": url, "acquisition_omissions": omitted, "acquisition_limitations": ["Submodule contents and Git LFS payloads are not automatically resolved"]}

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
