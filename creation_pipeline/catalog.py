#!/usr/bin/env python3
"""Normalize the two Zotero CSV exports without copying local attachment paths."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(paths: list[Path]) -> tuple[list[dict], dict]:
    rows, seen, inputs = [], set(), []
    for path in paths:
        inputs.append({"file": path.name, "sha256": sha256(path)})
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for line, raw in enumerate(reader, 2):
                title = (raw.get("Title") or "").strip()
                if not title:
                    continue
                doi = (raw.get("DOI") or "").strip().lower().removeprefix("https://doi.org/")
                identity = doi or " ".join(title.casefold().split())
                if identity in seen:
                    continue
                seen.add(identity)
                rows.append({
                    "paper_id": (raw.get("Key") or hashlib.sha256(identity.encode()).hexdigest()[:12]).strip(),
                    "title": title,
                    "authors": (raw.get("Author") or "").strip(),
                    "year": (raw.get("Publication Year") or "").strip(),
                    "doi": doi,
                    "url": (raw.get("Url") or ("https://doi.org/" + doi if doi else "")).strip(),
                    "source_list": path.name,
                    "source_row": line,
                    "status": "metadata_only",
                })
    report = {"input_files": inputs, "papers": len(rows),
              "with_doi": sum(bool(row["doi"]) for row in rows),
              "with_url": sum(bool(row["url"]) for row in rows),
              "excluded_fields": ["Abstract Note", "File Attachments", "Link Attachments", "Notes"]}
    return rows, report


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--forward", type=Path, required=True)
    p.add_argument("--retro", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    rows, report = normalize([args.forward, args.retro])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    args.output.with_suffix(".summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
