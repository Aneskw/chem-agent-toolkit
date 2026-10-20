# First implementation acceptance record

Development branch: `pipeline/task-skill-v1`; legacy baseline: `6bb535a`.
Environment: Windows, Python 3.11, Codex CLI 0.158.0, RDKit 2026.03.6.
The CLI used the existing configured model (`gpt-6-luna`); no Agent efficacy test was run.

## Engineering checks

`python -m unittest discover -s tests -v`: **30 tests passed**. Fixture model
responses are explicitly marked replay and are not new extraction evidence.

Coverage includes verbatim single-file builds, bounded repair, unchanged-failure
stopping, missing resources, blocked/draft/failed states, missing minimum-content
attestations, result assertions and expected rejection, extension positive/negative
requirements, evidence-gap handling, hash-checked installation, file/source mutation
detection, paths, controlled cleanup, filtered environments, bounded source views,
CLI turn/tool-event checks, inherited MCP disabling and process timeouts.

CLI help and configuration-only preflight passed. The real compact package was
installed into a temporary directory, its manifest verified, and its documented
example successfully executed outside the build directory. No formal skill
installation, Git push or Agent benchmark was performed.

## Actual model-authored builds

| Case | Build ID | Runtime files | Model calls | Status |
| --- | --- | --- | --- | --- |
| Compact direct | `20261021T001021-bd1db25f` | 1 | 3 | ready |
| Existing-code adapter | `20261021T002118-d64f2cc1` | 2 | 3 | ready |
| User-defined extension | `20261021T001602-c6b19e53` | 2 | 5 | ready |
| New API after code freeze | `20261021T002311-84b1e030` | 1 | 2 | ready |

These final cases used new model calls, not saved response replay. Each output
contains the runtime package and `build.json` under `.pipeline/outputs/<id>/`.
Those local records hold exact file hashes, source excerpts, executed checks and
model usage; outputs are intentionally ignored by Git. All four final builds
removed their registered temporary workspace after successful output verification.

- Compact direct: a **35-line SKILL.md**, with the ethane example plus invalid,
  empty and whitespace-only input checks.
- Adapter: the original descriptor implementation recovered from baseline Git,
  plus a generated CLI adapter. Valid rows, failed-row preservation, original order
  and empty-input behavior were checked. The original implementation stays external
  and its actual repository/revision/file acquisition is documented.
- Extension: a generated user-defined inclusive mass-window CLI, checked for accept,
  reject, malformed/empty input, equality, reversed bounds and a nonfinite bound;
  targeted content review passed. This is a numerical filter, not drug-likeness.
- New resource: installed RDKit CalcMolFormula docstrings were supplied only after
  pipeline code was frozen. The generated example returned ethanol C2H6O and rejected
  invalid/empty/whitespace inputs. Pipeline source/prompt hashes were unchanged
  throughout this case. This is a transfer smoke test within one library, not
  a statistical benchmark or broad cross-tool generalization claim.

## What the unsuccessful trials taught us

Initial trials revealed Windows CLI state access restrictions, repeated WebSocket
timeouts, ambiguity in mediated reading, inherited built-in/MCP tools, and malformed
double-encoded file responses. Those runs were not counted as successful builds.
The backend now mediates reads, disables unrelated capabilities and known user MCP
servers, supports an optional HTTP transport, and uses structured object envelopes
for authored file text. Markdown body organization remains free.

An initial extension stayed draft because essential boundary tests had not run.
An initial adapter ran correctly but lacked the real upstream acquisition address.
The inputs/checks were completed instead of weakening the stated task. Review
now separates missing evidence from defects that file edits can repair.

## Remaining evidence boundaries

- No Agent benchmark, question generation, parallel efficacy trials or A/B gains
  were implemented or run. These remain a later independent project.
- A full paper-plus-implementation case is still to be selected and validated.
  Existing-code adaptation is demonstrated; reconstructing algorithms from formulas
  is outside the first-version scope.
- GPU/weights, live HTTP/remote tool environments and heavyweight dependencies
  are not validated by these local cases.
- PDF parsing is optional; pypdf is not installed here. Supply extracted text or
  install the optional dependency. Scanned-document OCR is not implemented.
- The model calls ran during development with a dirty working tree, recorded as
  such. Default records support scoped provenance, not exact full model replay.
- `ready` establishes the recorded engineering checks in their tested scope, not
  universal scientific correctness or Agent benefit.
