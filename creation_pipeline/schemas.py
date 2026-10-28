"""Agent stage result records; Markdown organization remains unconstrained."""


STRING = {"type": "string"}
STRINGS = {"type": "array", "items": STRING}


def obj(properties):
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}


def array(properties):
    return {"type": "array", "items": obj(properties)}


REVIEW = obj({"status": {"type": "string", "enum": ["pass", "fail", "not_run"]},
              "resolution": {"type": "string", "enum": ["none", "revise_files", "supply_evidence"]},
              "findings": array({"location": STRING, "problem": STRING, "evidence": STRING,
                  "impact": STRING, "action": STRING, "blocking": {"type": "boolean"},
                  "category": {"type": "string", "enum": ["file", "check", "source", "environment", "suggestion"]}}),
              })


# Agent-facing records contain decisions, not host constants or output templates.
CANDIDATES = obj({
    "outcome": {"type": "string", "enum": ["candidates", "no_suitable_candidates", "blocked", "incomplete"]},
    "summary": STRING, "saved_candidates": STRINGS,
    "candidates": array({"name": STRING, "capability": STRING, "boundary": STRING,
        "value": STRING, "usage_path": STRING, "construction": STRING,
        "evidence": array({"id": STRING, "claim": STRING}), "gaps": STRINGS,
        "blocked": {"type": "boolean"}}),
    "omitted": array({"capability": STRING, "reason": STRING}), "limitations": STRINGS,
})
DELIVERY = obj({"completed": {"type": "boolean"}, "summary": STRING})
