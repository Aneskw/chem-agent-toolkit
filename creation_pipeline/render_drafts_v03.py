#!/usr/bin/env python3
"""Render cited extraction candidates as low-confidence, unpublished v0.3 drafts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def references(claims: list[dict]) -> str:
    output = []
    for claim in claims:
        refs = ", ".join(f"{c['source_id']}:L{c['start']}-L{c['end']}" for c in claim["citations"])
        output.append(f"- {claim['text']} ({refs})")
    return "\n".join(output)


def render(candidate: dict, bundle: dict, check: dict) -> str:
    name = candidate["name"]
    source_lines = [f"- {source['role']}: {source['url'] or source['path']} (source {source['id']}; SHA-256 {source['sha256']})"
                    for source in bundle["sources"]]
    requirements = [f"- {item['kind']}: {item['path']} — {item['reason']['text']}"
                    for item in candidate["requirements"]]
    unknowns = [f"- {item}" for item in candidate["unknowns"]]
    state = check["state"]
    return (
        "---\n"
        f"name: {name}\n"
        "description: >\n"
        f"  {candidate['description']} Invoke for: {candidate['operation']} Do not use as evidence of successful execution.\n"
        "license: undetermined\n"
        "compatibility: Unverified draft; inspect requirements and source license before use\n"
        "allowed-tools: Read\n"
        "---\n\n"
        f"# {name.replace('-', ' ').title()}\n\n"
        f"This cited draft describes {candidate['operation']} Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.\n\n"
        "## Credibility\n\n"
        f"**Low confidence (Highly flexible)**. State: `{state}`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.\n\n"
        "## Reference\n\n" + "\n".join(source_lines) + "\n\n"
        "## Input & Output\n\nInputs:\n\n" + references(candidate["inputs"]) +
        "\n\nOutputs:\n\n" + references(candidate["outputs"]) + "\n\n"
        "## Procedure Guidance\n\n" + references(candidate["steps"]) + "\n\n"
        "## Matters & Troubleshooting\n\nResources:\n\n" + ("\n".join(requirements) or "- None identified.") +
        "\n\nUnknowns and limits:\n\n" + ("\n".join(unknowns) or "- No explicit unknowns recorded.") + "\n"
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--paper-id", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    run = args.run
    result = run / "import_results" / args.paper_id
    response = json.loads((result / "validated.json").read_text())
    bundle = json.loads((run / "jobs" / args.paper_id / "bundle.json").read_text())
    summary = json.loads((run / "import_results" / "summary.json").read_text())
    checks = next(item["checks"] for item in summary["jobs"] if item["paper_id"] == args.paper_id)
    args.out.mkdir(parents=True, exist_ok=True)
    for candidate, check in zip(response["candidates"], checks):
        path = args.out / candidate["name"]
        path.mkdir(exist_ok=False)
        (path / "SKILL.md").write_text(render(candidate, bundle, check), encoding="utf-8")
    print(json.dumps({"paper_id": args.paper_id, "drafts": len(response["candidates"]), "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
