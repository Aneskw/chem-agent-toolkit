# Durable runtime recovery and relocation

The existing service, LocalExecutor, qualification gate and catalog transaction
remain the only runtime/library implementation. Recovery does not discover or
author an unchanged Skill. `runtime-prepare` remains the explicit entry for changed
environment plans; it preserves source files and locked assertions and may call
the planner when no explicit plan is supplied.

## Commands

```text
python -m creation_pipeline runtime-inspect LIBRARY --candidate NAME
python -m creation_pipeline runtime-resume LIBRARY --candidate NAME [--recover-lock]
python -m creation_pipeline runtime-validate LIBRARY --candidate NAME
python -m creation_pipeline runtime-build LIBRARY --candidate NAME
python -m creation_pipeline runtime-prepare LIBRARY --candidate NAME --spec spec.json
python -m creation_pipeline runtime-relocate LIBRARY --candidate NAME [--revalidate] [--recover-lock]
python -m creation_pipeline runtime-import SOURCE LIBRARY --candidate NAME
```

All selectors are explicit. Default library queries/install still exclude candidates.
Inspect reports historical execution, current qualification, pending operation,
host observations, blockers and the next action. It does not invoke a model.
Resource observations are current, not permanent guarantees.

`runtime-resume` calls the existing `resume_build(..., reuse_image=None)`:

| State / available evidence | Action |
|---|---|
| Unchanged validated plan, no verified completed build | Build, then execute |
| Completed build, exact inputs/log and current image ID/tag match | Reuse build, execute all locked cases afresh |
| Previous partial execution with completed bound build | Preserve partial evidence, clean locally owned scope, execute afresh |
| Build interrupted before a complete verifiable receipt | Do not trust its image; use another verified historical build or rebuild |
| Temporary prerequisite unavailable | Record `runtime_blocked`; preserve materials, history and content approval |
| Unsupported contract | Remain blocked; resource supply alone cannot implement an absent interface |
| Content approval revoked | Independent diagnosis required; this is not proof that business source is defective. Repair actual content/call defects, or use source-backed oracle correction for a verified contract error; plain runtime retry cannot restore approval |
| Frozen input/evidence drift | Stop; resolve inputs/new revision/review, never rewrite expected hashes |

`runtime-build` explicitly rebuilds; `runtime-validate` explicitly requires a bound
completed build. Both now permit an explicitly selected accepted item to refresh
evidence; qualification is withdrawn before the attempt and restored only after
the same gate passes. A bad business result is not an environmental exemption.

## Persistence and atomicity

Before Docker starts, the existing catalog transaction records `pending_runtime`
with an attempt path, revision, decision and local ownership location. The package
is in candidates while recovery is pending. A crash cannot leave a new attempt
silently qualified. Completion updates the runtime reference, current content,
execution/host observations and qualification through the same store transaction.
Old attempts remain in `runtime_history`; same delivery bytes never suppress a
new observation. Input fingerprints and freeze hash are unchanged on runtime-only
retries. `recovery_history` records decisions without becoming a second scheduler.
New revision history also retains pending imported attempts, interrupted-attempt
references and prior assessments. Contract versions and locked-input comparisons use
canonical fingerprints, so typed JSON changes such as `10` to `10.0` cannot silently
bypass versioning or ordinary environment-repair locks.

On retry, interrupted attempt files are inventoried in `interrupted_attempts`;
partial stdout, cases, artifacts and build diagnostics remain accessible. Container
ownership labels use the attempt ID. Local pending scopes are cleaned with the
migrated `runner.cleanup_scope`; observations, including cleanup failure, are
retained. Imported/relocated scope labels do not authorize stopping a producer's
containers at another location. Build inspection containers also carry the label.

Catalog replacement remains the commit point. Failed promotion rolls back staged
package changes and leaves the durable pending pointer. A later retry can use its
completed build, but cannot reuse the previous run's pass flags. Failed rollback
keeps backups/journal for `store.recover`; it does not discard evidence.

Normal process interruption releases the lock in `finally`. A hard process exit
may leave `.catalog.lock`; `--recover-lock` only archives it after proving the
local owner PID has exited. Live/unknown owners are refused. Windows uses process
exit status rather than treating an openable exited-process handle as live.
This is explicit single-host recovery, not distributed locking or remote leasing.

## First-run interruption and portable delivery

The native pipeline writes the frozen candidate record before its first Docker
operation. Thus an interrupted run can be imported without a complete bundle or
successful summary. `runtime-import` accepts either:

- Native output with `records/NAME.json`, the referenced frozen envelope and any
  pending/completed runtime attempt.
- The current installed `.runtime/NAME/` envelope (`frozen/` plus `attempt/`).

