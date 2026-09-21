#!/usr/bin/env python3
"""Correct nearby citation spans only when source words match exactly."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from core.creation_schema import candidate_claims


def whitespace_match(quote: str, excerpt: str) -> str | None:
    """Return exact source text for a quote differing only in whitespace."""
    tokens = list(re.finditer(r"\S+", excerpt))
    compact = []
    positions = []
    for index, token in enumerate(tokens):
        if index:
            compact.append(" ")
            positions.append(tokens[index - 1].end())
        for offset, char in enumerate(token.group()):
            compact.append(char)
            positions.append(token.start() + offset)
    needle = " ".join(quote.split())
    match_at = "".join(compact).find(needle)
    if match_at < 0:
        return None
    result = excerpt[positions[match_at]:positions[match_at + len(needle) - 1] + 1]
    return result if 8 <= len(result) <= 240 else None


def repair(response: dict, bundle: dict) -> tuple[dict, list[dict]]:
    sources = {source["id"]: source for source in bundle["sources"]}
    changes = []
    for candidate in response["candidates"]:
        for claim in candidate_claims(candidate):
            for citation in claim["citations"]:
                source = sources[citation["source_id"]]
                lines = source["lines"]
                old = (citation["start"], citation["end"])
                if citation["quote"] in "\n".join(lines[old[0] - 1:old[1]]):
                    continue
                matches = []
                for start in range(max(1, old[0] - 2), min(len(lines), old[1] + 2) + 1):
                    for end in range(start, min(len(lines), start + 25, old[1] + 2) + 1):
                        excerpt = "\n".join(lines[start - 1:end])
                        if citation["quote"] in excerpt:
                            matches.append((start, end, citation["quote"], "line_span"))
                        elif source["role"] in {"paper", "repo_doc", "database_doc", "tool_doc", "model_doc"}:
                            exact_quote = whitespace_match(citation["quote"], excerpt)
                            if exact_quote:
                                matches.append((start, end, exact_quote, "whitespace_only"))
                minimal = sorted(matches, key=lambda span: (span[1] - span[0], abs(span[0] - old[0]) + abs(span[1] - old[1])))
                if not minimal:
                    raise ValueError(f"Quote not found near {citation['source_id']}:{old}")
                best = minimal[0]
                if len(minimal) > 1 and minimal[1][1] - minimal[1][0] == best[1] - best[0]:
                    raise ValueError(f"Ambiguous citation span near {citation['source_id']}:{old}")
                old_quote = citation["quote"]
                citation["start"], citation["end"], citation["quote"] = best[:3]
                changes.append({"candidate": candidate["name"], "source_id": citation["source_id"],
                                "old": old, "new": best[:2], "reason": best[3],
                                "old_quote": old_quote, "quote": citation["quote"]})
    return response, changes


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--response", type=Path, required=True)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result, changes = repair(
        json.loads(args.response.read_text(encoding="utf-8")),
        json.loads(args.bundle.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".repairs.json").write_text(
        json.dumps(changes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"repaired_citations": len(changes), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
