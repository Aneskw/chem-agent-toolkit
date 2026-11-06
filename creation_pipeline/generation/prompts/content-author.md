Write a usable English Skill from this candidate and inspected sources. The supplied minimum
and packaging standards define the content; they are not a mandatory chapter template.

Write for an execution Agent that receives only the final package: it has neither this build
conversation nor the source workspace. Make essential external tools/resources obtainable through
explicit official repository/package/service/setup links and source-supported versions. Do not
leave unbound references such as "the repository" or build-only paths. A compact setup entry is
better than a dependency-tree copy; do not guess versions or repeat build restrictions in the Skill.

Choose a representative normal path consistent with the candidate's starting inputs and promised
result. Integrate real invocation code with necessary workflow explanations and output access.
Complete means no essential gap in that path, not every lifecycle phase or API option. Make
alternatives/external inputs/handoffs explicit. Organize preparation, invocation and result handling
so each can be located, with a body title and short sections where useful. Group related fields or
options in compact keys/lists/tables rather than mixing their meanings, defaults and failure behavior
in one paragraph. Keep the example and its necessary explanations connected. Exact numeric output
is optional, and fabricated execution results are forbidden.

Keep content that changes selection, preparation, invocation or output interpretation. Preserve
high-value defaults, mappings, destructive/state-changing behavior and boundaries; remove generic
background, obvious explanations and repetition. Use the smallest adequate package and references
only for useful conditional detail. Apply the same usefulness test to citations: retain official
setup/interface links and method references needed in use; put internal resource IDs, benchmark
graders and paper-to-Skill provenance in basis. Distinguish example choices from publication facts
where they affect the operation, without adding an unrelated publication recap or reproduction
disclaimer to a generic tool workflow. Source-supported code adaptations/compositions are allowed;
new glue must not invent research behavior. Independently inspect uncertain behavior in originals.

On repair, first verify feedback against the originals. If a finding is mistaken, retain the
correct behavior and supply a concise source-backed rebuttal in basis/issues rather than inventing
a workaround. Resolve real defects and affected relationships. Prefer replacing an ambiguous
passage over appending another warning. Check the repaired path for new inconsistency/redundancy;
do not silently narrow the capability merely to obtain approval.

Write actual files to output_directory and metadata_path JSON with required basis and optional
issues/notes arrays. Each basis item has location (delivered file/section), claim, source (registered
eN or unique source-id/path), locator (inspected function/page/passage), origin (upstream,
sourced_adaptation, or glue). Group factual justification by meaningful content blocks, not every
line of ordinary syntax. This writing basis stays outside the Skill and is not private reasoning.
issues have id, description, blocking and resolution. Do not put execution tests or proof files in the package.

Use helper finish with run, package=output_directory, token=delivery_token and metadata=metadata_path.
Its durable receipt completes delivery; return only completed/summary. Source-backed scope changes
may use candidate_update: changed task/scope/entrypoint/construction fields plus reason/evidence.
additional_candidates use the discovery schema.


Docker use belongs in one compact section: provide a pull command and a noninteractive command
running caller code or a tool command, using {{image}}, and identify the shell. A shell/REPL may
be optional but must not be the only execution path. Filenames and mount directories are adaptable
examples. Explain once that mounted outputs persist locally, and link runtime.json for compatible
local execution requirements. Do not duplicate Docker commands in later tool examples.
The host owns runtime.json. If its requirements are wrong, report the exact environment finding in
issues rather than editing it or copying a conflicting prerequisite into the prose. Do not transfer
verifier-only fixture paths, harness restrictions or build notes into end-user instructions.
For material output fields, give definitions and units/conventions supported by sources (including
whether a quantity is unitless, an index base, or an area/mass convention). No full API catalog.
