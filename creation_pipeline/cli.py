from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from creation_pipeline.paths import ROOT
from creation_pipeline.validation.checks import static_checks
from creation_pipeline.models import load_config
from creation_pipeline.artifacts.package import install, verify_bundle, manifest
from .pipeline import build
from creation_pipeline.records import clean_run, redact


def main(argv=None):
    parser = argparse.ArgumentParser(description="Discover reusable tool capabilities and build source-grounded skill packages")
    commands = parser.add_subparsers(dest="command", required=True)
    child = commands.add_parser('init', help='Create the portable descriptor example configuration; never overwrites')
    child.add_argument('--model', required=True, help='A model identifier available to your own Codex account')
    child.add_argument('--output', required=True)
    child = commands.add_parser('doctor', help='Zero-inference prerequisites and Codex flag/feature compatibility')
    child.add_argument('config')
    child.add_argument('--offline', action='store_true', help='Skip Docker observations; runtime availability stays deferred')
    child = commands.add_parser('manage', help='Versioned local management DTO; existing execution/qualification chain')
    child.add_argument('request', help='JSON request envelope for chem-local-management/v1')
    child = commands.add_parser('readiness', help='Observe prerequisites before inference; no construction, repair or qualification')
    child.add_argument('config')
    child.add_argument('--offline', action='store_true', help='Do not probe Docker; runtime availability remains deferred')
    child.add_argument('--mode', choices=('build','discover','draft'), default='build')
    for operation in ("build", "discover", "plan", "revise"):
        child = commands.add_parser(operation)
        child.add_argument("config", nargs="?")
        child.add_argument("--feedback-file")
        child.add_argument("--no-adopt", action="store_true")
        child.add_argument("--draft-only", action="store_true", help="Create a candidate draft without formal qualification or execution")
        child.add_argument("--library-dir", default=str(ROOT / "skills"))
        child.add_argument("--plan", dest="plan_path", help="Continue a saved plan without rediscovery")
        child.add_argument("--state-dir", default=str(ROOT / ".pipeline"))
        child.add_argument("--keep-debug", action="store_true")
        child.add_argument("--preflight", action="store_true", help="Validate configuration only; no source fetching or model calls")
    child = commands.add_parser("resume", help="Resume an interrupted native run from its local checkpoint")
    child.add_argument("build_id")
    child.add_argument("--extra-turns", type=int, default=0, help="Explicitly extend the saved turn budget; does not extend time")
    child.add_argument("--rediscover", action="store_true", help="Re-enter discovery in the retained native session")
    child.add_argument("--state-dir", default=str(ROOT / ".pipeline"))
    child.add_argument("--no-adopt", action="store_true")
    child.add_argument("--draft-only", action="store_true")
    child.add_argument("--library-dir", default=str(ROOT / "skills"))
    child.add_argument("--keep-debug", action="store_true")
    child = commands.add_parser("check")
    child.add_argument("path", help="Build output directory or standalone skill directory")
    child.add_argument("--config", help="Audit actual file paths against original caller requirements; no model calls or qualification inheritance")
    child = commands.add_parser("install")
    child.add_argument("output")
    child.add_argument("--destination", required=True)
    child.add_argument("--name", help="Install a named accepted entry from a catalog library")
    child.add_argument("--include-pending", action="store_true", help="Explicitly install an unverified pending Skill")
    child = commands.add_parser("library", help="Query the catalog; candidates require explicit selection")
    child.add_argument("path")
    child.add_argument("--name")
    child.add_argument("--include-candidates", action="store_true")
    child = commands.add_parser("clean")
    child.add_argument("build_id")
    child.add_argument("--state-dir", default=str(ROOT / ".pipeline"))
    child.add_argument("--dry-run", action="store_true")
    child = commands.add_parser("runtime-build", help="Rebuild an explicit stored candidate and execute its locked checks; no authoring")
    child.add_argument("library")
    child.add_argument("--candidate", required=True)
    child.add_argument("--resource-refs", help="JSON file mapping required resource descriptions to host references; never credential values")
    child = commands.add_parser("runtime-prepare", help="Prepare a new runtime revision of an explicitly selected candidate, preserving authored files and locked tests")
    child.add_argument("library")
    child.add_argument("--candidate", required=True)
    child.add_argument("--spec", required=True, help="JSON runtime preparation settings")
    child.add_argument('--oracle-correction', help='JSON reason and source citations; invokes independent review before changing locked assertions')
    child = commands.add_parser('runtime-validate', help='Execute locked checks for an explicit candidate using its bound image')
    child.add_argument('library')
    child.add_argument('--candidate', required=True)
    child.add_argument('--resource-refs')
    child = commands.add_parser('runtime-resume', help='Resume an explicit durable candidate; reuse verified build or rebuild, then revalidate')
    child.add_argument('library')
    child.add_argument('--candidate', required=True)
    child.add_argument('--resource-refs')
    child.add_argument('--recover-lock', action='store_true', help='Release only a provably dead local catalog lock')
    child = commands.add_parser('runtime-inspect', help='Inspect current recovery action and blockers without authoring')
    child.add_argument('library')
    child.add_argument('--candidate', required=True)
    child = commands.add_parser('runtime-shared-inspect', help='Read-only shared dependency environment identity observations; never grants skill qualification')
    child.add_argument('--root', help='Override the host-configured shared environment directory')
    child.add_argument('--offline', action='store_true', help='Read historical records without Docker/model calls; availability is unverified')
    child = commands.add_parser('runtime-tools-inspect', help='Read-only exact local ToolArtifact observations; never grants qualification')
    child.add_argument('--root')
    child.add_argument('--offline', action='store_true')
    child = commands.add_parser('runtime-import', help='Import frozen native output or installed runtime envelope as durable recovery input')
    child.add_argument('source')
    child.add_argument('library')
    child.add_argument('--candidate', required=True)
    child = commands.add_parser('runtime-relocate', help='Verify portable delivery, withdraw inherited qualification and optionally revalidate')
    child.add_argument('library')
    child.add_argument('--candidate', required=True)
    child.add_argument('--revalidate', action='store_true')
    child.add_argument('--recover-lock', action='store_true')
    child = commands.add_parser("promote", help="Promote a pending Skill using explicit manual verification evidence")
    child.add_argument("library")
    child.add_argument("name")
    child.add_argument("--report", required=True)
    for operation in ("pin", "unpin", "prune"):
        child = commands.add_parser(operation, help="Manage archived grouped workspaces")
        child.add_argument("--state-dir", default=str(ROOT / ".pipeline"))
        if operation == "prune":
            child.add_argument("--older-than-days", type=int, default=7)
            child.add_argument("--dry-run", action="store_true")
        else:
            child.add_argument("build_id")
    args = parser.parse_args(argv)
    try:
        if args.command in ("pin", "unpin"):
            from creation_pipeline.shared.retention import pin
            result = pin(args.state_dir, args.build_id, args.command == "pin")
        elif args.command == "prune":
            from creation_pipeline.shared.retention import sweep
            result = sweep(args.state_dir, args.older_than_days, args.dry_run)
        elif args.command == "promote":
            from creation_pipeline.shared.delivery import promote
            result = promote(args.library, args.name, json.loads(Path(args.report).read_text(encoding="utf-8")))
        elif args.command == 'init':
            from creation_pipeline.onboarding import initialize
            result = initialize(args.output,args.model)
        elif args.command == 'doctor':
            from creation_pipeline.doctor import from_config
            result = from_config(args.config,args.offline)
        elif args.command == 'manage':
            from creation_pipeline.management import from_file, exit_code
            result = from_file(args.request)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return exit_code(result)
        elif args.command == 'readiness':
            from creation_pipeline.readiness import from_config
            result = from_config(args.config, args.mode, args.offline)
        elif args.command in ("build", "discover", "plan", "revise"):
            if bool(args.config) == bool(args.plan_path):
                raise ValueError("Supply one configuration or --plan path")
            if args.command == "revise" and (not args.plan_path or not args.feedback_file):
                raise ValueError("revise requires --plan and --feedback-file")
            if args.preflight:
                if args.plan_path:
                    raise ValueError("Preflight takes a configuration; continuation validates saved sources itself")
                config = load_config(args.config)
                result = {"status": "configuration_valid", "source_count": sum(len(g["sources"]) for g in config.get("resource_groups", [{"sources": config["sources"]}])),
                          "source_availability": "not_checked", "model_calls": 0}
            else:
                result = build(args.config, args.state_dir, plan_only=args.command in ("discover", "plan", "revise"), plan_path=args.plan_path,
                               keep_debug=args.keep_debug,
                               no_adopt=args.no_adopt,
                               draft_only=args.draft_only,
                               library_root=args.library_dir,
                               feedback=Path(args.feedback_file).read_text(encoding="utf-8") if args.command == "revise" else None,
                               notify=lambda m: print(m, file=sys.stderr, flush=True))
        elif args.command == "resume":
            result = build(state_root=args.state_dir, resume_id=args.build_id, keep_debug=args.keep_debug,
                no_adopt=args.no_adopt, rediscover=args.rediscover, extra_turns=args.extra_turns, draft_only=args.draft_only, library_root=args.library_dir,
                notify=lambda m: print(m, file=sys.stderr, flush=True))
        elif args.command == "check":
            path = Path(args.path)
            from creation_pipeline.artifacts.layout import extract
            config = load_config(args.config) if args.config else None
            if (path / "summary.json").is_file() and json.loads((path / "summary.json").read_text(encoding="utf-8")).get("workflow") == "shared-environments":
                summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
                result = {"status": "pass", "recorded_build_status": summary["status"], "scope": "record_only_not_new_qualification"}
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            if (path / "summary.json").is_file():
                record, bundle = verify_bundle(path)
                reports = []
                for entity in record["entities"]:
                    directory = bundle / ("skills" if entity["kind"] == "skill" else "tools") / entity["name"]
                    if directory.exists():
                        from creation_pipeline.records import read_json
                        frozen = read_json(path / "records" / (entity["name"] + ".json"))
                        layout = frozen["delivery"]["inputs"].get("layout", {}).get("payload")
                        current = static_checks(directory, entity["name"], bundle=bundle, tool=entity["kind"] == "tool", layout=layout)
                        if config:
                            from creation_pipeline.artifacts.layout import problems
                            from creation_pipeline.validation.checks import result as check_result
                            for check in current:
                                if check["name"] == "delivery_layout":
                                    check["name"] = "frozen_delivery_layout"
                            current.append(check_result("delivery_layout", problems(
                                manifest(directory), extract(config, entity["name"]))))
                        reports += current
                result = {"status": "fail" if any(r["status"] == "fail" for r in reports) else "pass",
                          "checks": reports, "recorded_build_status": record["status"], "execution": "not_rerun",
                          "scope": "static_only_not_new_qualification"}
            else:
                reports = static_checks(path, layout=extract(config, path.name) if config else None)
                result = {"status": "fail" if any(r["status"] == "fail" for r in reports) else "pass",
                          "checks": reports, "execution": "not_run", "scope": "static_only_not_installation_approval"}
        elif args.command == "install":
            if (Path(args.output) / "catalog.json").exists() and json.loads((Path(args.output) / "catalog.json").read_text(encoding="utf-8")).get("workflow") == "shared-environments":
                from creation_pipeline.shared.delivery import install as shared_install
                if not args.name:
                    raise ValueError("Select --name for a shared environment Skill library")
                result = shared_install(args.output, args.name, args.destination, args.include_pending)
            elif args.name:
                from creation_pipeline.artifacts.library import install_from_library
                result = install_from_library(args.output, args.name, args.destination)
            else:
                result = install(args.output, args.destination)
        elif args.command == "library":
            from creation_pipeline.artifacts.library import entries, get
            if (Path(args.path) / "catalog.json").exists() and json.loads((Path(args.path) / "catalog.json").read_text(encoding="utf-8")).get("workflow") == "shared-environments":
                from creation_pipeline.shared.delivery import entries as shared_entries
                values = shared_entries(args.path, args.include_candidates)
                result = {"skills": [v for v in values if not args.name or v["name"] == args.name]}
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            result = get(args.path, args.name, include_candidates=args.include_candidates) if args.name else {"skills": entries(args.path, include_candidates=args.include_candidates)}
        elif args.command == "runtime-build":
            from creation_pipeline.runtime.service import resume_build
            refs = json.loads(Path(args.resource_refs).read_text(encoding="utf-8")) if args.resource_refs else None
            result = resume_build(args.library, args.candidate, refs)
        elif args.command == "runtime-prepare":
            from creation_pipeline.runtime.service import prepare_revision
            correction = json.loads(Path(args.oracle_correction).read_text(encoding='utf-8')) if args.oracle_correction else None
            result = prepare_revision(args.library, args.candidate, json.loads(Path(args.spec).read_text(encoding="utf-8")), correction=correction)
        elif args.command in ('runtime-validate', 'runtime-resume'):
            from creation_pipeline.runtime.service import resume_build
            refs = json.loads(Path(args.resource_refs).read_text(encoding='utf-8')) if args.resource_refs else None
            result = resume_build(args.library, args.candidate, refs,
                reuse_image=True if args.command == 'runtime-validate' else None, recover_lock=getattr(args,'recover_lock',False))
        elif args.command == 'runtime-inspect':
            from creation_pipeline.runtime.recovery import inspect_candidate
            result = inspect_candidate(args.library,args.candidate)
        elif args.command == 'runtime-shared-inspect':
            from creation_pipeline.runtime.shared_inspection import inspect_registry
            from creation_pipeline.runtime.shared_environment import registry_root
            result = inspect_registry(args.root if args.root is not None else registry_root(),offline=args.offline)
        elif args.command == 'runtime-import':
            from creation_pipeline.runtime.recovery import import_candidate
            result = import_candidate(args.source,args.library,args.candidate)
        elif args.command == 'runtime-tools-inspect':
            from creation_pipeline.runtime.shared_tool import inspect
            from creation_pipeline.runtime.local import LocalExecutor, process
            result = inspect(args.root, None if args.offline else LocalExecutor().host(), None if args.offline else process)
        elif args.command == 'runtime-relocate':
            from creation_pipeline.runtime.recovery import relocate
            result = relocate(args.library,args.candidate,revalidate=args.revalidate,recover_lock=args.recover_lock)
        else:
            saved_checkpoint = Path(args.state_dir) / 'runs' / args.build_id / 'checkpoint.json'
            if saved_checkpoint.is_file() and json.loads(saved_checkpoint.read_text(encoding='utf-8')).get('workflow') == 'shared-environments':
                from creation_pipeline.shared.retention import clean as shared_clean
                result = shared_clean(args.state_dir, args.build_id, args.dry_run)
            else:
                result = clean_run(args.state_dir, args.build_id, args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("status") in ("failed", "blocked", "fail", "partial", "interrupted", "incomplete", "not_run", "runtime_blocked", "build_failed", "execution_failed", "review_required") else 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "error", "error": redact(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
