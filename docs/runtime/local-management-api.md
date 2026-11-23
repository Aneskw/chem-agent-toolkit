# Local management API v1

Python entry: creation_pipeline.management.dispatch(request). CLI: python -m creation_pipeline manage REQUEST.json. contract() exposes the machine contract. These operations handle local RuntimeRequest and ToolArtifact data.

## Versioned envelope

```json
{
  "api_version": "chem-local-management/v1",
  "request_id": "operator-001",
  "operation": "tool.availability",
  "params": {
    "registry": "E:/operator/shared-tools",
    "reference": {"request_key": "<64 lowercase hex digits>", "artifact_id": "<64 lowercase hex digits>"},
    "offline": true
  }
}
```

Replace placeholders with concrete identities. api_version must match exactly. request_id is 1–128 ASCII letters/digits or ._:-, starting with a letter or digit. Unknown operations/fields and nonboolean offline are rejected. Both successful and failed operations return the envelope:

```json
{
  "api_version": "chem-local-management/v1",
  "request_id": "operator-001",
  "operation": "tool.availability",
  "ok": true,
  "observed_at": "<UTC ISO8601>",
  "data": {"available": null, "availability": "historical_unverified"},
  "error": null,
  "evidence": [{"path": "<local record path>", "kind": "tool_artifact_record", "sha256": "<file digest>"}],
  "side_effects": {"docker_observation": false, "builds": false, "model_calls": false}
}
```

data and side_effects above are excerpts; a full response has the contract's nine top-level fields. data projects the operation result; native/observation/observations preserve underlying results and Docker metadata observations. evidence path/kind/sha256 identifies actual input, registry, freeze or attempt files. Missing observation files have sha256=null. Digests describe bytes read for this operation; they are unsigned and do not guarantee continued availability. Output uses sanitized/redact.

An error contains code/object/field/expected/actual/reason/source_refs/raw. raw preserves underlying reasons, exception types or structured results, including mismatch details. For selection_failed, raw.observation.reason retains selected_request_mismatch and all mismatches[field,expected,actual]. Missing-image execution failures retain the receipt/gaps and current attempt's report/build-log references.

Base error codes include request_invalid, descriptor_invalid, request_changed, selection_failed, artifact_invalid, host_unavailable, not_found, lock_conflict, operation_failed, execution_failed, execution_blocked and cancelled. Named RuntimeBlocked codes such as binding_unresolved, revision_changed and independent_review_required pass through. Clients must preserve unfamiliar code/raw values rather than infer retries, budget increases or backend changes.

Exit codes: ok=true → 0; request_invalid → 2; other errors → 1. ok=true means the operation completed: resolve misses, unavailable images, qualification=false and offline unknown are valid observations. request_id correlates logs; it supplies no idempotency or cache. Repeated execute creates a new attempt.

## Operations and call order

| Operation | Required params | Optional params | Behavior |
| --- | --- | --- | --- |
| tool.describe | context, entry, declaration | requirements, constraints, runtime_limits, tool_compatibility, caller_constraints | Read context/package and context/sources/<id>; derive source mapping through preparation.bind, then shared_tool.describe; caller-asserted identical bindings are not accepted |
| tool.resolve | descriptor, request_key | registry | Re-describe and compare request_key before resolve; a miss performs no planning, build or Skill binding |
| tool.select | descriptor, request_key, reference | registry | Recompute the request and select only that version; missing, incompatible, corrupt or unavailable artifacts return selection_failed without fallback |
| tool.availability | reference | registry, offline | Validate record identity and current daemon/image; offline checks recorded evidence only |
| skill.execute | library, name, expected_revision, expected_freeze_sha256 | None | resume_build with reuse_image=true and allow_diagnosis=false; recheck under lock and execute the current locked contract in a fresh attempt, without builds, model calls or automatic repair |
| skill.qualification | library, name | offline | Online store.get/reconcile/qualify; offline static catalog checks with accepted=null |
| references.query | libraries, tool_registries, environment_registries, target | None | Read-only dependency lookup over explicit roots; see the reverse-reference protocol |

descriptor has the same shape as tool.describe params. Arbitrary request JSON without current-material checks is rejected. context is normally prepared/frozen runtime/context; entry is package-relative. declaration is the complete shared_tool declaration. runtime_limits accepts memory/cpus/pids through planner.options. v5 tool_compatibility uses the configuration v1 object. Unclassified requirements/constraints and full caller_constraints conservatively participate in tool identity. describe does not generate skill_contract or acceptance plans.

Description is an observation, not a file lock or qualified Skill. resolve/select recompute bytes to detect drift; preparation, freeze and execution perform their own checks. Recommended sequence: describe → resolve or select → availability → build/runtime-prepare with content review, current acceptance planning and concrete binding → execute → qualification. Explicit selection returns binding_persisted=false; preparation/freeze and receipts create the actual SkillBinding.

```json
{
  "api_version": "chem-local-management/v1",
  "request_id": "execute-001",
  "operation": "skill.execute",
  "params": {
    "library": "E:/operator/library",
    "name": "descriptor-rule-screening",
    "expected_revision": "rev-<64 lowercase hex digits>",
    "expected_freeze_sha256": "<64 lowercase hex digits>"
  }
}
```

Select a concrete revision/freeze before execution. The service rechecks under the writer lock; revision_changed reports field/expected/actual. Required diagnosis or review returns independent_review_required. Execution cannot silently change the business contract or incur model costs.

The service also returns evidence_snapshot under that lock, and response freeze/runtime/pending_runtime references use that snapshot. A later catalog read must not substitute another attempt. Interruptions and execution exceptions carry their locked-context snapshot. catalog.json digests describe bytes observed at response time; they do not establish a cross-file transaction snapshot. Missing complete bindings are rejected; missing images are not rebuilt automatically. Recovery and preparation use their explicit CLI entries.

## built, available, passed and accepted

- built is a recorded build fact. record_verified checks record format and identity, not a new build or complete execution-time image inspection.
- available observes the current target. Resolve/select/availability check daemon/image metadata; v2 additionally checks executables/plugins/data/rootfs. This grants no business result or new binding.
- passed comes from a new execution_passed result, with current cases, sources, locked contracts and full image checks.
- accepted is current qualification. passed=true can coexist with accepted=false. Offline returns null rather than inheriting catalog placement or recorded accepted. Valid no-execution Skills use their qualification branch without fabricated passed evidence.

## Query side effects and cancellation

side_effects lists possible actions, not command counts. describe has no Docker or writes. Registry observations create no directories, locks or images and do not write catalogs. Online v2 probes create and remove owned temporary containers. Offline availability never calls Docker.

Online qualification uses store.get, which can lock the catalog, recover transactions, reconcile accepted/candidates state and update evidence. Docker qualification may run probes. Offline qualification performs static checks without locks, recovery, writes or Docker and grants no current qualification. There is no unified TTL or cross-operation snapshot. Missing libraries are rejected before a query could create them.

execute writes attempts, journals and catalogs and may clean up its interrupted execution scope. Cancellation follows runner/service cleanup, pending journals and owner-lock rules, returns cancelled with existing evidence and grants no qualification. It does not steal locks, resume failed tests or delete unrelated Skills/tool versions. Reusing request_id does not suppress execution.
