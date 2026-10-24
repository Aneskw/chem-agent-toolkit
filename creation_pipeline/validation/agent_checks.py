"""Record approved checks requested by the review Agent."""
from pathlib import Path
import json
import uuid
from creation_pipeline.records import read_json, digest, sanitized
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.artifacts.delivery import inside
from creation_pipeline.resources.supplements import restore


def check(run, package, definition):
    from creation_pipeline.validation.runtime import execute
    sources = restore(run)
    package = inside(run, package)
    test = read_json(inside(run, definition))
    before = manifest(package)
    if not sources.config["execute_generated_checks"]:
        report = {"name": test.get("name", "agent-check"), "status": "not_run", "required": False,
                  "findings": ["Generated execution is disabled"]}
    else:
        report = execute(test, package, sources, Path(run) / "agent-checks" / uuid.uuid4().hex,
                         sources.limits["check_timeout"], sources.config["environment"].get("allow", []))
        if before != manifest(package):
            raise ValueError("Check changed delivered files")
        sources.verify()
    report.update(origin="review_agent", package=str(package), files=before, definition=test,
                  signature=digest(json.dumps(test, sort_keys=True).encode()), verification_id=uuid.uuid4().hex)
    with (Path(run) / "agent-checks.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(sanitized(report), ensure_ascii=False) + "\n")
    return report
