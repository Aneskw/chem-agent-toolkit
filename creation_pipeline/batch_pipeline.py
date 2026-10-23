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
import time
from workflow_state import counts, batch_exit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def execution_summary(records):
    counts = {}
    for record in records:
        for status in record.get("execution_checks", {}).values():
            counts[status] = counts.get(status, 0) + 1
    return {"candidate_status_counts": counts, "status": "reported" if counts else "not_run"}


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
    parser.add_argument("--runtime-mode", choices=("auto", "off", "docker"), default="auto")
    parser.add_argument('--draft-only',action='store_true')
    parser.add_argument("--tool-bindings", type=Path)
    parser.add_argument('--success-policy',choices=('delivery','creation','execution','draft'),default='delivery')
    parser.add_argument('--case-seconds',type=int,help='Complete creation budget per job, including Docker')
    parser.add_argument('--round-seconds',type=int,help='Shared batch deadline, including archival')
    parser.add_argument('--extraction-timeout',type=int,default=900)
    args = parser.parse_args()
    if any(v is not None and v<1 for v in [args.case_seconds,args.round_seconds,args.extraction_timeout]):parser.error('Budgets must be positive')
    batch_started=time.monotonic()
    deadline=batch_started+args.round_seconds if args.round_seconds else None
    from delivery import cli_mode
    if args.success_policy == 'draft': args.draft_only = True
    cli_mode(args, parser)
    runtime_args = ["--runtime-mode", args.runtime_mode]
    if args.tool_bindings:
        runtime_args += ["--tool-bindings", str(args.tool_bindings.resolve())]
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
        return sum(int(r.get('archived_candidate_count',r.get('candidate_count')) or 0) for r in run_records
                   if r.get('publish_status')=='published_locally')
    report_path = HERE / 'results' / f'{prefix}-batch.json'
    report_path.parent.mkdir(exist_ok=True)
    def checkpoint(state):
        final = state != 'running'
        report={'batch_id':prefix,'model':args.model,'rounds':args.rounds,'status':state,
                'delivery_accepted':bool(final and state=='finished' and args.success_policy!='draft'),
                'delivery_status':'draft_only' if args.success_policy=='draft' else 'delivered' if final and state=='finished' else 'blocked' if final else 'running',
                'manifest':str(manifest),'target_candidates':args.target_candidates,
                'deduplication':'not_run','execution_validation':execution_summary(run_records),
                'agent_effect_validation':'not_run','runs':run_records,'published_paths':published,
                'success_policy':args.success_policy,'counts':counts(run_records),'planned_runs':len(jobs)*args.rounds,
                'budget':{'case_seconds':args.case_seconds,'round_seconds':args.round_seconds,'elapsed_seconds':round(time.monotonic()-batch_started,3)},
                'unattempted_runs':max(0,len(jobs)*args.rounds-len(run_records)),
                'published_candidates':sum(int(r.get('archived_candidate_count',r.get('candidate_count')) or 0) for r in run_records
                                           if r.get('publish_status')=='published_locally')}
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    checkpoint('running')
    with tempfile.TemporaryDirectory(prefix="chemskillnet-batch-") as temp_name:
        temp_dir = Path(temp_name)
        for job in jobs:
            for round_number in range(1, args.rounds + 1):
                if deadline and time.monotonic()>=deadline:break
                run_id = f"{prefix}-{safe(job['paper_id'])}-r{round_number:02d}"
                config = temp_dir / f"{run_id}.json"
                config.write_text(json.dumps({"base": ".", "max_context_chars": data.get("max_context_chars", 80000),
                                              "jobs": [job]}, ensure_ascii=False, indent=2) + "\n",encoding='utf-8')
                print(f"Extracting {job['paper_id']} round {round_number}/{args.rounds} -> {run_id}", flush=True)
                creation_started=time.monotonic()
                command=[sys.executable, str(HERE / "run_pipeline.py"),
                                       "--config", str(config), "--model", args.model,
                                       "--run-id", run_id, *runtime_args]
                command+=['--extraction-timeout',str(args.extraction_timeout),'--success-policy',args.success_policy]
                limit=min(v for v in [args.case_seconds,deadline-time.monotonic() if deadline else None] if v is not None) if args.case_seconds or deadline else None
                if limit is None:proc = subprocess.run(command,text=True,capture_output=True)
                else:
                    from runtime_package import process
                    command+=['--total-seconds',str(max(1,int(limit)-30))]
                    try:observed=process(command,timeout=max(1,limit)+10,supervise=True)
                    except subprocess.TimeoutExpired as exc:
                        observed={'exit_code':2,'stdout':'','stderr':'Case deadline exceeded','scope':getattr(exc,'scope',None),'cleanup':getattr(exc,'cleanup',[])}
                    from types import SimpleNamespace
                    proc=SimpleNamespace(returncode=observed['exit_code'],stdout=observed['stdout'],stderr=observed['stderr'])
                result_path = HERE / "results" / f"{run_id}.json"
                try:
                    result = json.loads(result_path.read_text(encoding='utf-8')) if result_path.is_file() else {
                        "run_id": run_id, "status": "failed", "error": proc.stderr[-1200:]}
                except (OSError,ValueError) as exc:
                    result={'run_id':run_id,'status':'failed','error':'Creation result unreadable: '+repr(exc)}
                record = {"run_id": run_id, "paper_id": job["paper_id"],
                          "source_type": job.get("source_type", "paper"),
                          "status": result.get("status"), "candidate_count": result.get("candidate_count", 0),
                          "error": result.get("error"), "runtime_status": result.get("runtime_status", "not_run")}
                record.update(creation_exit_code=proc.returncode,extraction_succeeded=result.get('extraction_succeeded',result.get('status') in {'method_drafts_created','atomic_resource_hints_only','repo_only_hints_created','no_supported_skill'}),execution_checks=result.get('runtime_checks',{}),archive_status='not_started')
                record.update(current_acceptance_validated=result.get('current_acceptance_validated', False),
                              candidate_paths=result.get('candidate_paths', []))
                record.update({k:result.get(k) for k in ('delivery_accepted','delivery_status','delivery_checks','creation_mode')})
                record['creation_seconds']=round(time.monotonic()-creation_started,3)
                run_records.append(record)
                print(json.dumps(record, ensure_ascii=True), flush=True)
                if result.get("status") in {"method_drafts_created", "atomic_resource_hints_only",
                                             "repo_only_hints_created"}:
                    publish_command=[sys.executable,str(HERE/"publish_run.py"),"--run-id",run_id,
                                     '--success-policy', 'archive' if args.draft_only else args.success_policy]
                    publish_started=time.monotonic()
                    if limit is not None:
                        from runtime_package import process
                        cap=min(600,creation_started+limit-time.monotonic(),deadline-time.monotonic() if deadline else 600)
                        try:
                            if cap<=0:raise subprocess.TimeoutExpired(publish_command,0)
                            observed=process(publish_command,timeout=cap,supervise=True)
                            publish=subprocess.CompletedProcess(publish_command,observed['exit_code'],observed['stdout'],observed['stderr'])
                        except subprocess.TimeoutExpired as exc:
                            publish=subprocess.CompletedProcess(publish_command,124,'','Publication budget exhausted: '+str(exc))
                    else:
                        publish=subprocess.run(publish_command,text=True,capture_output=True,encoding='utf-8',errors='replace')
                    record['publication_seconds']=round(time.monotonic()-publish_started,3)
                    from strict_acceptance import publication_completed, candidates
                    strict_rejected = publish.returncode == 2 and publication_completed(publish.stdout)
                    if publish.returncode and not strict_rejected:
                        record["publish_status"] = "failed"
                        record['archive_status']='failed'
                        record["publish_error"] = publish.stderr[-1200:]
                        record["publish_exit_code"] = publish.returncode
                        record["publish_error_kind"] = ("target_conflict" if "Publication target conflict" in publish.stderr
                                                         else "publication_failed")
                    else:
                        record["publish_status"] = "published_locally"
                        record['archive_status']='completed'
                        published_path=ROOT / "skills" / "generated" / run_id
                        try:publication=json.loads((published_path / "PUBLISHING.json").read_text(encoding='utf-8'))
                        except (OSError,ValueError) as exc:
                            record.update(publish_status='failed',archive_status='report_unreadable',
                                publish_error=repr(exc),publish_error_kind='archive_report_unreadable',
                                publication_manifest=str(published_path/'PUBLISHING.json'))
                            checkpoint('running')
                            continue
                        record['archived_candidate_count']=publication.get('candidate_count',record['candidate_count'])
                        record["execution_checks"] = publication.get("execution_checks", {})
                        record["execution_validated"] = publication.get("execution_validated", False)
                        record['current_acceptance_validated'] = (not strict_rejected and
                            record['current_acceptance_validated'] is True and publication.get('current_acceptance_validated') is True)
                        record['candidate_paths'] = [str(p) for p in candidates(published_path)]
                        record.update({k:publication.get(k) for k in ('delivery_accepted','delivery_status','delivery_checks')})
                        record['publish_exit_code'] = publish.returncode
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
              "execution_validation": execution_summary(run_records), "agent_effect_validation": "not_run",
              "runs": run_records, "published_paths": published}
    code=batch_exit(run_records,args.success_policy,args.target_candidates)
    if args.success_policy == 'execution':
        from delivery import record_passes as delivery_passes
        if not all(delivery_passes(r) for r in run_records): code=code or 2
    if deadline and time.monotonic()>=deadline and len(run_records)<len(jobs)*args.rounds:code=1
    publish_failed = code!=0
    checkpoint('finished_with_errors' if publish_failed else 'finished')
    if args.push and published:
        subprocess.run(["git", "add", *published], cwd=ROOT, check=True)
        subprocess.run(["git", "add", str(report_path.relative_to(ROOT))], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", f"Publish batch source-validated candidates {prefix}"], cwd=ROOT, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    print(json.dumps({"status": "batch_finished_with_errors" if publish_failed else "batch_finished", "report": str(report_path),
                      "published": len(published), "pushed": bool(args.push and published)}, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
