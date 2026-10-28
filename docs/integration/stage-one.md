# Stage one: integration baseline and verification

Scope: identity, qualification, durable dual-zone library, pure-text/draft paths,
and runtime handoff contracts. Docker construction/execution remains later work.

## Fixed inputs

- Partner: `e117c434f54d11fd24e3e5566f187a8f4a41a87f`.
- Docker reference: `d5b77dc5d91711567af1960530d03739a5c442bf`, r3.1.
- Remote check on 2026-10-25: partner branch still e117c43; main was 1e7cada.
  No newer main changes were imported.
- Independent branch: `integration/docker-stage1`; original workspaces untouched.
- No applicable AGENTS.md was found in the inspected ancestry/project trees.
- The two supplied Mermaid designs were read; current user stage instructions
  resolve the policies their old comments still mark undecided.

## Environment and baseline

Windows, Python 3.14.3, existing `.venv-runtime` interpreter (no host installation).
The 102 original tests passed on the pinned partner checkout in the integration
workspace. The initial run had three Windows sandbox temporary-directory ACL
errors; rerunning with TEMP/TMP inside `.pipeline/test-temp` passed all 102.
The existing Python 3.15 deprecation warning for `PurePath.is_reserved` is unchanged.

Engineering checks exercise host code with deterministic Agent-stage doubles;
they are not evidence of model quality or Docker execution. Original source,
format, check, review, immutability and recovery assertions remain. Tests that
previously treated unexecuted tool content as ready now assert not_run/candidate;
installation and zero-call accepted reuse use an actual reading-only fixture.

See [delivery protocol](../pipeline/delivery-protocol.md) for data, directory,
transaction, invalidation and future runtime boundaries. Final verification
results are recorded alongside this document after the stage checks complete.

## Completed verification

- Full integrated regression: **125 tests passed** (102 original cases retained
  and migrated where policy changed, plus 23 protocol/storage cases).
- After the final disjoint-path and catalog-path hardening, the **23 protocol
  tests passed again**. No assertions were weakened to admit unexecuted tools.
- `git diff --check` passed. Validation files are marked `-text` in Git attributes
  so checkout line-ending conversion cannot corrupt frozen hashes.
- Real Native Agent discovery produced the reading-only checklist candidate.
  Initial author finalization failed because Windows child sandbox denied both
  the venv launcher and the main interpreter helper. These were saved as failed
  candidates, not accepted outputs. No sandbox restriction was disabled.
- Clarified the already existing host `finish` fallback: an explicit completed
  response for fully written files/metadata can request the host to execute the
  exact same validation/receipt routine. File existence alone is insufficient.
- Continued the real saved discovery plan: **2 real CLI turns**, author then an
  independent reviewer. Source-supported not_required content passed, entered
  accepted, and passed durable-copy integrity and installation checks.
- A separate real draft continuation used **2 real CLI turns**. Content review
  passed and requirement was not_required, yet it remained candidates; default
  library query returned zero entries and installation was refused.
- Native libraries, exact source bytes, freezes, records, summaries and test logs
  are preserved under `validation/stage1/`, outside disposable run/cache folders.
  CLI trial configurations contain explicit bounded smoke-test limits; these are
  not production defaults. No Docker execution or scientific validation occurred.

## Stage-two handoff

Use `contracts.runtime_request(delivery, frozen_directory, freeze_sha256,
attempt_directory)` and `runtime.interface.RuntimeExecutor`. Stage one has no
runtime-only resume implementation, environment planner, resource probe, Docker
builder/verifier or remote executor. Required candidates remain not_run. The
future verifier must replace the deliberate fail-closed required-execution gate
with actual image/input/business-evidence verification, never a status boolean.

Existing partner dated skill directories are retained as unregistered historical
artifacts. The v2 active catalog starts empty; no old acceptance is inherited.
Original projects, archives and their historical deletions were not modified.
No remote push, publication or PR merge was performed.
