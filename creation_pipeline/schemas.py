"""Model transport envelopes; Markdown organization remains unconstrained."""


STRING = {"type": "string"}
STRINGS = {"type": "array", "items": STRING}


def obj(properties):
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}


def array(properties):
    return {"type": "array", "items": obj(properties)}


PLAN = obj({
    **{key: STRING for key in ("name", "task", "scope", "entrypoint", "added_behavior")},
    "readiness": {"type": "string", "enum": ["callable", "adapter_needed", "blocked"]},
    "intent": {"type": "string", "enum": ["direct", "extension"]},
    "dependencies": STRINGS, "files": array({"path": STRING, "purpose": STRING}),
    "checks": STRINGS, "evidence": array({"id": STRING, "claim": STRING}), "gaps": STRINGS,
})

AUTHOR = obj({
    "files": array({"path": STRING, "content": STRING, "purpose": STRING}),
    "coverage": obj({key: STRING for key in ("scope", "io", "usage", "result_checks")}),
    "tests": array({"name": STRING, "argv": STRINGS, "expected_exit": {"type": "integer"},
                    "stdout_contains": STRINGS, "evidence": STRING, "purpose": STRING,
                    "kind": {"type": "string", "enum": ["positive", "negative", "boundary"]}}),
    "notes": STRINGS,
})

REVIEW = obj({"status": {"type": "string", "enum": ["pass", "fail", "not_run"]},
              "resolution": {"type": "string", "enum": ["none", "revise_files", "supply_evidence"]},
              "findings": STRINGS})
