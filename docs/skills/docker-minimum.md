# Minimum tool-skill content

## Tool-workflow eligibility

Every candidate must teach a source-supported use of actual software: a library, CLI,
script/module, service or documented executable software workflow. Connect realistic starting
inputs through real invocation to output access and interpretation. Laboratory recipes,
equipment names, standalone theory/mechanism explanations and paper summaries are not eligible.
Do not manufacture a trivial script to turn such content into a tool skill.

Using existing software in research can be valuable; a new tool, author repository, open source,
local installation or complete paper reproduction is not required. Licensed software can qualify
when acquisition, prerequisites and the actual interface can be established. Missing use details
in a paper trigger scoped supplementation for a promising capability, not immediate omission.
If evidence remains insufficient, retain a concrete gap rather than inventing an interface.

## Target software version

For reusable capabilities, first check official current stable releases, maintenance/support and
relevant documentation. Prefer a maintained, obtainable version compatible with the task and
declared environment. A paper's publication/citation date or cited software version is provenance,
not an automatic requirement to package that historical interface. Age alone does not establish
obsolescence; neither the highest version number nor the development branch is automatically best.

Use a historical release or specially constrained commit when an explicit reproduction requirement, existing artifacts,
format/platform constraint or source-supported scientific-method dependency requires it. An easier
old manual alone is not justification. If current usage cannot be established, record the gap;
do not silently fall back to an obsolete workflow and present it as the general current solution.
Pin the chosen release/commit as appropriate, including current supported releases.

Preserve the supported scientific method while verifying the chosen version's actual interfaces,
defaults, units, input/output behavior and dependencies. Do not assume numerical equivalence or
invent a migration. Record the target version, concise selection reason and original-versus-target
distinction in existing construction/basis/evidence fields. Runtime instructions need the chosen
version and operational boundaries, not a version-survey essay or build-only provenance.


Produce an English SKILL.md with YAML name and description and a descriptive body title.
Name identifies the capability; description explains when the Agent should select it.
Do not mechanically repeat that description.

The execution Agent receives only the final package, not the build conversation or source
workspace. Essential external tools/resources need explicit official acquisition/setup entrypoints
and source-supported versions where relevant; build records do not substitute for usage information.

Every skill must convey these five kinds of information, with flexible organization and headings:

1. **Capability and selection.** Identify the tool and coherent capability. State boundaries
   only when they change selection, execution or result meaning.
2. **Environment and prerequisites.** Give the source-supported tool version/commit, installation
   command or official setup entry, and necessary external resources/hardware/credentials.
   Use the concise Docker section and runtime.json contract below. Do not invent versions, duplicate a dependency tree or add generic warnings.
3. **Inputs and outputs.** Required inputs, preparation and principal results; formats, units,
   shapes, indices, paths or mutation when material. Prefer compact real keys, tables or small
   structures to scattered prose. Do not copy the full API or repeat obvious example details.
4. **Representative Usage.** Integrate a typical complete example with its necessary workflow
   explanations. Use real imports/commands and output access, creating an adaptable template.
   Mark external inputs, handoffs and alternative paths. Match the candidate's declared starting
   conditions; completeness is not exhaustive lifecycle/API coverage. Do not reduce this to a shortest call.
   Exact numerical output is optional; never fabricate an execution result.
5. **Result interpretation.** Explain how to use the output, tool-specific meaningful empty
   outcomes and failure signals. Predictions, measurements and scientific conclusions are distinct.

Organize content by its role in use. Use short descriptive sections when preparation, invocation
and result handling need separate lookup; a very short Skill may use a few connected paragraphs.
Present groups of fields/options as compact keys, lists or tables with material meanings and
units. Keep explanations beside the relevant example; avoid both dense mixed-purpose paragraphs
and line-by-line translations. No fixed section names or required table format.

Keep information that changes selection, preparation, invocation or interpretation. Runtime
references should help obtain a resource, resolve an interface or apply a method. Internal source
IDs, benchmark/grader links and accounts of why a paper inspired the Skill belong in build records.
Include publication-specific settings only when they affect the declared workflow; a generic tool
example need not end with a paper-reproduction disclaimer. Never present illustrative settings as
published facts. Omit generic background, repeated caveats and unrelated option catalogs.

SKILL.md and runtime.json are required. Conditional references/scripts/assets are allowed; link their
purpose and use conditions. Keep normal-path correctness in the main file. No mandatory chapter
template, length target, file quota or coverage quotations. Build basis/review records stay outside
the pure package. Semantic review does not execute target tools; a later stage selectively validates necessary custom logic.


Docker delivery: the author uses the supplied [runtime template](runtime-template.md) once, before
business examples. Replace the task command with real invocation; retain {{image}} for host
finalization. The host owns runtime.json. The section is included in full semantic review; it is
not injected after approval. Ordinary code can run locally with a compatible environment.
Important output quantities need source-supported meanings and units/conventions. No API catalog.
