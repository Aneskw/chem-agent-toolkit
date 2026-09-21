#!/usr/bin/env python3
"""Mine multiple paper/database/tool/model manifests and publish candidates."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def safe(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")
    if not value:
        raise ValueError("Empty or unsafe job identifier")
    return value[:60]


def absolute_job(job: dict, manifest_dir: Path) -> dict:
    item = dict(job)
    item["paper_id"] = safe(str(item["paper_id"]))
    if "repo_root" in item:
        item["repo_root"] = str((manifest_dir / item["repo_root"]).resolve())
    sources = []
    for source in item.get("sources", []):
        source = dict(source)
        source["path"] = str((manifest_dir / source["path"]).resolve())
        sources.append(source)
    item["sources"] = sources
    return item


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="JSON manifest with jobs[]")
    parser.add_argument("--model", default="gpt-6-astra")
    parser.add_argument("--rounds", type=int, default=1, help="Independent passes per source")
    parser.add_argument("--max-jobs", type=int, default=None, help="Process at most this many manifest jobs")
    parser.add_argument("--start-index", type=int, default=0, help="Zero-based manifest offset for resuming a batch")
    parser.add_argument("--target-candidates", type=int, default=None,
                        help="Stop after at least this many candidate skills are created")
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--push", action="store_true", help="Commit and push generated candidates")
    args = parser.parse_args()
    if args.rounds < 1 or args.rounds > 20:
        parser.error("--rounds must be between 1 and 20")
    if args.max_jobs is not None and args.max_jobs < 1:
        parser.error("--max-jobs must be positive")
    if args.start_index < 0:
        parser.error("--start-index must be non-negative")
    if args.target_candidates is not None and not 1 <= args.target_candidates <= 500:
        parser.error("--target-candidates must be between 1 and 500")
    manifest = args.manifest.resolve()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    jobs = data.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        parser.error("manifest must contain a non-empty jobs[] list")
    jobs = [absolute_job(job, (manifest.parent / data.get('base','.')).resolve()) for job in jobs]
    jobs = jobs[args.start_index:]
    if args.max_jobs is not None:
        jobs = jobs[:args.max_jobs]
    ids = [job["paper_id"] for job in jobs]
    if len(ids) != len(set(ids)):
        parser.error("jobs must have unique paper_id values")
    prefix = safe(args.prefix or f"batch-{datetime.now():%Y%m%d-%H%M%S}")
    run_records = []
    published = []
    def published_count():
        return sum(int(r.get('candidate_count') or 0) for r in run_records
                   if r.get('publish_status')=='published_locally')
    report_path = HERE / 'results' / f'{prefix}-batch.json'
    report_path.parent.mkdir(exist_ok=True)
    def checkpoint(state):
        report={'batch_id':prefix,'model':args.model,'rounds':args.rounds,'status':state,
                'manifest':str(manifest),'target_candidates':args.target_candidates,
                'deduplication':'not_run','execution_validation':'not_run',
                'agent_effect_validation':'not_run','runs':run_records,'published_paths':published,
                'published_candidates':sum(int(r.get('candidate_count') or 0) for r in run_records
                                           if r.get('publish_status')=='published_locally')}
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    checkpoint('running')
    with tempfile.TemporaryDirectory(prefix="chemskillnet-batch-") as temp_name:
        temp_dir = Path(temp_name)
        for job in jobs:
            for round_number in range(1, args.rounds + 1):
                run_id = f"{prefix}-{safe(job['paper_id'])}-r{round_number:02d}"
                config = temp_dir / f"{run_id}.json"
                config.write_text(json.dumps({"base": ".", "max_context_chars": data.get("max_context_chars", 80000),
                                              "jobs": [job]}, ensure_ascii=False, indent=2) + "\n")
                print(f"Extracting {job['paper_id']} round {round_number}/{args.rounds} -> {run_id}", flush=True)
                proc = subprocess.run([sys.executable, str(HERE / "run_pipeline.py"),
                                       "--config", str(config), "--model", args.model,
                                       "--run-id", run_id], text=True, capture_output=True)
                result_path = HERE / "results" / f"{run_id}.json"
                result = json.loads(result_path.read_text()) if result_path.is_file() else {
                    "run_id": run_id, "status": "failed", "error": proc.stderr[-1200:]}
                record = {"run_id": run_id, "paper_id": job["paper_id"],
                          "source_type": job.get("source_type", "paper"),
                          "status": result.get("status"), "candidate_count": result.get("candidate_count", 0),
                          "error": result.get("error")}
                run_records.append(record)
                print(json.dumps(record, ensure_ascii=False), flush=True)
                if result.get("status") in {"method_drafts_created", "atomic_resource_hints_only",
                                             "repo_only_hints_created"}:
                    publish = subprocess.run([sys.executable, str(HERE / "publish_run.py"),
                                              "--run-id", run_id], text=True, capture_output=True)
                    if publish.returncode:
                        record["publish_status"] = "failed"
                        record["publish_error"] = publish.stderr[-1200:]
                    else:
                        record["publish_status"] = "published_locally"
                        published_path=ROOT / "skills" / "generated" / run_id
                        publication=json.loads((published_path / "PUBLISHING.json").read_text())
                        record["execution_checks"] = publication.get("execution_checks", {})
                        record["execution_validated"] = publication.get("execution_validated", False)
                        record["publication_state"] = publication.get("publication_state")
                        published.append(str(published_path.relative_to(ROOT)))
                        for routed in publication.get("classifications", {}).values():
                            routed_path = routed.get("path")
                            if routed_path and routed_path not in published:
                                published.append(routed_path)
                else:
                    record["publish_status"] = "not_published"
                checkpoint('running')
                if args.target_candidates is not None and published_count() >= args.target_candidates:
                    break
            if args.target_candidates is not None and published_count() >= args.target_candidates:
                break
    report = {"batch_id": prefix, "model": args.model, "rounds": args.rounds,
              "manifest": str(manifest), "target_candidates": args.target_candidates,
              "deduplication": "not_run",
              "execution_validation": "not_run", "agent_effect_validation": "not_run",
              "runs": run_records, "published_paths": published}
    checkpoint('finished')
    if args.push and published:
        subprocess.run(["git", "add", *published], cwd=ROOT, check=True)
        subprocess.run(["git", "add", str(report_path.relative_to(ROOT))], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", f"Publish batch source-validated candidates {prefix}"], cwd=ROOT, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    print(json.dumps({"status": "batch_finished", "report": str(report_path),
                      "published": len(published), "pushed": bool(args.push and published)}, ensure_ascii=False))
    return 0 if args.target_candidates is None or published_count() >= args.target_candidates else 2


if __name__ == "__main__":
    raise SystemExit(main())
