#!/usr/bin/env python3
"""Publish source-validated extraction candidates and optionally push them."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from validate_tool_execution import validate as validate_execution

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ALLOWED = {"method_drafts_created", "atomic_resource_hints_only", "repo_only_hints_created"}


def run_command(*args: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{' '.join(args)} failed: {result.stderr[-1200:]}")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--push", action="store_true", help="Commit and push the generated candidates")
    parser.add_argument("--replace-existing", action="store_true", help="Replace a previous publication for this run ID")
    parser.add_argument("--commit-message", default=None)
    args = parser.parse_args()
    result_path = HERE / "results" / f"{args.run_id}.json"
    run_dir = HERE / "runs" / args.run_id
    if not result_path.is_file():
        parser.error(f"Missing result: {result_path}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("status") not in ALLOWED:
        parser.error(f"Run status {result.get('status')!r} is not publishable")
    source_drafts = run_dir / "drafts-v03"
    if not source_drafts.is_dir():
        parser.error(f"Missing rendered drafts: {source_drafts}")
    candidates = sorted(path for path in source_drafts.iterdir() if (path / "SKILL.md").is_file())
    if not candidates:
        parser.error("No SKILL.md candidates found")
    destination = ROOT / "skills" / "generated" / args.run_id
    if destination.exists() and not args.replace_existing:
        parser.error(f"Destination already exists: {destination}")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for candidate in candidates:
        shutil.copytree(candidate, destination / candidate.name)
    execution_checks = {}
    for candidate in candidates:
        report = validate_execution(destination / candidate.name)
        execution_checks[candidate.name] = report
        report_path = destination / candidate.name / "reports" / "execution.json"
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    statuses = {name: report['status'] for name, report in execution_checks.items()}
    executable_present = any(status != 'not_applicable' for status in statuses.values())
    all_executable_passed = executable_present and all(status in {'passed','not_applicable'} for status in statuses.values())
    publication_state = ('tool_execution_checked_candidate' if all_executable_passed
                         else 'tool_execution_failed_candidate' if 'failed' in statuses.values()
                         else 'tool_execution_unchecked_candidate' if executable_present
                         else 'source_validated_candidate')
    manifest = {
        "run_id": args.run_id,
        "paper_id": result.get("paper_id"),
        "model_origin": result.get("model_origin"),
        "source_scope": result.get("source_scope"),
        "source_text_complete": result.get("source_text_complete"),
        "candidate_count": len(candidates),
        "publication_state": publication_state,
        "execution_validated": all_executable_passed,
        "execution_checks": statuses,
        "agent_effect_validated": False,
        "note": "Source citations and format checked. Declared packaged script fixtures ran where present; this does not establish scientific correctness or agent utility.",
    }
    (destination / "PUBLISHING.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme = destination / "README.md"
    readme.write_text(
        "# Generated skill candidates\n\n"
        "These packages were generated from a cited extraction run. Packaged script fixture results, "
        "where applicable, are in each `reports/execution.json`. No agent utility test has been run. "
        "Review the source evidence and requirements before installation. See `PUBLISHING.json`.\n",
        encoding="utf-8",
    )
    relative = destination.relative_to(ROOT)
    print(json.dumps({"status": "published_locally", "destination": str(relative), "candidates": len(candidates)}, ensure_ascii=False))
    if args.push:
        message = args.commit_message or f"Publish source-validated candidates from {args.run_id}"
        run_command("git", "add", str(relative))
        run_command("git", "commit", "-m", message)
        push_output = run_command("git", "push", "origin", "main")
        print(json.dumps({"status": "published_remote", "destination": str(relative), "push": push_output}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
