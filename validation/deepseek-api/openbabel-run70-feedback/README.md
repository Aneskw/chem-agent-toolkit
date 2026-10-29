# run70 observed test-contract failures

The historical batch prepared on its FIRST planner call, built a thin image and hit
the run69 shared dependency environment. It still FAILED: 5/11 records passed. No
historical result establishes current acceptance; rerun all five obligation groups.

The original input.smi is CCO followed by CRLF (5 bytes), NOT LF (4 bytes). Its original
hash in the author checks was correct. The plan reconstructed an LF fixture and thus
the comparison failed. The host planner material projection now preserves raw UTF-8
newlines. Copy the exact original fixture, including CRLF, when using input_files.
Native checks can instead read the byte-identical packaged/source fixture. Never
replace the expected original hash just to make a changed fixture pass.

Every native declaration becomes an INDEPENDENT container with a fresh /output.
It has no implicit /input fixtures and no prior check artifacts. A standalone
retained-structure check must create its own converted file before parsing it.
A preservation check must perform before/after operations within its own check.
Use {package}/examples/input.smi or {source:existing_openbabel}/examples/input.smi,
not an unprovided /input/input.smi. Inline code macros are translated too.
Keep all five obligation groups: actual obabel/version and baseline; normal direct
conversion; unknown format rejection; retained SDF structure; input/entry preservation.
Do not remove tests/assertions; repair setup and state assumptions.

The normal plan case again incorrectly used kind=json on output_file=ethanol.sdf.
That file is SDF, not the JSON stdout report. Use acceptance.assertion.kind=text_regex
with a source-grounded full-match pattern for its structure; check stdout JSON
separately using stdout_contains/json_equals. A separate supplementary structure
validator may run its own conversion and exact parser. No cross-case /output sharing.
The required unknown-format fixture remains nonexistent_format_xyz, exit2/ok:false.
The original wrapper must remain byte-identical, including its actual empty-output
limitation. Keep source-correct behavior; do not invent rejection from flag presence.
