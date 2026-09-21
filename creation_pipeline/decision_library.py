"""Lossless abstraction and conservative deduplication of bounded decision policies."""
from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher


FIELDS = (
    "trigger",
    "preconditions",
    "action_if_true",
    "action_if_false",
    "verification",
    "stop_conditions",
    "negative_scope",
)


def _text(claims):
    return " | ".join(item["text"] for item in claims)


def _citations(claims):
    seen = set()
    output = []
    for claim in claims:
        for citation in claim.get("citations", []):
            key = json.dumps(citation, sort_keys=True, ensure_ascii=False)
            if key not in seen:
                seen.add(key)
                output.append(citation)
    return output


def policies(candidate):
    """Convert the operational contract into bounded portable policies."""
    common = candidate.get("invoke_when", [])
    preconditions = candidate.get("preconditions", [])
    checks = candidate.get("verification_checks", [])
    stops = candidate.get("stop_conditions", [])
    negative = candidate.get("do_not_invoke_when", [])
    points = candidate.get("decision_points", [])
    if points:
        for point in points:
            claims = common + preconditions + checks + stops + negative + [
                point["condition"], point["if_true"], point["if_false"]
            ]
            yield {
                "trigger": point["condition"]["text"],
                "preconditions": _text(preconditions),
                "action_if_true": point["if_true"]["text"],
                "action_if_false": point["if_false"]["text"],
                "verification": _text(checks),
                "stop_conditions": _text(stops),
                "negative_scope": _text(negative),
                "citations": _citations(claims),
            }
    elif candidate.get("kind") == "method_procedure":
        claims = common + preconditions + candidate.get("steps", []) + checks + stops + negative
        yield {
            "trigger": _text(common),
            "preconditions": _text(preconditions),
            "action_if_true": _text(candidate.get("steps", [])),
            "action_if_false": "",
            "verification": _text(checks),
            "stop_conditions": _text(stops),
            "negative_scope": _text(negative),
            "citations": _citations(claims),
        }


def canonical(rule):
    # Preserve case, punctuation, score direction, stereochemistry, and scope.
    return {key: re.sub(r"\s+", " ", rule.get(key, "")).strip() for key in FIELDS}


def build_library(responses, origins=None):
    groups = {}
    related = []
    input_rules = 0
    for response_index, response in enumerate(responses):
        for candidate in response["candidates"]:
            for index, rule in enumerate(policies(candidate)):
                input_rules += 1
                policy = canonical(rule)
                key = hashlib.sha256(
                    json.dumps(policy, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest()
                group = groups.setdefault(key, {"rule_id": key, "policy": policy, "origins": []})
                group["origins"].append({
                    "paper_id": response["paper_id"],
                    "candidate": candidate["name"],
                    "decision_index": index,
                    "citations": rule["citations"],
                    **(origins[response_index] if origins else {}),
                })
    values = list(groups.values())
    for index, left in enumerate(values):
        for right in values[index + 1:]:
            ratio = SequenceMatcher(
                None, left["policy"]["action_if_true"], right["policy"]["action_if_true"]
            ).ratio()
            if ratio >= 0.7:
                related.append({
                    "a": left["rule_id"],
                    "b": right["rule_id"],
                    "action": "retain_scoped_variants",
                    "reason": "Similar action is not evidence of equivalent triggers, scope, or mechanism.",
                })
    return {
        "version": 2,
        "rules": values,
        "related": related,
        "abstraction": "A portable conditional policy with original scope and evidence; no invented parent rule.",
        "input_rules": input_rules,
        "unique_rules": len(values),
        "utility": "not_evaluated",
    }


def main():
    import argparse
    from pathlib import Path
    from core.creation_schema import normalize_response, validate

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    responses = []
    origins = []
    for run in args.run:
        paths = sorted((run / "import_results").glob("*/validated.json"))
        if not paths:
            paths = sorted((run / "import_results").glob("*/operational-contract.json"))
        if not paths:
            raise ValueError("No citation-validated responses in " + str(run))
        for path in paths:
            response, legacy = normalize_response(json.loads(path.read_text(encoding="utf-8")))
            bundle_path = run / "jobs" / response["paper_id"] / "bundle.json"
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            validate(response, bundle, enforce_contract=not legacy)
            responses.append(response)
            origins.append({
                "run_id": run.name,
                "bundle_sha256": hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
            })
    if args.out.exists():
        raise ValueError("Library output already exists")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(build_library(responses, origins), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
