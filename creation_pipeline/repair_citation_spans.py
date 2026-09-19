#!/usr/bin/env python3
"""Correct only uniquely identifiable, off-by-one citation spans."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def repair(response: dict, bundle: dict) -> tuple[dict, list[dict]]:
    sources = {source["id"]: source for source in bundle["sources"]}
    changes = []
    for candidate in response["candidates"]:
        claims = candidate["inputs"] + candidate["outputs"] + candidate["steps"]
        claims += [item["reason"] for item in candidate["requirements"]]
        for claim in claims:
            for citation in claim["citations"]:
                source = sources[citation["source_id"]]
                lines = source["lines"]
                old = (citation["start"], citation["end"])
                if citation["quote"] in "\n".join(lines[old[0] - 1:old[1]]):
                    continue
                matches = []
                for start in range(max(1, old[0] - 2), min(len(lines), old[1] + 2) + 1):
                    for end in range(start, min(len(lines), start + 25, old[1] + 2) + 1):
                        if citation["quote"] in "\n".join(lines[start - 1:end]):
                            matches.append((start, end))
                minimal = sorted(matches, key=lambda span: (span[1] - span[0], abs(span[0] - old[0]) + abs(span[1] - old[1])))
                if not minimal:
                    raise ValueError(f"Quote not found near {citation['source_id']}:{old}")
                best = minimal[0]
                if len(minimal) > 1 and minimal[1][1] - minimal[1][0] == best[1] - best[0]:
                    raise ValueError(f"Ambiguous citation span near {citation['source_id']}:{old}")
                citation["start"], citation["end"] = best
                changes.append({"candidate": candidate["name"], "source_id": citation["source_id"],
                                "old": old, "new": best, "quote": citation["quote"]})
    return response, changes


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--response", type=Path, required=True)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result, changes = repair(json.loads(args.response.read_text()), json.loads(args.bundle.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".repairs.json").write_text(json.dumps(changes, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"repaired_citations": len(changes), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
