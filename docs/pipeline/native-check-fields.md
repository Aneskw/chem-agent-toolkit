# Native check declarations are a closed protocol

Supported fields are candidate, name, argv, cwd, expected_exit, stdout_contains,
json_equals, artifacts, evidence, purpose and kind. candidate is optional caller
routing metadata. The same field set is supplied to author and review contexts.
Unknown fields produce a named validation error; they cannot disappear during
native execution or Docker mapping.

Planner case fields such as stdout_equals, input_files, output_file, acceptance and
timeout_seconds are not native declarations. Preserve each intended constraint
using supported native assertions or enforce it in the self-contained check
program. Removing an unsupported user/source-backed assertion to pass validation
is not a valid repair. Planned case contracts retain their separate protocol.

The counterexample at
`E:\Users\27343\Docker\native-check-field-counterexample-20261029.json` showed the
old issue: a declaration with a supported marker and an unsupported exact-output
assertion was accepted; mapping dropped the exact assertion and synthetic wrong
output passed the marker. This was static mapping/comparison only, not a model,
Docker or chemistry run. New regressions reject this at validation and mapping,
reject unknown fixture/typo fields, and retain documented routing metadata.

The first whole-suite run exposed that candidate is a legitimate existing routing
field; it was added to the explicit supported set before completion. The final
whole suite passes 639 tests (three skipped), with three prompt checks green.
Author/review instructions and contexts use the validator's field set. Development
was independent of run74 and did not modify its live code.

Saved-check audit
`E:\Users\27343\Docker\native-check-conformance-accepted-five-20261029.json`
confirms all 30 native declarations in the accepted run59/62/64/65/74 batches use
supported fields and map identically to their original locked cases. It calls no
models, Docker or business implementation and does not rewrite historical checks.
