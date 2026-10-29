Build a usable English skill from the candidate and actual research sources. Follow the
supplied minimum/packaging rules as semantic constraints, not a chapter template.
Record metadata.entry naming the single executable entry of the delivery when it has
one: {"kind":"script","path":"<delivered .py or .sh>"} or
{"kind":"markdown_python","path":"SKILL.md","block_index":<n>} (block_index is 0-based:
the first python block is 0) (optionally with the
code_sha256 of that block). Declare it whenever the package ships scripts together with
documentation examples, or more than one script; without a declaration such a package
is refused as ambiguous instead of being guessed. The host validates the declaration
against the actual package and still requires the source association and the
independent review; the declaration is never evidence by itself.
The executable entry must be unambiguous. Either ship exactly one runnable script
under scripts/ (declare it), or keep exactly ONE complete, unindented ```python fenced
block in SKILL.md. Any additional illustrative snippet must use a non-python fence
(for example ```text) or live in references/; two or more python fences without an
entry declaration are refused, and an interactive prompt (>>>) or an indented fence is
not executable.
Record metadata.runtime_requirement with status required/not_required/unknown, a reason,
and citations [{source_id,path,quote}] quoting the registered original source exactly:
source_id is the source id (for example recap), path is that source's snapshot path
(for example document.py) and quote is verbatim source text. eN evidence locators are
for evidence references and claims only; they are not source ids.
Use not_required only for an explicitly supported non-executable capability, never
because dependencies are unavailable or no tests were written. Independent review
confirms this declaration. configured_requirement, if supplied, is reviewed as well.
Do not install software dependencies or run business checks on the host. After independent
content review, the host pipeline plans/builds Docker and runs locked checks against the
delivered entry. Author completion and content review do not establish runtime acceptance.
The candidate is a starting point: new evidence may justify narrowing/splitting scope or
changing support files. Source-supported splits may be recorded as metadata.additional_candidates
in the concise discovery format; they enter the queue after the current package passes review. Record meaningful scope changes in metadata.candidate_update with
source evidence and reason; never silently change the promise just to pass a check.

Keep the normal path, essential prerequisites, I/O and decision-changing caveats in SKILL.md.
Be minimal but sufficient. Do not force one file, multiple files, scripts or a particular length.
Use conditional references for long/uncommon details, scripts for necessary reusable processing,
and assets/examples for useful small inputs. Give actual imports/commands, source acquisition
and relevant versions. Explain empty/failure outcomes. Never copy a full upstream tree/weights,
invent scientific behavior, or depend on pipeline cache paths/sibling skills.

Read originals or obtain specific missing known resources with the helper when necessary.
Write actual files into output_directory. Use reliable native file tools or small UTF-8 chunks
(helper write); avoid long Windows shell patch arguments. Preserve fixture bytes. Binary support
files are allowed when justified and provenance is understood. Remove obsolete partial files.
Do not leave temporary files in the runtime package. Do not execute programs unless permitted.

Save progress as files, not one huge final response. When the package is complete, write
metadata_path JSON containing tests, issues and notes (arrays; empty is allowed).
runtime_requirement is an object {status: required|not_required|unknown, reason,
citations: [{source_id, path, quote}]}; quotes must be verbatim from the source and a
required status needs at least one citation. Checks should
exercise actual delivered examples/scripts, use source-grounded expected results and relevant
boundaries; do not invent a check simply to satisfy a template. Each test has name, argv, cwd,
expected_exit, stdout_contains and/or json_equals/artifacts, evidence, purpose, kind.
The optional candidate field is caller routing metadata. These are the supported
native-check fields (also supplied in execution_policy).
Unknown fields are rejected; planner case fields such as stdout_equals, input_files,
output_file, acceptance and timeout_seconds are not native-check fields. Preserve
each intended constraint through supported assertions or the self-contained check
program; never remove a user/source-backed assertion merely to pass validation.
Every check runs independently in a fresh container and output directory. No check
can read a previous check's /output files. Read packaged/source fixtures or prepare
inputs within the check; /input files are not implicit in native declarations.
For artifact or before/after validation, produce and validate its own artifact in
that check. Preserve all assertions, fixture bytes and line endings. Compute hashes
from actual bytes, not reconstructed/newline-normalized text. Supplementary checks
do not replace a direct business entry check.
json_equals is an OBJECT mapping a dotted field/index path into the parsed stdout JSON to
its exact expected value, for example {"leaves": ["*CCO"]}, {"count": 0} or {"0": "*CCC"}
for a top-level JSON array. It is never the whole JSON value: an array or scalar there is
rejected. Use stdout_contains for substring assertions.
A check needs a result assertion, not an exit code alone: every check, including a
rejection check, must assert observable output (stdout_contains, json_equals or a
nonempty artifact). "expected_exit only" is rejected by the delivery validator and
counts as a failed author turn.
When you document a rejection, the delivered code must implement it: never rely on an
upstream parser to reject a value. In particular an empty or whitespace-only input is
often accepted by a parser as an empty value, so check it explicitly and exit with the
documented code. A rejection case must use an input that actually triggers the
documented behaviour.
evidence is one registered source locator ID string (for example e1), not an array;
explain the inspected source passage and expected behavior in purpose.
{python},{package},{run},{source:ID} are check-only macros. Explicitly group/select continuous
examples; do not execute mutually exclusive, illustrative or external-input snippets blindly.
Lack of a trustworthy oracle or environment is recorded, not hidden by printing desired output.
User-configured assertions remain unchanged. If source proves an earlier generated oracle wrong,
record the correction for independent-context review, not output matching.

issues entries need id, description, blocking, resolution. Blocking means a genuine content or
essential evidence defect, not merely an absent local GPU/dependency. notes record unverified
execution and other nonduplicated limitations. A written test is not execution evidence.
Use helper finish with run, output_directory, delivery_token and metadata_path. It snapshots
file hashes and metadata; this is the durable completion receipt. Final reply is only
{completed,summary}, never file contents or coverage quotations. Repair only affected work.
If the helper executable cannot start, request host finalization in summary and return
completed=true only after all intended files and metadata are fully written. The host
validates them with the same finish routine; the files alone never establish completion
or acceptance. Unfinished files require completed=false.
