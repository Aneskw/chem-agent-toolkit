"""Native-Agent helper command routing; implementations live with their responsibilities."""
from pathlib import Path
import argparse
import json
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "creation_pipeline.agent"

from creation_pipeline.resources.supplements import supplement, inventory, register
from creation_pipeline.artifacts.delivery import write_chunk, finish
from creation_pipeline.validation.agent_checks import check
from creation_pipeline.generation.candidates import save_candidate
from creation_pipeline.records import sanitized


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("inventory")
    p.add_argument("--run", required=True)
    p.add_argument("--query", default="")
    p.add_argument("--source")
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--offset", type=int, default=0)
    p = commands.add_parser("candidate")
    p.add_argument("--run", required=True)
    p.add_argument("--definition", required=True)
    p = commands.add_parser("supplement")
    p.add_argument("--run", required=True)
    locations = p.add_mutually_exclusive_group(required=True)
    for key in ("url", "repo", "paper"):
        locations.add_argument("--" + key)
    p.add_argument("--reason", required=True)
    p.add_argument("--ref")
    p.add_argument("--related-to", nargs="+")
    p = commands.add_parser("register")
    p.add_argument("--run", required=True)
    p.add_argument("--definition", required=True)
    p = commands.add_parser("lookup")
    p.add_argument("--run", required=True)
    p.add_argument("--query", required=True)
    p = commands.add_parser("adopt-resource")
    for field in ("run", "snapshot", "reason"):
        p.add_argument("--" + field, required=True)
    p.add_argument("--related-to", nargs="+", required=True)
    p = commands.add_parser("write")
    p.add_argument("--package", required=True)
    p.add_argument("--path", required=True)
    p.add_argument("--base64", required=True)
    p.add_argument("--append", action="store_true")
    p = commands.add_parser("finish")
    for key in ("run", "package", "token"):
        p.add_argument("--" + key, required=True)
    p.add_argument("--metadata")
    p = commands.add_parser("check")
    for key in ("run", "package", "definition"):
        p.add_argument("--" + key, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            result = inventory(args.run, args.query, args.source, args.limit, args.offset)
        elif args.command == "candidate":
            result = save_candidate(args.run, args.definition)
        elif args.command == "supplement":
            result = supplement(args.run, {k: getattr(args, k) for k in ("url", "repo", "paper") if getattr(args, k)}, args.reason, args.ref, args.related_to)
        elif args.command == "register":
            result = register(args.run, args.definition)
        elif args.command == "lookup":
            from creation_pipeline.shared.resources import lookup
            result = lookup(args.run, args.query)
        elif args.command == "adopt-resource":
            from creation_pipeline.shared.resources import adopt
            result = adopt(args.run, args.snapshot, args.reason, args.related_to)
        elif args.command == "write":
            result = write_chunk(args.package, args.path, args.base64, args.append)
        elif args.command == "finish":
            from creation_pipeline.records import read_json
            if read_json(Path(args.run) / "resource-state.json")["config"].get("workflow") == "shared-environments":
                from creation_pipeline.artifacts.content_delivery import finish as content_finish
                result = content_finish(args.run, args.package, args.token, args.metadata)
            else:
                result = finish(args.run, args.package, args.token, args.metadata)
        else:
            result = check(args.run, args.package, args.definition)
        print(json.dumps(sanitized(result), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
