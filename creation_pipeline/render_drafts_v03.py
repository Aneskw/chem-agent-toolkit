#!/usr/bin/env python3
"""Render cited extraction candidates as low-confidence, unpublished v0.3 drafts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def references(claims: list[dict], numbered: bool = False) -> str:
    output = []
    for index, claim in enumerate(claims, 1):
        refs = ", ".join(f"{c['source_id']}:L{c['start']}-L{c['end']}" for c in claim["citations"])
        prefix = f"{index}." if numbered else "-"
        output.append(f"{prefix} {claim['text']} ({refs})")
    return "\n".join(output)


def decision_points(points: list[dict]) -> str:
    output = []
    for index, point in enumerate(points, 1):
        output.append(f"{index}. Condition: {references([point['condition']])[2:]}")
        output.append(f"   - If true: {references([point['if_true']])[2:]}")
        output.append(f"   - If false: {references([point['if_false']])[2:]}")
    return "\n".join(output)


def render(candidate: dict, bundle: dict, check: dict) -> str:
    name = candidate["name"]
    source_lines = [f"- {source['role']}: {source['url'] or source['path']} (source {source['id']}; SHA-256 {source['sha256']})"
                    for source in bundle["sources"]]
    requirements = [f"- {item['kind']}: {item['path']} — {item['reason']['text']}"
                    for item in candidate["requirements"]]
    unknowns = [f"- {item}" for item in candidate["unknowns"]]
    invoke_for = "; ".join(item["text"] for item in candidate["invoke_when"])
    exclusions = "; ".join(item["text"] for item in candidate["do_not_invoke_when"])
    state = check["state"]
    return (
        "---\n"
        f"name: {name}\n"
        "description: >\n"
        f"  {candidate['description']} Invoke for: {invoke_for} "
        + (f"Do not invoke for: {exclusions} " if exclusions else "")
        + "Do not use as evidence of successful execution.\n"
        "license: undetermined\n"
        "compatibility: Unverified draft; inspect requirements and source license before use\n"
        "allowed-tools: Read\n"
        "---\n\n"
        f"# {name.replace('-', ' ').title()}\n\n"
        f"This cited draft describes {candidate['operation']} It is a `source_validated_candidate`, not an execution-validated package.\n\n"
        "Use when:\n\n" + references(candidate["invoke_when"]) + "\n\n"
        "Do not use when:\n\n" + (references(candidate["do_not_invoke_when"]) or "- No source-supported exclusion was extracted.") + "\n\n"
        "Preconditions:\n\n" + (references(candidate["preconditions"]) or "- No additional source-supported precondition was extracted.") + "\n\n"
        "## Credibility\n\n"
        f"**Low confidence (Highly flexible)**. State: `{state}`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.\n\n"
        "## Reference\n\n" + "\n".join(source_lines) + "\n\n"
        "## Input & Output\n\nInputs:\n\n" + references(candidate["inputs"]) +
        "\n\nOutputs:\n\n" + references(candidate["outputs"]) + "\n\n"
        "## Procedure Guidance\n\nSteps:\n\n" + references(candidate["steps"], numbered=True) + "\n\n"
        "Decision points:\n\n" + (decision_points(candidate["decision_points"]) or "- No source-supported decision branch was extracted.") + "\n\n"
        "Verification checks:\n\n" + (references(candidate["verification_checks"]) or "- No source-supported verification check was extracted.") + "\n\n"
        "Stop conditions:\n\n" + (references(candidate["stop_conditions"]) or "- No source-supported stop condition was extracted.") + "\n\n"
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
    contract = result / "operational-contract.json"
    response = json.loads(contract.read_text(encoding="utf-8"))
    bundle = json.loads((run / "jobs" / args.paper_id / "bundle.json").read_text(encoding="utf-8"))
    summary = json.loads((run / "import_results" / "summary.json").read_text(encoding="utf-8"))
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
