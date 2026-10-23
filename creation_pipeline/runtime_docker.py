"""Public Docker entry points for the model-driven schema-3 runtime."""
from pathlib import Path

from runtime_common import read, write, digest, files, aggregate


def require_model_runtime(settings):
    if not isinstance(settings, dict) or settings.get("schema_version") != 3:
        raise ValueError("Docker runtime v1/v2 is retired; use schema_version 3 bindings and re-prepare with the model-driven generator")


def prepare(candidate, job_id, bindings_path, *, budget_seconds=None, review_blocked=False):
    require_model_runtime(read(bindings_path))
    from runtime_model_lifecycle import prepare as prepare_model
    return prepare_model(candidate, job_id, bindings_path,budget_seconds=budget_seconds,review_blocked=review_blocked)


def validate(candidate, *, budget=None, repair_from_history=False, reuse_build=False):
    require_model_runtime(read(Path(candidate) / "runtime/prepared.json"))
    from runtime_model_lifecycle import validate as validate_model
    return validate_model(candidate, budget=budget, repair_from_history=repair_from_history, reuse_build=reuse_build)


def evidence(candidate):
    """Reject missing, retired or stale evidence; never execute on the host."""
    try:
        require_model_runtime(read(Path(candidate) / "runtime/prepared.json"))
    except (OSError, ValueError, TypeError) as exc:
        return {"schema_version": 3, "backend": "docker", "status": "needs_review", "error": str(exc),
                "validation": {k: "not_verified" for k in ("environment", "interface", "behavior")},
                "agent_effect_status": "not_evaluated"}
    from runtime_model_lifecycle import evidence as evidence_model
    return evidence_model(candidate)


def stage(drafts, job_id, bindings, *, deadline=None):
    require_model_runtime(read(bindings))
    reports = {}
    from runtime_model import BudgetExceeded
    for candidate in sorted(Path(drafts).iterdir()):
        if not (candidate / "SKILL.md").is_file():
            continue
        try:
            import time
            if deadline is None:prepared = prepare(candidate,job_id,bindings)
            else:
                if deadline-time.monotonic()<1:raise BudgetExceeded('Creation deadline exhausted before runtime preparation')
                prepared = prepare(candidate,job_id,bindings,budget_seconds=int(deadline-time.monotonic()))
            if prepared.get('restored_previous_runtime'):
                reports[candidate.name] = prepared['status']
                continue
            report = validate(candidate)
        except BudgetExceeded as exc:
            report={'status':'budget_exhausted','error':str(exc)};write(candidate/'runtime/execution.json',report)
        except (ValueError,KeyError,TypeError) as exc:
            report={'status':'needs_review','error':str(exc),'failure_kind':'configuration'};write(candidate/'runtime/execution.json',report)
        except OSError as exc:
            report = {"status": "blocked_resources", "error": str(exc)}
            write(candidate / "runtime/execution.json", report)
        reports[candidate.name] = report["status"]
    return {"runtime_mode": "docker", "runtime_status": aggregate(reports.values()), "runtime_checks": reports,
            "agent_effect_status": "not_evaluated"}
