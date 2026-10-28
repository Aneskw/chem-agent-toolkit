# Docker dependency build protocol — stage two

Historical stage-two protocol. Stage three supersedes execution, retry,
qualification and recovery behavior: see [docker-execution.md](docker-execution.md).

On Windows, deep evidence paths may require repository-local
`git config core.longpaths true` to check out/stage preserved snapshots.

Normal native builds call `prepare` after independent content review, then freeze
the resulting inputs, call `LocalExecutor.build`, and adopt each outcome through
the existing single catalog transaction. No second authoring or publication flow
is introduced. Drafts and reviewed reading-only skills skip Docker. Unresolved
requirements and ambiguous bindings produce a saved candidate with concrete gaps.

## Inputs and scope

Optional configuration is `runtime.<candidate-name>`:

```json
{
  "binding": {
    "entry": "scripts/tool.py", "source_id": "upstream",
    "source_path": "tool.py", "association": "identical"
  },
  "options": {"build_seconds": 600, "model_timeout": 600},
  "constraints": ["Use the source-declared dependency versions"],
  "resource_refs": {
    "required dataset description": {"path": "/local/data.bin", "sha256": "expected digest"},
    "required credential description": {"env": "TOOL_LICENSE"}
  }
}
```

Without a configured binding, a unique identical delivered `.py`/`.sh` file and
registered source file can be bound automatically. Otherwise preparation blocks.
An explicit adapted-file association uses `association: explicit`, `reason` and
an exact source `quote`; the user supplies this association, not an unverified
model claim. A named delivered entry must exist. First implementation supports a
single delivered file entry per candidate; an installed upstream CLI alone is not
the final Skill entry and does not satisfy this boundary.

An optional `plan` object bypasses model planning, but never program validation.
The schema is `runtime/planner.py::PLAN_SCHEMA`. It includes source-selected files,
dependencies/choices with evidence, container-only installation steps, resource
requirements, and grounded locked tests. `resource_assessment` explicitly records
`complete`/`unknown`, a source citation and CPU/memory requirements. General test
or scientific limitations remain in `unresolved`/`unverified_behavior`; they are
not confused with missing execution resources. Source citations constrain model
reasoning but substring verification is not proof of all semantic judgments.

Invalid-input handling is classified per operation with three states, and the
requirement is kept separate from its verification:

