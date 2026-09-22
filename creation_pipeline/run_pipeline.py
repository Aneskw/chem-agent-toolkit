#!/usr/bin/env python3
"""Source lock -> model extraction -> citation audit -> v0.3 draft pipeline."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from decision_library import build_library

HERE = Path(__file__).resolve().parent


class MissingPaperText(Exception):
    pass


def call(*args: str) -> None:
    subprocess.run([sys.executable, *args], check=True)


def main() -> int:
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
    args = p.parse_args()
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
                 "--paper-id", args.paper_id, "--model", args.model)
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
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        status.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    run.mkdir(parents=True, exist_ok=True)
    (run / "pipeline_status.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    results = HERE / "results"
    results.mkdir(exist_ok=True)
    (results / f"{run_id}.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(status, ensure_ascii=False))
    return 0 if status["status"] in {"method_drafts_created", "atomic_resource_hints_only",
                                      "repo_only_hints_created", "no_supported_skill"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
