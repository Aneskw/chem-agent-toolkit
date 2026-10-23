#!/usr/bin/env python3
"""Publish source-validated extraction candidates and optionally push them."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from validate_tool_execution import validate as validate_execution
from runtime_docker import evidence, aggregate
from publication_transaction import PublicationTransaction

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ALLOWED = {"method_drafts_created", "atomic_resource_hints_only", "repo_only_hints_created"}
CATEGORY_ROOTS = {
    "database": Path("databases-skills") / "generated",
    "tool": Path("tools-skills") / "generated",
    "model": Path("models-skills") / "open-models",
    "workflow": Path("workflows") / "generated",
}
MODEL_SIGNALS = re.compile(
    r"\b(?:ai|machine learning|deep learning|neural|transformer|model|inference|prediction|"
    r"retrosynthesis|reaction prediction|beam search|checkpoint|training|graphretro|graph2smiles|"
    r"localretro|retroxpert|retroprime|wln)\b",
    re.IGNORECASE,
)


def run_command(*args: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{' '.join(args)} failed: {result.stderr[-1200:]}")
    return result.stdout.strip()


def load_run_bundle(run_dir: Path) -> dict:
    """Load one extraction bundle to recover source type and title for routing."""
    bundles = sorted((run_dir / "jobs").glob("*/bundle.json"))
    if not bundles:
        return {}
    try:
        return json.loads(bundles[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def classify_candidate(candidate: Path, bundle: dict, override: str) -> str:
    """Route a candidate to a repository category without treating every paper as a model."""
    if override != "auto":
        return override
    source_type = str(bundle.get("source_type", "paper")).lower()
    if source_type in {"database", "tool", "model"}:
        return source_type
    skill_text = (candidate / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    evidence = "\n".join((str(bundle.get("title", "")), candidate.name, skill_text[:5000]))
    return "model" if MODEL_SIGNALS.search(evidence) else "workflow"


def stage_reports(args, result, candidates, destination, classifications):
    execution_checks = {}
    for candidate in candidates:
        packaged = destination / candidate.name
        if result.get("runtime_mode") == "docker" or (packaged / "runtime").exists():
            report=evidence(packaged)
        elif getattr(args,'success_policy','delivery') == 'archive':
            report=validate_execution(packaged)  # Explicit legacy archival path only.
        else:
            from delivery import candidate_report
            assessed=candidate_report(packaged)
            report={'status':'not_required' if assessed.get('requirement')=='not_required' and assessed['deliverable'] else 'needs_review',
                    'error':assessed.get('error'),'execution_accepted':False}
        if (packaged / "runtime/package.json").is_file() and report["status"] != "execution_passed":
            # Never archive stale positive claims when current acceptance fails.
            from runtime_model_lifecycle import refresh_docs
            from runtime_common import withdraw_claims
            for copy in (packaged,):
                if (copy / "runtime/package.json").is_file():
                    try:
                        refresh_docs(copy, report["status"])
                    except (OSError, ValueError, KeyError, TypeError):
                        # Malformed artifacts cannot be made deliverable by publication.
                        withdraw_claims(copy, report["status"])
        execution_checks[candidate.name] = report
        report_path = destination / candidate.name / "reports" / "execution.json"
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    statuses = {name: report['status'] for name, report in execution_checks.items()}
    from strict_acceptance import reports_pass
    executable_present = any(status not in {'not_applicable', 'not_required'} for status in statuses.values())
    all_executable_passed = executable_present and all(status in {'passed','not_applicable','execution_passed','not_required'} for status in statuses.values())
    observed_failed=any('failed' in report.get('validation',{}).values() for report in execution_checks.values())
    publication_state = ('tool_execution_checked_candidate' if all_executable_passed
                         else 'tool_execution_failed_candidate' if observed_failed or set(statuses.values()) & {'failed','execution_failed','build_failed','blocked_resources'}
                         else 'tool_execution_unchecked_candidate' if executable_present
                         else 'source_validated_candidate')
    manifest = {
        "run_id": args.run_id,
        "publication_complete": True,
        "paper_id": result.get("paper_id"),
        "model_origin": result.get("model_origin"),
        "source_scope": result.get("source_scope"),
        "source_text_complete": result.get("source_text_complete"),
        "candidate_count": len(candidates),
        "archive_status": "completed",
        "execution_passed_candidates": sum(s=='execution_passed' for s in statuses.values()),
        "container_acceptance_status": 'passed' if all(s=='execution_passed' for s in statuses.values()) else 'partial' if 'execution_passed' in statuses.values() else 'not_accepted',
        "publication_state": publication_state,
        "execution_validated": all_executable_passed,
        "acceptance_versions": {name: report.get('acceptance_version', 1) for name, report in execution_checks.items()},
        "current_acceptance_validated": reports_pass(execution_checks, len(candidates)),
        "execution_checks": statuses,
        "layered_validation": {name: report.get("validation", {}) for name, report in execution_checks.items()},
        "extraction_status": result.get("extraction_status", result.get("status")),
        "runtime_status": aggregate(statuses.values()) if any(r.get("backend") == "docker" for r in execution_checks.values()) else "not_run",
        "agent_effect_status": "not_evaluated",
        "classifications": classifications,
        "candidate_identities": {c.name: __import__('candidate_identity').load(c) for c in candidates},
        "agent_effect_validated": False,
        "note": "Source citations and format checked. Declared packaged script fixtures ran where present; this does not establish scientific correctness or agent utility.",
    }
    from delivery import evaluate as delivery_evaluate
    manifest.update(delivery_evaluate([destination/c.name for c in candidates],len(candidates),
                                     'draft' if result.get('creation_mode') == 'draft' else 'delivery'))
    manifest['delivery_publication_state'] = 'accepted_delivery' if manifest['delivery_accepted'] else 'unaccepted_archive'
    (destination / "PUBLISHING.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme = destination / "README.md"
    readme.write_text(
        "# Generated skill candidates\n\n"
        "These packages were generated from a cited extraction run. Packaged script fixture results, "
        "where applicable, are in each `reports/execution.json`. No agent utility test has been run. "
        "Review the source evidence and requirements before installation. See `PUBLISHING.json`.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--push", action="store_true", help="Commit and push the generated candidates")
    parser.add_argument("--replace-existing", action="store_true", help="Explicitly replace existing audit and category targets, with rollback on failure")
    parser.add_argument('--success-policy',choices=('delivery','archive','execution'),default='delivery',help='Default requirement-aware delivery; archive explicitly stores unaccepted artifacts')
    parser.add_argument(
        "--category",
        choices=("auto", "database", "tool", "model", "workflow"),
        default="auto",
        help="Category mirror; auto uses source type and model-method signals",
    )
    parser.add_argument("--commit-message", default=None)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.run_id) or args.run_id in {".", ".."}:
        parser.error("run-id must be a single safe directory name")
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
    bundle = load_run_bundle(run_dir)
    classifications = {}
    classified_paths = []
    targets = []
    for candidate in candidates:
        category = classify_candidate(candidate, bundle, args.category)
        classified = ROOT / CATEGORY_ROOTS[category] / candidate.name
        classifications[candidate.name] = {"category": category, "path": str(classified.relative_to(ROOT))}
        classified_paths.append(classified.relative_to(ROOT))
        targets.append(classified)
    # Preflight every mirror AND audit target before copying or replacing anything.
    # Commit the audit manifest last; each earlier directory move is recoverable.
    try:
        transaction = PublicationTransaction(ROOT, args.run_id, [*targets, destination], args.replace_existing)
    except ValueError as exc:
        parser.error(str(exc))
    with transaction:
        staged = transaction.stage(destination)
        staged.mkdir()
        for candidate in candidates:
            shutil.copytree(candidate, staged / candidate.name)
        stage_reports(args, result, candidates, staged, classifications)
        staged_manifest=json.loads((staged/'PUBLISHING.json').read_text(encoding='utf-8'))
        for name,row in staged_manifest['delivery_checks'].items():
            row['path']=str((destination/name).resolve())
        staged_manifest['candidate_paths']=[str((destination/c.name).resolve()) for c in candidates]
        (staged/'PUBLISHING.json').write_text(json.dumps(staged_manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        for candidate, target in zip(candidates, targets):
            shutil.copytree(staged / candidate.name, transaction.stage(target))
        transaction.commit()
    relative = destination.relative_to(ROOT)
    print(json.dumps({
        "status": "published_locally",
        "destination": str(relative),
        "classified_destinations": [str(path) for path in classified_paths],
        "candidates": len(candidates),
    }, ensure_ascii=False))
    if args.push:
        message = args.commit_message or f"Publish source-validated candidates from {args.run_id}"
        run_command("git", "add", str(relative), *(str(path) for path in classified_paths))
        run_command("git", "commit", "-m", message)
        push_output = run_command("git", "push", "origin", "main")
        print(json.dumps({"status": "published_remote", "destination": str(relative), "push": push_output}, ensure_ascii=False))
    manifest=json.loads((destination/'PUBLISHING.json').read_text(encoding='utf-8'))
    from strict_acceptance import record_passes
    strict_record = dict(manifest, candidate_paths=[str(destination / c.name) for c in candidates])
    if args.success_policy == 'delivery':
        from delivery import record_passes as delivery_passes
        return 0 if manifest['delivery_accepted'] and delivery_passes(strict_record) else 2
    return 2 if args.success_policy=='execution' and (
        not manifest['delivery_accepted'] or manifest['execution_passed_candidates']!=len(candidates) or not record_passes(strict_record)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
