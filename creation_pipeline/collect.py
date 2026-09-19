#!/usr/bin/env python3
"""Collect pinned, selected paper/repository sources into an ignored local cache."""
from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fetch(url: str, limit: int = 5_000_000) -> bytes:
    host = urllib.parse.urlsplit(url).hostname
    if host not in {"raw.githubusercontent.com", "www.ebi.ac.uk", "api.github.com"}:
        raise ValueError(f"Unexpected source host: {host}")
    cafile = "/etc/ssl/cert.pem" if Path("/etc/ssl/cert.pem").is_file() else None
    request = urllib.request.Request(url, headers={"User-Agent": "chem-agent-toolkit/creation-pipeline"})
    with urllib.request.urlopen(request, context=ssl.create_default_context(cafile=cafile), timeout=45) as response:
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError("Source exceeds 5 MB limit")
    if len(content) < 100:
        raise ValueError("Source unexpectedly small")
    return content


def collect(paper_id: str, cache: Path, catalog: Path, repo_map: Path, locks: Path) -> dict:
    papers = {x["paper_id"]: x for x in map(json.loads, catalog.read_text().splitlines()) if x}
    mapping = json.loads(repo_map.read_text())
    if paper_id not in papers:
        raise ValueError(f"Unknown paper ID: {paper_id}")
    if paper_id not in mapping:
        raise ValueError(f"No pinned repository map for {paper_id}; add one after source review")
    paper, repo = papers[paper_id], mapping[paper_id]
    root = cache / paper_id
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "repo.json"
    if not manifest_path.is_file():
        tree_url = f"https://api.github.com/repos/{repo['repo']}/git/trees/{repo['commit']}?recursive=1"
        tree = json.loads(fetch(tree_url, limit=2_000_000))
        if tree.get("truncated") or not isinstance(tree.get("tree"), list):
            raise ValueError("Repository tree is missing or truncated")
        manifest_path.write_text(json.dumps({"repo": repo["repo"], "commit": repo["commit"],
                                             "tree": tree["tree"]}, indent=2) + "\n")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("repo") != repo["repo"] or manifest.get("commit") != repo["commit"]:
        raise ValueError("Cached repository tree does not match pinned source")
    entries, sources = [], []
    for relative in repo["files"]:
        part = Path(relative)
        if part.is_absolute() or ".." in part.parts:
            raise ValueError("Unsafe repository path")
        url = f"https://raw.githubusercontent.com/{repo['repo']}/{repo['commit']}/{relative}"
        dest = root / "repo" / part
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.is_file():
            dest.write_bytes(fetch(url))
        data = dest.read_bytes()
        entries.append({"role": "repo", "path": relative, "url": url,
                        "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                        "license": "see upstream repository LICENSE"})
        sources.append({"path": str(dest.relative_to(root)),
                        "role": "repo_doc" if part.suffix == ".md" else "repo_code", "url": url})
    paper_url = repo.get("paper_url")
    if paper_url:
        dest = root / "paper.xml"
        if not dest.is_file():
            dest.write_bytes(fetch(paper_url))
        data = dest.read_bytes()
        entries.append({"role": "paper", "url": paper_url, "sha256": hashlib.sha256(data).hexdigest(),
                        "bytes": len(data), "license": repo.get("paper_license", "verify before redistribution")})
        sources.insert(0, {"path": "paper.xml", "role": "paper", "url": paper_url})
    config = {"base": ".", "max_context_chars": 80000, "jobs": [{
        "paper_id": paper_id, "title": paper["title"], "repo_root": "repo",
        "repo_manifest": "repo.json", "repo_url": f"https://github.com/{repo['repo']}",
        "commit": repo["commit"], "sources": sources,
    }]}
    (root / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    lock = {"paper_id": paper_id, "title": paper["title"], "doi": paper["doi"],
            "paper_url": paper["url"], "repository": repo["repo"], "commit": repo["commit"],
            "source_files": entries, "repository_tree_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "repository_file_count": len(manifest["tree"]), "raw_files_committed": False}
    locks.mkdir(parents=True, exist_ok=True)
    lock_path = locks / f"{paper_id}.json"
    if lock_path.is_file():
        old = json.loads(lock_path.read_text(encoding="utf-8"))
        if old.get("source_files") != lock["source_files"] or old.get("commit") != lock["commit"]:
            raise ValueError("Source bytes or pinned commit changed since the previous lock; review before updating")
    lock_path.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n")
    return {"paper_id": paper_id, "sources": len(entries), "paper_fulltext": bool(paper_url),
            "config": str(root / "config.json"), "lock": str(lock_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-id", required=True)
    parser.add_argument("--catalog", type=Path, default=HERE / "papers.jsonl")
    parser.add_argument("--repo-map", type=Path, default=HERE / "repo_map.json")
    parser.add_argument("--cache", type=Path, default=HERE / "cache")
    parser.add_argument("--locks", type=Path, default=HERE / "source_locks")
    args = parser.parse_args()
    print(json.dumps(collect(args.paper_id, args.cache, args.catalog, args.repo_map, args.locks), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
