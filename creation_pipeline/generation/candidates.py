"""Persist inspected candidate decisions before full discovery completes."""
from pathlib import Path
from creation_pipeline.records import read_json, write_json, safe_relative
from creation_pipeline.artifacts.delivery import inside
from creation_pipeline.resources.supplements import restore


def save_candidate(run, definition):
    candidate = read_json(inside(run, definition))
    from creation_pipeline.generation.discovery import normalize
    from creation_pipeline.models import validate_plan
    normalized = normalize({"candidates": [candidate]})["candidates"][0]
    validate_plan(normalized)
    sources = restore(run)
    sources.validate_evidence(candidate["evidence"])
    target = safe_relative(Path(run), "candidates/" + candidate["name"] + ".json")
    write_json(target, candidate)
    return {"status": "saved", "candidate": candidate["name"]}
