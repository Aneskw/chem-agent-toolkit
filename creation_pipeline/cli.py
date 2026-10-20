from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyze import ROOT
from .checks import static_checks
from .models import load_config
from .package import install, verify_output
from .pipeline import build
from .records import clean_run, redact


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build one model-authored tool skill; no automatic installation or Agent benchmark")
    commands = parser.add_subparsers(dest="command", required=True)
    for operation in ("build", "plan"):
        child = commands.add_parser(operation)
        child.add_argument("config")
        child.add_argument("--state-dir", default=str(ROOT / ".pipeline"))
        child.add_argument("--keep-debug", action="store_true")
        child.add_argument("--execute-generated-checks", action="store_true",
                           help="Trust and run model-proposed code with this user's permissions")
        child.add_argument("--preflight", action="store_true", help="Validate configuration only; no source fetching or model calls")
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
        if args.command in ("build", "plan"):
            if args.preflight:
                config = load_config(args.config)
                result = {"status": "configuration_valid", "source_count": len(config["sources"]),
                          "source_availability": "not_checked", "model_calls": 0}
            else:
                result = build(args.config, args.state_dir, plan_only=args.command == "plan",
                               keep_debug=args.keep_debug, execute_generated=args.execute_generated_checks,
                               notify=lambda m: print(m, file=sys.stderr, flush=True))
        elif args.command == "check":
            path = Path(args.path)
            if (path / "build.json").is_file():
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
        return 1 if result.get("status") in ("failed", "blocked", "fail") else 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "error", "error": redact(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