| state | when | obligation |
| --- | --- | --- |
| `required` | the caller, the delivered interface (a wrapper's own error branch counts) or the source states a constraint | a named check and an actual rejection case that passes |
| `none_documented` | no examined material and no promise declares a contract | records `reason`, `scope`, `limitation`, `checked` materials with fingerprints and an independent confirmation; reported as a validation gap |
| `not_applicable` | the operation has no caller-supplied business input | normal functional verification only |

The policy's `invalid_input` is the strongest declared state. Coverage reports
`coverage_complete` (were the applicable declared checks covered), `validation_gaps`
(which behavior has no contract basis) and `blockers` (a stated obligation without a
verifiable contract) separately. A recorded gap never replaces a stated obligation:
`none_documented` cannot waive a requirement expressed by the caller, the delivered
interface or an author-declared rejection check, and it needs an independent review
artifact that `preparation.confirm_gaps` binds; without one the classification is
only a declaration and runtime preparation blocks with `invalid_input_review_missing`.

The old planner's source inventory, demand reads, plan/patch validation and
acceptance-contract checks are adapted internally. Tests must invoke the actual
delivered entry and cover declared operations. Environment changes cannot remove
or change locked cases or their acceptance policies. Source, scope or oracle
changes requiring new independent review are outside runtime-only recovery.

Production defaults disable aggregate time, attempt, read-round, file-count and
context-size quotas. Single model/build operations retain configurable timeouts.
Explicit global/candidate model-call limits and global time limits also constrain
the adapter. Repeated diagnostics or material requests with no new information
stop. There is no automatic build-failure repair loop: diagnostics identify the
environment lane, and `runtime-prepare` takes an explicit replacement plan or
invokes planning for a new revision. Content repair remains with the native flow.

## Resource checks and execution boundary

Docker engine OS/architecture, CPU count and memory are queried from Docker,
not the Windows host. Required files need a supplied path and matching SHA-256;
credentials need an existing environment reference. Credential values are neither
put in build inputs nor forwarded into Docker builds. Only resources marked
required for the selected scope are checked. A model's `available: true` is never
used as a host observation. Unknown requirements do not become resource success.

GPU, private dependencies and external-service/network requirements without a
local verifier remain `runtime_blocked`; no remote service, CPU substitution or
cloud purchase is implemented. Public package downloads are attempted by Docker
and their real failures are recorded as `build_failed`. Missing Docker prevents
model calls; an explicit plan can still be validated/materialized offline.

`RuntimeRequest` binds candidate/revision, package/source/binding/environment/
acceptance fingerprints and the freeze hash. Local paths locate the envelope and
separate attempt directory; receipts contain portable identities, not those paths.
`executor_kind=local-docker`, `target_id=local` reserve a transport boundary; other
targets are rejected. Remote authorization/transport and execution are not built.

Builds use Docker `--iidfile` and inspect that immutable ID, platform, entrypoint
and revision labels. A stopped container is created only to copy the package out
and verify every delivered byte; no business code is run by that inspection.
`validate()` deliberately raises `NotImplementedError`. No Docker `RUN` result,
import success, image creation or package byte check counts as business acceptance.

## Durable files and observations

```text
skills/
  catalog.json
  candidates/<name>/                    # reviewed authored package
  evidence/<candidate>/<snapshot>/
    package/                           # exact authored bytes
    sources/ + sources.json
    runtime/context/                   # Dockerfile, selected source, final package
    runtime/plan.json
    runtime/locked-tests.json
    runtime/planning/                  # real model responses/receipts if called
    record.json + freeze.json
  runtime/<candidate>/<attempt>/
    attempt-start.json
    receipt.json + build-log.json
    image.id                           # when build succeeds
    image-package/                     # stopped-image integrity inspection
```

The environment contract includes the materials manifest and relevant resource
identities (hashes/environment-variable names, not paths or values). Changed
binding/plan/materials/tests generate a new revision and withdraw old eligibility.
Dynamic attempt files are independently hashed, verified on library access and
copied into the library by the same publication transaction. They remain outside
the freeze. Partial/unreferenced attempts never replace a committed catalog item.

`delivery` remains the historical frozen snapshot. The catalog's `runtime`,
`current_execution` and `current_host` describe the latest attempt:

| Build state | Execution state | Formal qualification |
|---|---|---|
| prepared/built | not_run | false for execution-required candidates |
| runtime_blocked | runtime_blocked | false; content result preserved |
| build_failed | build_failed | false; environment diagnostic |

`current_host` is timestamped preflight information, not a permanent promise.
`verify_current(request, receipt)` rechecks resources and the exact image ID;
missing images return unavailable without rewriting historical build facts.
No required candidate is promoted in this stage, even if a stored status says
`passed`. Future acceptance must implement independent evidence verification.

## Recovery

`runtime-build LIBRARY --candidate NAME [--resource-refs refs.json]` rebuilds from
an intact frozen candidate without discovery/authoring. Previous attempts remain
in `runtime_history`. `runtime-prepare LIBRARY --candidate NAME --spec spec.json`
creates an environment revision while preserving authored files and source bytes,
locks existing tests, and publishes with an expected-parent check. A new resource
digest/reference identity requires this latter operation; relocation of the same
verified resource does not. Drafts and unreviewed/changed content cannot use it to
bypass independent review. Invalidated source/package evidence needs review again.

Stage three must consume this request and locked contract, run actual delivered
entrypoints, inspect business assertions, revoke content approval when appropriate,
and implement the final qualification verifier. It must also supply execution
resource mounts/limits, remote adapters if later authorized, and installation of
runtime materials for executable accepted packages. None is claimed here.
