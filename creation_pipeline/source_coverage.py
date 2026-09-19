#!/usr/bin/env python3
"""Report which spreadsheet papers have enough local source evidence for creation."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build() -> dict:
    papers = [json.loads(line) for line in (HERE / "papers.jsonl").read_text().splitlines() if line]
    mapping = json.loads((HERE / "repo_map.json").read_text())
    rows = []
    for paper in papers:
        key = paper["paper_id"]
        lock_path = HERE / "source_locks" / f"{key}.json"
        lock = json.loads(lock_path.read_text()) if lock_path.is_file() else None
        has_paper = bool(lock and any(x["role"] == "paper" for x in lock["source_files"]))
        has_repo = key in mapping and lock is not None
        state = "paper_and_repository" if has_paper and has_repo else (
            "repository_only" if has_repo else "metadata_only")
        rows.append({"paper_id": key, "title": paper["title"],
                     "source_list": paper["source_list"], "state": state,
                     "paper_fulltext_local": has_paper,
                     "pinned_repository": has_repo})
    counts = {state: sum(row["state"] == state for row in rows)
              for state in ("paper_and_repository", "repository_only", "metadata_only")}
    return {"total_papers": len(rows), "counts": counts, "papers": rows}


if __name__ == "__main__":
    report = build()
    target = HERE / "source_coverage.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"total_papers": report["total_papers"], "counts": report["counts"],
                      "report": str(target)}, ensure_ascii=False))
