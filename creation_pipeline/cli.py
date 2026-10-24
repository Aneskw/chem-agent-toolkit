from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyze import ROOT
from .checks import static_checks
from .models import load_config
from .package import install, verify_output, verify_bundle
from .pipeline import build
from .records import clean_run, redact


def main(argv=None):
    parser = argparse.ArgumentParser(description="Discover reusable tool capabilities and build source-grounded skill packages")
    commands = parser.add_subparsers(dest="command", required=True)
    for operation in ("build", "discover", "plan", "revise"):
        child = commands.add_parser(operation)
        child.add_argument("config", nargs="?")
        child.add_argument("--feedback-file")
        child.add_argument("--no-adopt", action="store_true")
        child.add_argument("--plan", dest="plan_path", help="Continue a saved plan without rediscovery")
        child.add_argument("--state-dir", default=str(ROOT / ".pipeline"))
        child.add_argument("--keep-debug", action="store_true")
        child.add_argument("--execute-generated-checks", action="store_true",
                           help="Trust and run model-proposed code with this user's permissions")
        child.add_argument("--preflight", action="store_true", help="Validate configuration only; no source fetching or model calls")
    child = commands.add_parser("resume", help="Resume an interrupted native run from its local checkpoint")
    child.add_argument("build_id")
    child.add_argument("--extra-turns", type=int, default=0, help="Explicitly extend the saved turn budget; does not extend time")
    child.add_argument("--rediscover", action="store_true", help="Re-enter discovery in the retained native session")
    child.add_argument("--state-dir", default=str(ROOT / ".pipeline"))
    child.add_argument("--no-adopt", action="store_true")
    child.add_argument("--keep-debug", action="store_true")
    child.add_argument("--execute-generated-checks", action="store_true")
    child = commands.add_parser("check")
    child.add_argument("path", help="Build output directory or standalone skill directory")
    child = commands.add_parser("install")
    child.add_argument("output")
    child.add_argument("--destination", required=True)
    child = commands.add_parser("clean")
    child.add_argument("build_id")
    child.add_argument("--state-dir", default=str(ROOT / ".pipeline"))
    child.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command in ("build", "discover", "plan", "revise"):
            if bool(args.config) == bool(args.plan_path):
                raise ValueError("Supply one configuration or --plan path")
            if args.command == "revise" and (not args.plan_path or not args.feedback_file):
                raise ValueError("revise requires --plan and --feedback-file")
            if args.preflight:
                if args.plan_path:
                    raise ValueError("Preflight takes a configuration; continuation validates saved sources itself")
                config = load_config(args.config)
                result = {"status": "configuration_valid", "source_count": len(config["sources"]),
                          "source_availability": "not_checked", "model_calls": 0}
            else:
                result = build(args.config, args.state_dir, plan_only=args.command in ("discover", "plan", "revise"), plan_path=args.plan_path,
                               keep_debug=args.keep_debug, execute_generated=args.execute_generated_checks,
                               no_adopt=args.no_adopt,
                               feedback=Path(args.feedback_file).read_text(encoding="utf-8") if args.command == "revise" else None,
                               notify=lambda m: print(m, file=sys.stderr, flush=True))
        elif args.command == "resume":
            result = build(state_root=args.state_dir, resume_id=args.build_id, keep_debug=args.keep_debug,
                no_adopt=args.no_adopt, execute_generated=args.execute_generated_checks, rediscover=args.rediscover, extra_turns=args.extra_turns,
                notify=lambda m: print(m, file=sys.stderr, flush=True))
        elif args.command == "check":
            path = Path(args.path)
            if (path / "summary.json").is_file():
                record, bundle = verify_bundle(path)
                reports = []
                for entity in record["entities"]:
                    directory = bundle / ("skills" if entity["kind"] == "skill" else "tools") / entity["name"]
                    if directory.exists():
                        reports += static_checks(directory, entity["name"], bundle=bundle, tool=entity["kind"] == "tool")
                result = {"status": "fail" if any(r["status"] == "fail" for r in reports) else "pass",
                          "checks": reports, "recorded_build_status": record["status"], "execution": "not_rerun"}
            elif (path / "build.json").is_file():
                record, package = verify_output(path)
                reports = static_checks(package, record["plan"]["name"], record.get("coverage"))
                result = {"status": "fail" if any(r["status"] == "fail" for r in reports) else "pass",
                          "checks": reports, "recorded_build_status": record["status"],
                          "execution": "not_rerun", "scope": "manifest_and_static_only"}
            else:
                reports = static_checks(path)
                result = {"status": "fail" if any(r["status"] == "fail" for r in reports) else "pass",
                          "checks": reports, "execution": "not_run", "scope": "static_only_not_installation_approval"}
        elif args.command == "install":
            result = install(args.output, args.destination)
        else:
            result = clean_run(args.state_dir, args.build_id, args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("status") in ("failed", "blocked", "fail", "partial", "interrupted", "incomplete") else 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "error", "error": redact(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
