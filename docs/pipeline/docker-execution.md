# Docker execution protocol — stage three

This extends the stage-one delivery/catalog and stage-two planner/build contracts.
`pipeline.build` remains the sole discovery/author/review/repair/adoption flow.
Normal executable candidates run prepare → freeze → build → validate → qualify.
Drafts skip execution and cannot qualify. Reviewed source-supported non-executable
skills skip Docker. Unknown requirements remain blocked candidates.

## Bound inputs and frozen/dynamic boundary

`RuntimeRequest` still binds candidate/revision, files, sources, tool association,
environment, acceptance version/fingerprints and freeze hash. `LocalExecutor`
implements `preflight`, `build`, `validate(request, build_receipt=None)`, and
`verify_current`. Other executor/target values are rejected; remote transport is
not implemented or verified.

Author completion receipts cover authored files. Final freeze additionally covers
source snapshots, validated plan, build context, locked tests and review evidence.
Neither execution nor environment repair edits that envelope. Changed files,
sources, environment or contracts require a new revision. Dynamic attempts live at:

```text
skills/catalog.json
skills/accepted/<name>/                  # authored files only
skills/candidates/<name>/
skills/evidence/<candidate>/<snapshot>/  # immutable package/sources/runtime/record/freeze
skills/runtime/<candidate>/<attempt>/
  receipt.json + build-log.json + image.id
  image-package/                        # build-time inspected package bytes
  execution/started.json
  execution/tests.json
  execution/report.json
  execution/case-<digest>/               # retained actual output files
```

Build receipts remain historical `built/not_run` records. Execution reports bind
the build receipt hash, image ID/tag, all request fingerprints and locked cases.
Attempt manifests cover reports, logs and retained files. Catalog `runtime` selects
the current attempt; `runtime_history` and revision `history` retain predecessors.
`delivery.content/execution/host` are frozen historical observations. Catalog
`current_content`, `current_execution`, `current_host` and `current_qualification`
are separate. A prior execution pass can remain historical while current eligibility
is withdrawn; `runtime_invalidated` records this event.

## Container checks

Existing native configured/generated checks are declared before freezing, then
appended to the migrated source-grounded business cases. There is no production
host execution for those checks:

| Native declaration | Container mapping |
|---|---|
| `{python}` | validated Python plan interpreter |
| `{package}` | `/opt/skill/package`, immutable delivered files in image |
| `{source:ID}` | `/sources/ID`, frozen source tree mounted read-only |
| `{run}` / artifacts | `/output`, retained after exit/timeout |
| cwd | declared mapped directory, default `/output` |

Unknown source macros, undeclared host absolute paths and escaping artifact paths
are rejected. Image integrity verifies all delivered support files and selected
source bytes before business cases. The migrated runner retains stdout/stderr,
exact argv, expected exit, JSONL/subset/tolerance/relation assertions, semantic
acceptance assertions, file fixtures, persisted output checks and operation/input
coverage. Native JSON assertions/artifact declarations supplement those checks.
Passing an import or upstream test runner never supplies business coverage.

Containers use an immutable image ID, read-only rootfs and input/source mounts,
UID/GID 10001, dropped capabilities, no-new-privileges and configured resource/time
limits. Network is disabled for the public CPU sample. Output files use a writable
mount; timeouts kill the client process tree and explicitly remove the named owned
container. Partial stdout/stderr/files and cleanup observations are retained. A
cleanup error records its ownership scope for recovery; it is not called success.

## Outcomes, retries and qualification

| Observation | Outcome / route |
|---|---|
| Required resource missing/unknown | `runtime_blocked`, preserve content/materials/locked tests |
| Docker build fails | `build_failed`, environment planner feedback |
| Dependency probe fails, no contradictory business result | `execution_failed`, environment repair |
| Business result/call fails | `execution_failed`, content approval revoked; existing author + independent reviewer |
| Contract/coverage invalid | failed/blocked with diagnostic; no invented pass |
| All applicable tests and current evidence pass | eligible only if normal mode and independent content approval also pass |

Normal build feeds environment failures to the existing runtime planner with the
previous plan, diagnostic and unchanged locked cases. Content failures return to
the partner author/reviewer. Both use the same candidate loop/catalog. Repeated
file/plan/failure signatures stop; explicit aggregate limits remain effective
across retries. No hidden production attempt quota is introduced.

The only admission gate is `contracts.qualify`, used by the existing store and
installation paths. For required execution it revalidates frozen bindings, raw
results, actual output hashes, coverage, current Docker resources, immutable image
ID and retention tag. Status flags alone cannot qualify. Default query/install
exclude candidates; image/tag loss demotes accepted items without erasing old
execution facts. Restoring a tag alone does not automatically re-promote.

Known wrong business results cannot turn into success or disappear behind a later
resource failure. One failed candidate does not prevent other candidates from
being handled; a mixed successful/failed build reports `partial`.

## Explicit recovery

```text
python -m creation_pipeline runtime-validate LIBRARY --candidate NAME
python -m creation_pipeline runtime-build LIBRARY --candidate NAME
python -m creation_pipeline runtime-prepare LIBRARY --candidate NAME --spec spec.json
python -m creation_pipeline runtime-prepare LIBRARY --candidate NAME --spec spec.json --oracle-correction correction.json
```

`runtime-validate` reuses a bound build, never old execution results. `runtime-build`
rebuilds frozen inputs and then executes. `runtime-prepare` creates an environment
revision, preserving authored/source bytes and locked assertions; it then builds,
executes and adopts via expected-parent catalog update. Revoked content cannot use
ordinary runtime-only recovery to regain approval.

Oracle correction requires an explicit replacement plan, a reason and verified
source citations, then a fresh independent partner reviewer confirming
`oracle_changes_verified`. Test names/promised operations/purposes cannot simply
be dropped. Review evidence is retained even on rejection. A confirmed correction
creates a new acceptance/environment revision, preserves old history and executes
again. Scope/content changes use author repair and review instead. No correction
is inferred from observed output. This approval interface has mechanism tests;
no real source-oracle correction was needed for the RDKit sample.

Library install copies runtime envelope/evidence to `.runtime/<name>/` beside the
authored skill. Bundle install uses `runtime/<name>/`. Frozen manifests stay intact;
build materials, immutable image identity and stable actual entry remain available.

## Deliberate limits

First implementation validates local Linux amd64 CPU/public-dependency workloads.
Required GPU, services, runtime networking, private dependencies, external weight/
data mount contracts and secret delivery are not implemented. Even when an external
file/env reference exists, unsupported delivery is reported as a concrete blocker.
No host installs, mock/CPU substitution for another target, cloud purchase or remote
service are performed. Historical test facts are not a guarantee on another host.

Snapshot/log hashes provide local integrity, not a remote attestation system or
scientific proof. Keep current host checks at consumption boundaries. Native model
review and real CPU tests provide the specifically recorded scope only.
