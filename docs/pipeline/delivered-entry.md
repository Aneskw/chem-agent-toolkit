# Delivered execution entries

The native author chooses useful delivery files. An executable skill does not
need an extra script solely to satisfy runtime packaging. Runtime preparation
supports unchanged source scripts, reviewed source-associated scripts, and one
complete Python fence in the final `SKILL.md`.

## Resolution order

The entry is resolved in this order; each step is validated and a failure blocks
instead of falling through to a different entry.

1. **Caller binding** (`runtime.<candidate>.binding`). The path, the delivered file
   and the source association are checked. A failure is `binding_unresolved`; the
   entry is never silently re-derived.
2. **Author declaration** (`metadata.entry` in the delivery receipt, persisted with
   it):
   `{"kind":"script","path":"<delivered .py/.sh>"}` or
   `{"kind":"markdown_python","path":"SKILL.md","block_index":<n>}` with an optional
   `code_sha256`. This is how a package may deliberately deliver scripts plus
   documentation examples without being called ambiguous.
3. **Conservative recognition** for deliveries without a declaration: a single
   conforming candidate is adopted; two candidates remain `entry_ambiguous`.

A declaration only selects. It is validated before use - the path must be a safe
relative path of a delivered file, a script entry must be a nonempty delivered
`.py`/`.sh`, a Markdown entry must extract one complete unindented block (and match
`code_sha256` when one is given), and static code checks still run. Source
association, the exact-quotation check and the independent review are unchanged: a
declaration cannot substitute for source evidence or reviewer approval.

The resolved binding records `declaration` and `declaration_source`
(`user_binding`, `author_declaration`, `identical_bytes` or `conservative`). Because
the binding enters `inputs.bindings` - and therefore the revision fingerprint - the
declaration, the entry locator/content hash and the delivered-file manifest are all
bound to the delivery. The unchanged plan validator requires the plan to invoke the
bound entry (`runtime_path`), so Docker executes that entry and cannot substitute
another implementation.

## Association and invocation

`runtime-prepare` and normal `build` share the same preparation, planner,
executor and catalog. Exact unique `.py`/`.sh` source copies retain their strict
byte-identity path. Other entries require a model association proposal containing
the delivery entry, original source ID/path, exact quotation, reason and invocation
description. Programs verify paths, source hashes and quotations. A separate native
reviewer must confirm the semantic API relationship, delivered context and scope;
the proposer cannot approve itself. Missing evidence or a rejected association
does not trigger repeated proposals within the same attempt.

The invocation description covers interpreter, arguments or function inputs,
working directory, outputs and required supports. The existing environment planner
turns that description into a validated executable plan and locked tests. It may
not synthesize or overwrite business code.

## Markdown Python v1

Without a declaration the deterministic selector requires exactly one unindented,
complete backtick fence labeled `python` or `py` in `SKILL.md`. A declared
`block_index` selects one specific complete block, which is why a usage example no
longer makes a Markdown delivery look ambiguous. Either way the selector records the
original Markdown SHA-256, the zero-based block index, byte offsets, start line and
exact code SHA-256. The code bytes, including line endings, are copied unchanged into
`entry/skill.py` in the runtime handoff/build context. This file is runtime material,
not an independently authored replacement for the Skill.

Python is parsed without execution. Syntax errors and unresolved global names
are content/context defects. Multiple blocks, nonstandard/nested fences, interactive
input, dynamically constructed execution and ambiguous script selection are not
supported by this automatic selector. It never combines blocks, adds imports,
inserts function calls or fills in missing context. Static checks are conservative;
passing them is not proof of safe or correct runtime behavior.

A standalone example can be run as extracted. A function may be used only with an
explicit reviewed invocation contract and complete applicable tests. Running a
function definition without exercising its promised behavior does not establish
business acceptance. Existing author checks may read the exact final Markdown
and execute its block; those checks are preserved and translated by `mapped_checks`.
Any unsupported macro or host path is rejected, not silently removed.

All delivered supports remain in `package/`; sources remain separately identified.
No second harness implements the algorithm. The model must plan the actual
extracted entry and the tests must cover the declared use. Existing coverage,
strict assertions, environment-repair locks and independent oracle-correction
rules continue to apply.

## Integrity and failure paths

The binding includes the complete delivered-file manifest and extraction locator.
The existing revision fingerprints bind it to source, environment and acceptance
contracts. Runtime materials and association/reviewer evidence enter the existing
freeze. Before build/execution, deterministic extraction is repeated and compared
with frozen material bytes. Image checks include both the complete package and
the selected extracted entry. A document, code block, support, source, environment
or contract change cannot reuse the old qualified revision.

- Confirmed syntax/context or independently reviewed file defects revoke content
  approval and return to the existing author/review branch.
- Unsupported entry shape is `runtime_blocked` with `blocker_kind=unsupported_contract`.
- Ambiguous association or reviewer nonapproval is `unresolved_input`.
- Host/resource conditions retain the existing temporary-resource diagnosis.
- Runtime-only recovery never authors files. Explicit saved-plan continuation can
  reuse verified reviewed-but-blocked bytes without discovery or author calls.
  A newer durable association-review rejection in the selected catalog overrides
  an older plan's approval and goes to the existing author branch. Correct author
  checks stay locked through that content repair.

An explicit retry does not imply qualification. The existing store transaction
alone promotes a content-approved and genuinely execution-approved revision.

## Source identity

Local input directories inside a repository expose `carrier_repository`, not an
inferred upstream version. A repository root may retain its local revision; model
views label local/legacy references separately when no upstream repository is
verified. Input inventory hashes and snapshot IDs always identify actual bytes.

An immutable `https://raw.githubusercontent.com/<owner>/<repo>/<40-hex-commit>/<path>`
source records the retrieved upstream repository, commit, path and content hash.
Configure `sha256` to require the expected bytes. Mutable URL names and arbitrary
local files do not acquire a guessed upstream version. Upstream identity is passed
to authors, reviewers, association proposals and planner source handoff. Historical
records remain unchanged; an old unverified `resolved_ref` is explicitly described
as insufficient evidence of upstream version.

Remote GPU, external resource mounts, credential delivery and external services
remain unsupported. Software installation remains container-only.

### Outer literal fences

A Python-looking fence inside a larger backtick or tilde code fence is literal documentation, not a delivered executable entry. The selector tracks surrounding fences before recording byte offsets. The existing single-block rule and exact code bytes remain unchanged; no author script is required to work around this executor boundary.
