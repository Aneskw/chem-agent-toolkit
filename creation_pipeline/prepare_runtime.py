"""Prepare a model-planned execution package from schema-3 tool bindings."""
import argparse
import json
from pathlib import Path
from runtime_docker import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--tool-bindings", type=Path, required=True)
    parser.add_argument('--total-seconds',type=int)
    parser.add_argument('--review-blocked-resources',action='store_true',help='Re-evaluate source-backed resource necessity, preserving original tests and history')
    parser.add_argument('--refresh-renderer',action='store_true',help='Explicit plan replay with unchanged tests after a generic renderer fix; preserves history and requires new validation')
    args = parser.parse_args()
    if args.refresh_renderer:
        if args.review_blocked_resources:parser.error('Choose only one recovery action')
        from runtime_model_lifecycle import refresh_renderer
        report=refresh_renderer(args.candidate,args.job_id,args.tool_bindings,args.total_seconds)
    else:
        report = prepare(args.candidate, args.job_id, args.tool_bindings,budget_seconds=args.total_seconds,review_blocked=args.review_blocked_resources)
    # ASCII JSON is portable through Windows consoles/pipes using legacy code pages.
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report["status"] in {"prepared", "not_required"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
