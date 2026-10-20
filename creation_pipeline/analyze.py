from pathlib import Path

from .models import validate_plan
from .schemas import PLAN


ROOT = Path(__file__).resolve().parents[1]


def analyze(session, config):
    instructions = (ROOT / "creation_pipeline/prompts/analyze.md").read_text(encoding="utf-8")
    initial_views = []
    # Explicitly supplied document files can be read once up front. Repositories
    # remain indexed/on-demand; the model can request further ranges either way.
    for sid, entry in session.sources.entries.items():
        path = Path(entry["path"])
        if path.is_file() and len(initial_views) < 2:
            initial_views.append(session.sources.request({"action": "read", "source": sid,
                "path": path.name, "start": 1, "limit": 120}))
    plan = validate_plan(session.stage(instructions, {
        "task": config["task"], "intent": config["intent"], "notes": config.get("notes", ""),
        "sources": session.sources.index(), "configured_checks": config["checks"],
        "initial_source_views": initial_views,
    }, schema=PLAN))
    if plan["intent"] != config["intent"]:
        raise ValueError("Model changed packaging intent; update the task/config explicitly")
    session.sources.validate_evidence(plan["evidence"])
    return plan
