from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from creation_pipeline.paths import ROOT
from creation_pipeline.validation.checks import static_checks
from creation_pipeline.models import load_config
from creation_pipeline.artifacts.package import install, verify_output, verify_bundle
from .pipeline import build
from creation_pipeline.records import redact


def main(argv=None):
    parser = argparse.ArgumentParser(description="Discover reusable tool capabilities and build source-grounded skill packages")
    commands = parser.add_subparsers(dest="command", required=True)
    for operation in ("build", "discover"):
        child = commands.add_parser(operation)
        child.add_argument("config")
        child.add_argument("--no-adopt", action="store_true")
        child.add_argument("--state-dir", default=str(ROOT / ".pipeline"))
        child.add_argument("--keep-debug", action="store_true")
        child.add_argument("--preflight", action="store_true", help="Validate configuration only; no source fetching or model calls")
    child = commands.add_parser("resume", help="Resume an interrupted native run from its local checkpoint")
    child.add_argument("build_id")
    child.add_argument("--extra-turns", type=int, default=0, help="Explicitly extend the saved turn budget; does not extend time")
    child.add_argument("--rediscover", action="store_true", help="Re-enter discovery in the retained native session")
    child.add_argument("--state-dir", default=str(ROOT / ".pipeline"))
    child.add_argument("--no-adopt", action="store_true")
    child.add_argument("--keep-debug", action="store_true")
    for operation in ("pin", "unpin"):
        child = commands.add_parser(operation, help="Keep/release a registered batch workspace")
        child.add_argument("build_id")
        child.add_argument("--state-dir", default=str(ROOT / ".pipeline"))
    child = commands.add_parser("prune", help="Clean expired registered temporary artifacts")
    child.add_argument("--state-dir", default=str(ROOT / ".pipeline"))
    child.add_argument("--dry-run", action="store_true")
    child = commands.add_parser("retention", help="List managed and historical local directories")
    child.add_argument("--state-dir", default=str(ROOT / ".pipeline"))
    child = commands.add_parser("check")
    child.add_argument("path", help="Build output directory or standalone skill directory")
    child = commands.add_parser("install")
    child.add_argument("output")
    child.add_argument("--destination", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in ("build", "discover"):
            if args.preflight:
                config = load_config(args.config)
                result = {"status": "configuration_valid", "source_count": len(config["sources"]),
                          "source_availability": "not_checked", "model_calls": 0}
            else:
                result = build(args.config, args.state_dir, plan_only=args.command == "discover",
                               keep_debug=args.keep_debug, no_adopt=args.no_adopt,
                               notify=lambda m: print(m, file=sys.stderr, flush=True))
        elif args.command == "resume":
            result = build(state_root=args.state_dir, resume_id=args.build_id, keep_debug=args.keep_debug,
                no_adopt=args.no_adopt, rediscover=args.rediscover, extra_turns=args.extra_turns,
                notify=lambda m: print(m, file=sys.stderr, flush=True))
        elif args.command in ("pin", "unpin"):
            from creation_pipeline.retention import pin
            result = pin(args.state_dir, args.build_id, args.command == "pin")
        elif args.command == "prune":
            from creation_pipeline.retention import sweep
            result = sweep(args.state_dir, dry_run=args.dry_run)
        elif args.command == "retention":
            from creation_pipeline.records import read_json
            state = Path(args.state_dir)
            registrations = [read_json(p) for p in (state / "retention").glob("*.json")]
            known = {r["build_id"] for r in registrations}
            result = {"registered": registrations, "historical_unmanaged": [str(p) for base in ("runs", "outputs")
                for p in (state / base).glob("*") if p.is_dir() and p.name not in known]}
        elif args.command == "check":
            path = Path(args.path)
            if (path / "complete.json").is_file():
                from creation_pipeline.artifacts.package import archive_packages
                summary, packages = archive_packages(path)
                reports = [report for record, package in packages for report in static_checks(package, record["name"])]
                result = {"status": "fail" if any(r["status"] == "fail" for r in reports) else "pass",
                          "checks": reports, "recorded_build_status": summary["status"], "scope": "static_only"}
            elif (path / "summary.json").is_file():
                record, bundle = verify_bundle(path)
                reports = []
                for entity in record["entities"]:
                    directory = bundle / ("skills" if entity["kind"] == "skill" else "tools") / entity["name"]
                    if directory.exists():
                        reports += static_checks(directory, entity["name"], bundle=bundle, tool=entity["kind"] == "tool")
                result = {"status": "fail" if any(r["status"] == "fail" for r in reports) else "pass",
                          "checks": reports, "recorded_build_status": record["status"], "review_scope": "source_and_content_only"}
            elif (path / "build.json").is_file():
                record, package = verify_output(path)
                reports = static_checks(package, record["plan"]["name"])
                result = {"status": "fail" if any(r["status"] == "fail" for r in reports) else "pass",
                          "checks": reports, "recorded_build_status": record["status"],
                          "review_scope": "source_and_content_only", "scope": "manifest_and_static_only"}
            else:
                reports = static_checks(path)
                result = {"status": "fail" if any(r["status"] == "fail" for r in reports) else "pass",
                          "checks": reports, "review_scope": "source_and_content_only", "scope": "static_only_not_installation_approval"}
        elif args.command == "install":
            result = install(args.output, args.destination)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("status") in ("failed", "blocked", "fail", "partial", "interrupted", "incomplete") else 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "error", "error": redact(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
