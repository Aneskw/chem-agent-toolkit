Build a usable English skill from the candidate and actual research sources. Follow the
supplied minimum/packaging rules as semantic constraints, not a chapter template.
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
metadata_path JSON containing tests, issues and notes (arrays; empty is allowed). Checks should
exercise actual delivered examples/scripts, use source-grounded expected results and relevant
boundaries; do not invent a check simply to satisfy a template. Each test has name, argv, cwd,
expected_exit, stdout_contains and/or json_equals/artifacts, evidence, purpose, kind.
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
