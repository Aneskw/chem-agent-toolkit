"""Deterministic Agent-stage doubles; never part of the production transport."""
import copy
import json
from pathlib import Path
from creation_pipeline.agent.backend import NativeSession
from creation_pipeline.artifacts.delivery import finish, validate_package
from creation_pipeline.models import ModelCallError
from creation_pipeline.records import write_json, safe_relative

MAIN = """---
name: add-numbers
description: Add two numeric inputs using the supplied tool.
---
# Add numbers
Use adder for numeric addition. This does not concatenate strings.
Inputs a and b are numbers; output is their sum.
```python
print(2 + 3)
```
Check that the result equals 5 for this example.
"""
PLAN = {"name": "add-numbers", "task": "Add two numbers", "scope": "Numeric addition",
        "entrypoint": "adder.add(a,b)", "readiness": "callable", "intent": "direct", "added_behavior": "none",
        "dependencies": [], "files": [{"path": "SKILL.md", "purpose": "Instructions"}],
        "checks": ["2+3=5"], "evidence": [{"id": "e1", "claim": "Tool adds two numbers"}], "gaps": []}
ARTIFACT = {"files": [{"path": "SKILL.md", "content": MAIN, "purpose": "Instructions"}],
            "basis": [{"location": "SKILL.md", "claim": "Tool adds numbers", "source": "e1", "locator": "add", "origin": "upstream"}], "notes": []}


def write_fixture_files(package, files, max_bytes):
    """Simulate native file writes; validation remains production code."""
    package = Path(package)
    package.mkdir(parents=True, exist_ok=True)
    for item in files:
        path = safe_relative(package, item["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(item["content"].encode("utf-8"))
    validate_package(package, max_bytes)


def response(value):
    return copy.deepcopy(value)


class ReplayStages:
    """Simulate decisions and direct file delivery through the actual host receipt."""
    def __init__(self, values):
        self.values = copy.deepcopy(list(values))
        self.prompts = []

    def __call__(self, config, sources, limits, work, keep_debug=False):
        owner = self
        class FixtureSession(NativeSession):
            def stage(self, instructions, context, schema=None):
                return owner.stage(self, instructions, context, schema)
        return FixtureSession(config, sources, limits, work, keep_debug)

    def stage(self, session, instructions, context, schema=None):
        self.prompts.append(instructions + "\n" + json.dumps(context, ensure_ascii=False))
        phase = context.get("_phase", "discovery")
        write_json(session.work / "active-phase.json", {"phase": phase})
        session.receipts.append({"model": "deterministic-agent-fixture", "phase": phase, "usage": None})
        if phase == "review" and (not self.values or "status" not in self.values[0]):
            return {"status": "pass", "resolution": "none", "findings": []}
        if not self.values:
            raise ModelCallError("No fixture Agent result")
        value = self.values.pop(0)
        if phase == "author":
            package = Path(context["output_directory"])
            write_fixture_files(package, value.get("files"), session.limits["package_bytes"])
            metadata = Path(context["metadata_path"])
            write_json(metadata, {k: v for k, v in value.items() if k not in ("files", "coverage")})
            finish(session.work, package, context["delivery_token"], metadata)
            return {"completed": True, "summary": "Fixture wrote package files"}
        if phase != "review":
            value.setdefault("outcome", "candidates" if value.get("candidates") else "no_suitable_candidates")
        return value
