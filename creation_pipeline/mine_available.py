#!/usr/bin/env python3
"""Automatically mine every catalog entry with local paper and repository evidence."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

from source_coverage import build

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GOOD = {"method_drafts_created", "atomic_resource_hints_only", "repo_only_hints_created"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-6-astra")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.rounds <= 10:
        parser.error("--rounds must be between 1 and 10")
    report = build()
    eligible = [row for row in report["papers"] if row["state"] == "paper_and_repository"]
    prefix = args.prefix or f"catalog-{datetime.now():%Y%m%d-%H%M%S}"
    plan = {"prefix": prefix, "model": args.model, "rounds": args.rounds,
            "total": report["total_papers"], "eligible": [row["paper_id"] for row in eligible],
            "counts": report["counts"],
            "skipped": {"repository_only": report["counts"]["repository_only"],
                        "metadata_only": report["counts"]["metadata_only"]}}
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0
    records = []
    for row in eligible:
        for round_number in range(1, args.rounds + 1):
            run_id = f"{prefix}-{row['paper_id']}-r{round_number:02d}"
            print(f"Extracting {row['paper_id']} ({row['title']}) round {round_number}/{args.rounds}", flush=True)
            proc = subprocess.run([sys.executable, str(HERE / "run_pipeline.py"),
                                   "--paper-id", row["paper_id"], "--model", args.model,
                                   "--run-id", run_id], cwd=ROOT, text=True, capture_output=True)
            result_path = HERE / "results" / f"{run_id}.json"
            result = json.loads(result_path.read_text()) if result_path.is_file() else {
                "status": "failed", "error": proc.stderr[-1200:]}
            record = {"paper_id": row["paper_id"], "run_id": run_id,
                      "status": result.get("status"), "candidate_count": result.get("candidate_count", 0),
                      "error": result.get("error")}
            if result.get("status") in GOOD:
                publish_args = [sys.executable, str(HERE / "publish_run.py"), "--run-id", run_id]
                if args.push:
                    publish_args.append("--push")
                publish = subprocess.run(publish_args, cwd=ROOT, text=True, capture_output=True)
                record["publish_status"] = "published" if publish.returncode == 0 else "publish_failed"
                if publish.returncode:
                    record["publish_error"] = publish.stderr[-1200:]
            else:
                record["publish_status"] = "not_published"
            records.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
            if result.get("status") == "failed":
                print("Stopping after the first failed extraction.", file=sys.stderr)
                break
    output = HERE / "results" / f"{prefix}-catalog-batch.json"
    output.write_text(json.dumps({"plan": plan, "runs": records,
                                  "deduplication": "not_run",
                                  "execution_validation": "not_run",
                                  "agent_effect_validation": "not_run"},
                                 ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "finished", "report": str(output), "runs": len(records)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
