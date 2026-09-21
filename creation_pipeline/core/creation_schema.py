"""Operational extraction contract and deterministic provenance checks."""
from __future__ import annotations

import copy
import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit


def obj(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": required or list(properties),
        "additionalProperties": False,
    }


TEXT = {"type": "string", "minLength": 1, "maxLength": 3000}
CITATION = obj({
    "source_id": TEXT,
    "start": {"type": "integer", "minimum": 1},
    "end": {"type": "integer", "minimum": 1},
    "quote": {"type": "string", "minLength": 8, "maxLength": 240},
})
CLAIM = obj({
    "text": TEXT,
    "citations": {"type": "array", "minItems": 1, "maxItems": 5, "items": CITATION},
})


def claim_array(min_items=0, max_items=15):
    return {"type": "array", "minItems": min_items, "maxItems": max_items, "items": CLAIM}


DECISION_POINT = obj({
    "condition": CLAIM,
    "if_true": CLAIM,
    "if_false": CLAIM,
})

CANDIDATE = obj({
    "name": {"type": "string", "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$", "maxLength": 63},
    "description": TEXT,
    "kind": {"type": "string", "enum": ["tool_usage", "method_procedure"]},
    "operation": TEXT,
    "invoke_when": claim_array(min_items=1, max_items=8),
    "do_not_invoke_when": claim_array(max_items=8),
    "preconditions": claim_array(max_items=12),
    "inputs": claim_array(min_items=1),
    "outputs": claim_array(min_items=1),
    "steps": claim_array(min_items=1),
    "decision_points": {
        "type": "array", "minItems": 0, "maxItems": 10, "items": DECISION_POINT,
    },
    "verification_checks": claim_array(max_items=12),
    "stop_conditions": claim_array(max_items=12),
    "requirements": {
        "type": "array",
        "maxItems": 30,
        "items": obj({
            "path": TEXT,
            "kind": {"type": "string", "enum": ["repo_file", "external_asset"]},
            "reason": CLAIM,
        }),
    },
    "unknowns": {"type": "array", "maxItems": 20, "items": TEXT},
})

SCHEMA = obj({
    "contract_version": {"type": "string", "enum": ["1.0"]},
    "schema_version": {"type": "integer", "enum": [2]},
    "paper_id": TEXT,
    "candidates": {"type": "array", "maxItems": 4, "items": CANDIDATE},
    "no_skill_reason": {"type": "string", "maxLength": 3000},
})


def normalize_response(response):
    """Upgrade saved v1 responses so deterministic replays keep working."""
    version = response.get("schema_version") if isinstance(response, dict) else None
    if version == 2:
        return response, False
    if version != 1:
        raise ValueError("Unsupported schema_version")
    upgraded = copy.deepcopy(response)
    upgraded["contract_version"] = "1.0"
    upgraded["schema_version"] = 2
    for candidate in upgraded.get("candidates", []):
        operation = candidate.get("operation", "")
        candidate.setdefault("invoke_when", [{
            "text": operation,
            "citations": copy.deepcopy(candidate.get("steps", [{}])[0].get("citations", [])),
        }])
        candidate.setdefault("do_not_invoke_when", [])
        candidate.setdefault("preconditions", [])
        candidate.setdefault("decision_points", [])
        candidate.setdefault("verification_checks", [])
        candidate.setdefault("stop_conditions", [])
    return upgraded, True


def candidate_claims(candidate):
    """Yield every source-derived claim in the extraction contract."""
    for field in (
        "invoke_when", "do_not_invoke_when", "preconditions", "inputs", "outputs",
        "steps", "verification_checks", "stop_conditions",
    ):
        yield from candidate.get(field, [])
    for point in candidate.get("decision_points", []):
        yield point["condition"]
        yield point["if_true"]
        yield point["if_false"]
    for requirement in candidate.get("requirements", []):
        yield requirement["reason"]


def procedure_claims(candidate):
    yield from candidate.get("steps", [])
    yield from candidate.get("verification_checks", [])
    yield from candidate.get("stop_conditions", [])
    for point in candidate.get("decision_points", []):
        yield point["condition"]
        yield point["if_true"]
        yield point["if_false"]