Import verifies the freeze, sources and delivery identity, copies recovery evidence
into the one library via `store.adopt`, and does not inherit execution approval.
Complete native attempt evidence is also checked before import. Known content
revocation is preserved. Existing names are never silently replaced; use their
explicit recovery/revision path. Required execution remains candidate-only until
`runtime-resume` succeeds. The original output/installation may then be removed;
the catalog references only library-owned frozen/material/evidence directories.

For ZIP transfer, archive the entire current library (catalog, both zones, evidence,
runtime and histories), not just `SKILL.md`. After extraction use `runtime-relocate`
and `runtime-resume`, or `runtime-relocate --revalidate`. Native output/envelope
archives can instead be extracted and passed to `runtime-import`. These commands
do not accept legacy ZIP/bindings/checkpoints or implement an archive extractor.

`execution_location` binds a library's current qualification to its observed root.
Copying a catalog does not preserve that qualification. Executable bundle installs
also refuse a moved/unbound output. The execution verifier separately checks that
the recorded Docker engine ID matches the current engine. Even loading the same
image/tag on another engine cannot inherit an old execution pass.

Relocation first verifies all package/source/context/locked-test bytes. Pure path
changes do not change revision/freeze hashes; they require fresh execution proof.
Content changes fail before relocation mutation. Relocation history retains the
previous location/qualification. No timestamps or manifests are relaxed. Reviewed
reading-only deliveries use the same content/no-execution gate without Docker;
drafts remain unqualified.

## Blocker categories and scope

`gap.blocker_kind` distinguishes `temporary_resource` (Docker/CPU/memory or missing
reference), `unsupported_contract` (GPU/platform/service/secret or external-resource
delivery), `unresolved_input`, `caller_limit` and deterministic `failure`.
External weight/data and credential requirements retain an unsupported-contract
gap even when a particular file/env reference is also missing. Satisfying that
reference alone never makes the interface supported.

First scope is unchanged: local Linux amd64 Docker, CPU and public dependencies.
No remote GPU service, resource mount contract, secret delivery, cloud purchase or
fallback CPU/mock acceptance is added. RuntimeRequest still binds candidate/revision,
package/source/binding/environment/acceptance fingerprints and freeze hash; receipts
bind image, environment and actual business results. `executor_kind/target_id` reserve
the future authorized-node boundary; LocalExecutor rejects non-local targets.

Preserved hashes are local integrity records, not remote signed attestation.
Historical success, current qualification and timestamped host availability remain
separate. A copied `summary.json` is never a substitute for current verification.

## Source diagnosis and automatic contract correction

Ordinary business assertion failures now start with `repair_lane=unknown`, not a
claim that Skill code is defective. Cases preserve raw exit/output/environment
observations. `review_required` is a conservative gate, not proof of a source defect.
Environment probes still route to environment preparation; resource/unsupported
contract gaps retain their existing distinct categories.

For frozen candidates, the existing `runtime-resume` (or `runtime-prepare` with an
options-only spec) can diagnose a contract/unknown failure from source. No new CLI:

```sh
python -m creation_pipeline runtime-resume ./skills --candidate NAME
python -m creation_pipeline runtime-prepare ./skills --candidate NAME --spec options.json
```

The tool-free model receives frozen source, delivery, original plan and observations.
It proposes data only. Program checks exact source citations, old values and allowed
edit fields; the existing separate reviewer must approve before preparation, a new
contract version, full execution and the existing catalog transaction. Inputs, source,
negative cases, call scope, assertion kinds and allowed-value cardinality are immutable
in automatic correction. No coercion/tolerance is added. Explicit `--oracle-correction`
remains available through the same approval helper. A content conclusion returns to
the normal build's author/review loop; runtime-only recovery never starts an author.

Unknown, rejected or repeated diagnosis stops without promotion. `runtime_diagnosis`
references durable model input/receipt, proposal and outcome; successful correction
also freezes the full diagnosis/review audit with its materials. Old failure and
diagnosis references remain in catalog history, including after an author repair.
Execution report `acceptance_version=2` is the runner protocol, distinct from the
versioned acceptance contract in `delivery.inputs.acceptance.version`.

Before locking, exact stdout can be compared to an assertion on that same stdout
(or a file capturing stdout), using the original strict JSON/JSONL path semantics.
An independent output file is not stdout. This limited satisfiability check cannot
decide scientific correctness or the intended oracle; source review remains necessary.

## Restricted execution environments

An inaccessible Docker daemon is `runtime_blocked`, not `execution_failed` and not successful reuse of a historical image. A copied accepted library must first lose path-bound qualification; default query and install cannot expose it while fresh validation is blocked. Preserve the historical receipt and the new blocked attempt separately. Source acquisition denied before discovery creates a blocked build with no candidate; it is not an execution-phase recovery or evidence of successful creation. See the final acceptance review for a recorded example.
