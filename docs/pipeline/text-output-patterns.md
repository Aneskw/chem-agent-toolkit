# Source-grounded text output patterns

A normal non-JSON file outcome can use `acceptance.assertion.kind=text_regex`.
The pattern full-matches the actual retained file, or stdout if no output_file
is declared. Source citations and structural/numeric business expectations remain
required. JSON stdout metadata can be asserted separately. The runner does not
trim text or repair a predicate to make it pass.

When a representative complete positive output exists in read source materials,
declare `acceptance.assertion.example_source_path` with its exact indexed path.
Before locking the plan, the validator reads that UTF-8 file with the same newline
reading used for retained output and checks the full-match pattern against it.
An unread/escaping path or non-matching example is rejected with the case, path,
pattern and actual tail. This catches contradictions such as a predicate requiring
an SDF delimiter at end-of-text while its cited example has a terminating newline.

This optional annotation is a consistency check, not a successful execution. It
does not count a historical artifact as new output or remove any normal/rejection,
source, entrypoint or coverage obligation. A pattern matching its example can still
fail on actual current output; the current Docker execution remains authoritative.
The validator does not automatically decide which arbitrary source file is a
representative positive example. Do not use an input fixture, partial excerpt or
success banner as the example.

2026-10-29 validation: four focused regressions and 626 offline tests passed (three
skipped), and all three prompt/schema self-checks passed. Saved run71 predicate
plus the new annotation was rejected against its historical SDF in
`E:\Users\27343\Docker\acceptance-openbabel-run71-20261029\positive-example-preflight-offline-replay.json`.
That replay used no model, Docker or business execution and did not modify the
original locked case or failed batch status. Development was isolated from the
simultaneously running run72; it is not retroactive run72 behavior.