def check(value, schema, path="$"):
    kind = schema["type"]
    expected = {"object": dict, "array": list, "string": str, "integer": int}[kind]
    if type(value) is not expected:
        raise ValueError(f"{path}: expected {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: unsupported value")
    if kind == "object":
        missing = set(schema["required"]) - set(value)
        extra = set(value) - set(schema["properties"])
        if missing or extra:
            raise ValueError(f"{path}: missing={sorted(missing)}, extra={sorted(extra)}")
        for key, child in value.items():
            check(child, schema["properties"][key], path + "." + key)
    elif kind == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 10000):
            raise ValueError(path + ": invalid item count")
        for index, child in enumerate(value):
            check(child, schema["items"], f"{path}[{index}]")
    elif kind == "string":
        if not schema.get("minLength", 0) <= len(value.strip()) <= schema.get("maxLength", 100000):
            raise ValueError(path + ": invalid string length")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            raise ValueError(path + ": invalid name")
    elif kind == "integer" and value < schema.get("minimum", value):
        raise ValueError(path + ": integer below minimum")


def validate(response, bundle, enforce_contract=True):
    check(response, SCHEMA)
    if response["paper_id"] != bundle["paper_id"]:
        raise ValueError("paper_id does not match source bundle")
    if not response["candidates"] and not response["no_skill_reason"].strip():
        raise ValueError("No candidates requires a reason")
    names = [candidate["name"] for candidate in response["candidates"]]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate candidate names")
    sources = {source["id"]: source for source in bundle["sources"]}
    results = []
    for candidate in response["candidates"]:
        if enforce_contract and candidate["kind"] == "method_procedure":
            if len(candidate["steps"]) < 2:
                raise ValueError(f"{candidate['name']}: method_procedure needs at least two ordered steps")
            operational_signals = (
                candidate["decision_points"]
                + candidate["verification_checks"]
                + candidate["stop_conditions"]
            )
            if not operational_signals:
                raise ValueError(
                    f"{candidate['name']}: method_procedure needs a decision point, "
                    "verification check, or stop condition"
                )

        procedural = {id(claim) for claim in procedure_claims(candidate)}
        primary_cited = False
        primary_role = bundle.get("primary_role", "paper")
        for claim in candidate_claims(candidate):
            for citation in claim["citations"]:
                source = sources.get(citation["source_id"])
                if source is None:
                    raise ValueError("Unknown source_id: " + citation["source_id"])
                start, end = citation["start"], citation["end"]
                if not 1 <= start <= end <= len(source["lines"]):
                    raise ValueError("Citation line range outside source")
                if end - start > 25:
                    raise ValueError("Citation range too broad; use at most 26 lines")
                excerpt = "\n".join(source["lines"][start - 1:end])
                if citation["quote"] not in excerpt:
                    raise ValueError("Citation quote not found in referenced lines")
                if source["role"] == primary_role and id(claim) in procedural:
                    primary_cited = True
        if candidate["kind"] == "method_procedure" and not primary_cited:
            raise ValueError(
                f"method_procedure needs a procedural citation to supplied {primary_role}, "
                "not metadata or README alone"
            )

        missing = []
        external = []
        for requirement in candidate["requirements"]:
            raw_path = requirement["path"]
            if (
                requirement["kind"] == "external_asset"
                and bundle.get("source_type") == "database"
                and raw_path.startswith("/")
                and not raw_path.startswith("//")
            ):
                if ".." in PurePosixPath(urlsplit(raw_path).path).parts or "\\" in raw_path:
                    raise ValueError("Unsafe API route template")
                external.append(raw_path)
                continue
            if requirement["kind"] == "external_asset" and raw_path.startswith("https://"):
                parsed = urlsplit(raw_path)
                if not parsed.hostname or parsed.username or parsed.password or ".." in PurePosixPath(parsed.path).parts:
                    raise ValueError("Unsafe external resource URL")
                external.append(raw_path)
                continue
            if requirement["kind"] == "external_asset" and ": " in raw_path:
                if raw_path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", raw_path) or "://" in raw_path:
                    raise ValueError("Unsafe external resource identifier")
                external.append(raw_path)
                continue
            path = PurePosixPath(raw_path)
            if path.is_absolute() or ".." in path.parts or "\\" in str(path) or ":" in str(path):
                raise ValueError("Unsafe resource path")
            if requirement["kind"] == "repo_file" and str(path) not in bundle["repo_files"]:
                missing.append(str(path))
            if requirement["kind"] == "external_asset":
                external.append(str(path))
        results.append({
            "name": candidate["name"],
            "state": "blocked_resources" if missing else "draft_unexecuted",
            "missing_repo_files": missing,
            "external_assets_unverified": external,
            "checks": (
                "Operational-contract shape and source citations checked; semantic completeness, "
                "execution, and agent utility NOT verified."
            ),
        })
    return results
