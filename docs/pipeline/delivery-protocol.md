# Integrated delivery protocol

The [Docker execution protocol](docker-execution.md) and [durable recovery protocol](runtime-recovery.md)
extend these identity, freeze and catalog contracts. Local Linux/amd64 build and real
business acceptance are implemented. Historical implementation stages are recorded
separately in `docs/integration/`.

This is the single new pipeline protocol. No old CLI/checkpoint/bindings/ZIP
compatibility is provided. Historical approval is never imported.

## Boundaries and identities

The author `finish` receipt binds authored files to the candidate/feedback token.
It confirms file delivery, not content correctness or runtime acceptance.
The independent review remains mandatory for formal qualification.

After review and applicable stable environment-material generation,
the final freeze stores the exact package, source bytes, source versions, review,
test definitions and delivery inputs. A `freeze.json` manifest hashes every file
except itself; its own SHA-256 is referenced by the output and catalog. Dynamic
runtime attempts/logs and host observations must live outside that frozen tree.

`candidate_id` identifies a library name. `revision_id` is a canonical SHA-256 of
the candidate plan, exact package manifest, portable source identity, requirement,
bindings, environment and acceptance contracts. A changed file/source/contract
creates a different revision; successful old assertions are not transferred.
Identical names do not authorize overwrites: a changed assessment/revision needs
`revision_parents: {name: expected_current_revision_id}`. Publication holds a
catalog lock and checks the current parent, so a stale update cannot win silently.

Every binding/environment/acceptance contract has `version`, `payload`, `sha256`.
Before preparation, bindings and environment payloads are null; acceptance contains
preserved configured/generated/reviewer definitions. Runtime preparation versions
the binding, environment and locked business cases; definitions are not execution evidence.
Exact files/sources/contracts also have aggregate fingerprints for executors.

## Requirement and result

Authors may propose `metadata.runtime_requirement`; users may supply a declaration
under `runtime_requirements.<candidate-name>`. Declarations contain:

```json
{
  "status": "not_required",
  "reason": "The cited method is a manual reading procedure",
  "citations": [{"source_id": "manual", "path": "guide.txt", "quote": "Exact original passage"}]
}
```

The host checks registered files and exact quotations. Independent content review
must return `requirement_assessment: confirmed`; uncertainty/conflict or invalid
citations produce `unknown`. Locator IDs, absent tests and unavailable resources
do not establish a no-execution exemption. Semantic correctness is a reviewer
judgment, not something the quotation substring check proves.

Separate fields record:

- `content.status`: passed, failed, not_reviewed.
- `execution.status`: not_run, runtime_blocked, build_failed, execution_failed,
  passed. Stage one emits only not_run; old host checks do not become Docker facts.
- `host.status`: not_checked, available, unavailable, not_applicable, plus observation time.
- `mode`: normal or draft.
- `qualification`: the result at freeze time. The catalog separately maintains
  `current_qualification`, `current_host` and invalidation events.

Normal, independently reviewed, source-supported `not_required` deliveries can be
accepted. Drafts never qualify. Unknown requirements and required-but-unexecuted
packages stay candidates. The required-execution verifier deliberately fails
closed until the runtime stage implements real evidence checks; setting a stored
`passed` boolean cannot promote a candidate. Stage one does not check Docker/GPU
availability or claim resource preflight has occurred.

## Durable layout

```text
skills/
  catalog.json                       # v2, the only active index
  accepted/<name>/                    # current qualified package files
  candidates/<name>/                  # current unqualified/invalidated package
  evidence/<candidate-id>/<receipt>/
    package/                         # immutable historical package copy
    sources/<source-id>/              # actual input bytes, not cache references
    sources.json                     # relative portable source locations
    record.json                      # review, diagnostics, definitions, delivery
    freeze.json                      # final freeze manifest
  .catalog.lock                      # exclusive reader/writer lock
  .transaction.json                  # incomplete transaction recovery journal
```

Each catalog entry contains the current evidence reference and freeze hash, with
prior references in `history`. Earlier packages/sources/records remain in evidence
after promotion, demotion or revision replacement. Output directories also contain
self-contained evidence; library publication copies it, never points back to runs
or caches. Diagnostic strings may mention original audit paths; those are not
resolvable input dependencies. Future execution must resolve the durable sources
registry and bind to the final package rather than use diagnostic path strings.

Recognizable credential content is rejected before copying immutable files;
diagnostic metadata is sanitized. Credential values are not an environment-input
protocol. Large external assets/secret injection are later runtime work; this
stage makes no promise of remote/secret-resource acquisition.

## Access, transactions and invalidation

`library PATH` returns only current accepted entries. `--include-candidates` is
required for candidate inspection. `install PATH --name NAME --destination DIR`
uses the library and has no candidate override. Installing a build output also
rechecks the frozen evidence and qualification. Static `check` alone grants no
installation approval. No separate recommendation or Agent-consumption service
is added. Consumers must use the catalog API, not recursively scan directories.

Library reads reconcile manifests. Drift demotes an accepted active package to
candidates and records invalidation without changing the historical delivery
fact. Changed current files are unreviewed; they do not rewrite the frozen
revision. A new reviewed build establishes a new revision. Lost/corrupted frozen
evidence blocks qualification; the system does not pretend it can reconstruct
externally destroyed history.

Writers stage complete replacements, journal old/new paths, rename under the
exclusive lock, then atomically replace catalog.json as the commit point.
Pre-commit failures restore old directories/catalog; post-commit recovery retains
the committed state. Incomplete journals are reconciled on the next lock holder.
Stale locks after a killed process require confirming the owner is stopped before
removal. This is not a claim of power-loss durability or distributed locking.
Unregistered active directories and mismatched revision parents are not overwritten.

## Runtime handoff

`contracts.runtime_request()` first verifies the frozen receipt and then binds the
revision and package/source/binding/environment/acceptance fingerprints to its
durable input directory. The attempt directory must be disjoint from that frozen
tree (neither a child nor an ancestor), keeping dynamic records separate.
`runtime.interface.RuntimeExecutor` defines preflight, build, validate and
verify_current boundaries. LocalExecutor verifies actual delivered entrypoints,
business assertions, source integrity and immutable image identity; saves logs and
host observations outside the freeze; and invalidates qualification on drift.

Local Linux amd64/CPU is the implemented first backend. A future remote adapter must
use configured authorized nodes and return evidence bound to the same inputs.
The interface does not purchase compute or implement/validate remote execution.

Production's existing unlimited aggregate defaults remain. This stage adds no
hidden planner/time/read quota and installs no dependencies on the host.
