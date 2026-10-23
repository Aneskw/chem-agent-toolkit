#!/usr/bin/env python3
"""Source lock -> model extraction -> citation audit -> v0.3 draft pipeline."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from decision_library import build_library

HERE = Path(__file__).resolve().parent
RUN_DEADLINE=None


class MissingPaperText(Exception):
    pass


def call(*args: str) -> None:
    if RUN_DEADLINE is None:
        result = subprocess.run([sys.executable, *args], text=True, capture_output=True, encoding='utf-8', errors='replace')
        if result.stdout: print(result.stdout, end='')
        if result.returncode: raise subprocess.CalledProcessError(result.returncode, args, output=result.stdout, stderr=result.stderr)
    else:
        from runtime_package import process
        remaining=RUN_DEADLINE-time.monotonic()
        if remaining<=0:raise subprocess.TimeoutExpired(args,0)
        result=process([sys.executable,*args],timeout=remaining,supervise=True)
        if result['stdout']:print(result['stdout'],end='')
        if result['exit_code']:raise subprocess.CalledProcessError(result['exit_code'],args,output=result['stdout'],stderr=result['stderr'])


def main() -> int:
    started=time.monotonic()
    p = argparse.ArgumentParser()
    p.add_argument("--paper-id", help="ID from the literature catalog, or job ID in --config")
    p.add_argument("--config", type=Path, help="Local source manifest; accepts paper, database, tool or model documentation")
    p.add_argument("--model", default="gpt-6-astra")
    p.add_argument("--run-id", default=None)
    p.add_argument("--response-file", type=Path, help="Replay a saved model JSON for deterministic testing")
    p.add_argument("--skip-collect", action="store_true", help="Use already collected, locked local sources")
    p.add_argument("--allow-repo-only", action="store_true", help="Create repository hints, never paper-derived skill drafts")
    p.add_argument("--draft-eval-tasks", action="store_true",
                   help="also propose two positive and two negative decision-task drafts per method skill; human review still required")
    p.add_argument("--runtime-mode", choices=("auto", "off", "docker"), default="auto", help='Deprecated: default auto follows each candidate requirement')
    p.add_argument('--draft-only', action='store_true', help='Generate source-checked drafts; never claim delivery or execution acceptance')
    p.add_argument("--tool-bindings", type=Path)
    p.add_argument('--publish-local',action='store_true',help='Archive candidates locally after extraction and optional Docker acceptance; never pushes')
    p.add_argument('--success-policy',choices=('delivery','creation','execution','draft'),default='delivery')
    p.add_argument('--total-seconds',type=int,help='Bound the complete invocation including extraction, Docker and local archive')
    p.add_argument('--extraction-timeout',type=int,default=900,help='Per model call timeout during extraction/review')
    args = p.parse_args()
    global RUN_DEADLINE
    if args.total_seconds is not None and args.total_seconds<1:p.error('total-seconds must be positive')
    if args.extraction_timeout<1:p.error('extraction-timeout must be positive')
    RUN_DEADLINE=time.monotonic()+args.total_seconds if args.total_seconds else None
    from delivery import cli_mode
    if args.success_policy == 'draft': args.draft_only = True
    cli_mode(args, p)
    if args.config:
        config = args.config.resolve()
        settings = json.loads(config.read_text(encoding="utf-8"))
        jobs = settings.get("jobs", [])
        if len(jobs) != 1:
            p.error("--config currently requires exactly one job")
        job_id = jobs[0]["paper_id"]
        if args.paper_id and args.paper_id != job_id:
            p.error("--paper-id must match the job ID in --config")
        args.paper_id = job_id
    elif not args.paper_id:
        p.error("provide --paper-id or --config")
    run_id = args.run_id or f"{args.paper_id}-{datetime.now():%Y%m%d-%H%M%S}"
    run = HERE / "runs" / run_id
    if run.exists():
        p.error(f"run already exists: {run}")
    status = {"run_id": run_id, "paper_id": args.paper_id, "stage": "started", "status": "running"}
    status.update(runtime_mode=args.runtime_mode, runtime_status="not_run", agent_effect_status="not_evaluated")
    if args.tool_bindings:status['tool_bindings']=str(args.tool_bindings.resolve())
    try:
        if not args.skip_collect and not args.config:
            call(str(HERE / "collect.py"), "--paper-id", args.paper_id)
        status["stage"] = "source_collected"
        if not args.config:
            config = HERE / "cache" / args.paper_id / "config.json"
        if not config.is_file():
            raise FileNotFoundError(f"Missing collected source config: {config}")
        call(str(HERE / "core" / "creation.py"), "prepare", "--config", str(config), "--out", str(run))
        prepared = json.loads((run / "prepared.json").read_text(encoding="utf-8"))
        if prepared["jobs"][0]["status"] != "prepared":
            raise ValueError(prepared["jobs"][0].get("error", "source preparation failed"))
        bundle = json.loads((run / "jobs" / args.paper_id / "bundle.json").read_text(encoding="utf-8"))
        status["omitted_source_sections"] = len(bundle.get("omitted", []))
        status["source_text_complete"] = not bundle.get("omitted")
        primary_present = bundle["coverage"].get("primary_text_supplied", bundle["coverage"]["paper_text_supplied"])
        source_type = bundle.get("source_type", "paper")
        status["source_scope"] = source_type + ("_primary_text" if primary_present else "_secondary_only")
        if not primary_present and not args.allow_repo_only:
            raise MissingPaperText(f"No {bundle.get('primary_role', 'paper')} text in the source bundle; secondary material alone is insufficient")
        status["stage"] = "bundle_prepared"
        response_dir = run / "responses"
        response_dir.mkdir()
        response = response_dir / f"{args.paper_id}.json"
        if args.response_file:
            shutil.copyfile(args.response_file, response)
            status["model_origin"] = "saved_response_replay"
        else:
            call(str(HERE / "codex_extract.py"), "--run", str(run),
                 "--paper-id", args.paper_id, "--model", args.model,'--timeout',str(args.extraction_timeout))
            status["model_origin"] = "codex_cli"
        status["stage"] = "model_response_received"
        repaired_dir = run / "checked_responses"
        repaired_dir.mkdir()
        call(str(HERE / "repair_citation_spans.py"), "--response", str(response),
             "--bundle", str(run / "jobs" / args.paper_id / "bundle.json"),
             "--output", str(repaired_dir / f"{args.paper_id}.json"))
        call(str(HERE / "core" / "creation.py"), "import-response", "--run", str(run),
             "--responses", str(repaired_dir), "--origin", "codex_current_task")
        extraction = json.loads((run / "import_results" / "summary.json").read_text(encoding="utf-8"))
        job = extraction["jobs"][0]
        if job["status"] not in {"candidates_validated", "no_supported_skill"}:
            raise ValueError(job.get("error", "citation audit failed"))
        status.update(extraction_succeeded=True,extraction_status=job['status'],candidate_count=job.get('candidate_count',0))
        contract_file = run / "import_results" / args.paper_id / "operational-contract.json"
        response_data = json.loads(contract_file.read_text(encoding="utf-8"))
        kind_counts = {kind: sum(item["kind"] == kind for item in response_data["candidates"])
                       for kind in ("method_procedure", "tool_usage")}
        status["stage"] = "citations_validated"
        library = build_library([response_data])
        (run / "decision_library.json").write_text(
            json.dumps(library, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        status["decision_rules"] = library["unique_rules"]
        status["utility"] = "not_evaluated"
        if job["status"] == "candidates_validated":
            drafts = run / "drafts-v03"
            call(str(HERE / "render_drafts_v03.py"), "--run", str(run),
                 "--paper-id", args.paper_id, "--out", str(drafts))
            for folder in drafts.iterdir():
                call(str(HERE / "validate_skill_format.py"), str(folder))
            from delivery import stage
            status.update(stage(drafts,args.paper_id,args.tool_bindings,
                deadline=RUN_DEADLINE-(30 if args.publish_local else 0) if RUN_DEADLINE else None,
                draft_only=args.draft_only))
            if args.draft_eval_tasks:
                task_drafts = run / "evaluation_task_drafts"
                task_drafts.mkdir()
                method_names = [c["name"] for c in response_data["candidates"]
                                if c["kind"] == "method_procedure"]
                for name in method_names:
                    call(str(HERE.parent / "evaluation" / "method_decisions" / "draft_tasks.py"),
                         "--skill", str(drafts / name / "SKILL.md"),
                         "--output", str(task_drafts / f"{name}.json"), "--model", args.model)
                status["evaluation_task_drafts"] = len(method_names)
                status["evaluation_task_drafts_state"] = "draft_requires_review"
        if job["status"] == "no_supported_skill":
            outcome = "no_supported_skill"
        elif not primary_present:
            outcome = "repo_only_hints_created"
        elif kind_counts["method_procedure"]:
            outcome = "method_drafts_created"
        else:
            outcome = "atomic_resource_hints_only"
        status["extraction_status"] = outcome
        status.update({"stage": "drafts_rendered" if job["status"] == "candidates_validated" else "no_supported_skill",
                       "status": outcome, "candidate_kinds": kind_counts,
                       "candidate_count": job.get("candidate_count", 0),
                       "contract_version": response_data["contract_version"],
                       "contract_file": str(contract_file.relative_to(HERE.parent)),
                       "checks": job.get("checks", []),
                       "source_bundle_sha256": job.get("bundle_sha256"),
                       "response_sha256": job.get("response_sha256"),
                       "run_dir": str(run.relative_to(HERE.parent))})
    except MissingPaperText as exc:
        status.update(status="primary_text_missing", error=str(exc))
    except (OSError, ValueError, subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        status.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        if isinstance(exc,subprocess.CalledProcessError):
            status['failure_details']={'command':exc.cmd,'exit_code':exc.returncode,
                'stdout_tail':(exc.output or '')[-2000:],'stderr_tail':(exc.stderr or '')[-2000:]}
        elif isinstance(exc,subprocess.TimeoutExpired):
            status['failure_details']={'command':exc.cmd,'timeout_seconds':exc.timeout,
                'scope':getattr(exc,'scope',None),'cleanup':getattr(exc,'cleanup',[])}
    from workflow_state import CREATED
    from strict_acceptance import evaluate, record_passes, candidates, publication_completed
    status.update(success_policy=args.success_policy,extraction_succeeded=status.get('extraction_succeeded',False) or status['status'] in CREATED|{'no_supported_skill'},
                  archive_status='not_requested',execution_passed_candidates=sum(s=='execution_passed' for s in status.get('runtime_checks',{}).values()))
    status.update(evaluate(candidates(run / 'drafts-v03'), status.get('candidate_count', 0)))
    from delivery import evaluate as delivery_evaluate
    status.update(delivery_evaluate(candidates(run/'drafts-v03'),status.get('candidate_count',0),
                                   'draft' if args.draft_only else 'delivery'))
    run.mkdir(parents=True, exist_ok=True)
    (run / "pipeline_status.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    results = HERE / "results"
    results.mkdir(exist_ok=True)
    (results / f"{run_id}.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if args.publish_local and status['status'] in CREATED:
        try:
            call(str(HERE/'publish_run.py'),'--run-id',run_id,'--success-policy',
                 'archive' if args.draft_only else args.success_policy)
            publication=json.loads((HERE.parent/'skills/generated'/run_id/'PUBLISHING.json').read_text(encoding='utf-8'))
            status.update(archive_status='completed',publication_manifest=str(HERE.parent/'skills/generated'/run_id/'PUBLISHING.json'),
                          execution_passed_candidates=publication['execution_passed_candidates'])
        except subprocess.CalledProcessError as exc:
            if exc.returncode == 2 and publication_completed(exc.output):
                status.update(archive_status='completed', current_acceptance_validated=False, acceptance_error=str(exc))
            else:
                status.update(archive_status='failed',archive_error=str(exc))
        except (OSError,subprocess.TimeoutExpired) as exc:
            status.update(archive_status='failed',archive_error=str(exc))
    exit_code=(1 if not status['extraction_succeeded'] or status['archive_status']=='failed' else
               2 if args.success_policy in {'delivery','execution'} and not status['delivery_accepted'] else
               2 if args.success_policy=='execution' and (not status.get('candidate_count') or status['execution_passed_candidates']!=status['candidate_count']
                                                         or not record_passes(status)) else 0)
    if status['archive_status']=='failed' or not status['extraction_succeeded']:
        status.update(delivery_accepted=False, delivery_status='blocked')
    status['exit_code']=exit_code
    status['elapsed_seconds']=round(time.monotonic()-started,3)
    for path in [run/'pipeline_status.json',results/f'{run_id}.json']:
        path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(status, ensure_ascii=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
