"""Persist inspected candidate decisions before full discovery completes."""
from pathlib import Path
from creation_pipeline.records import read_json, write_json, safe_relative
from creation_pipeline.artifacts.delivery import inside
from creation_pipeline.resources.supplements import restore


def save_candidate(run, definition):
    phase = Path(run) / "active-phase.json"
    if phase.exists() and read_json(phase).get("phase") != "discovery":
        raise ValueError("candidate helper is discovery-only; authors must put candidate_update with reason/evidence and changed scope/task/entrypoint/construction in metadata_path")
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
