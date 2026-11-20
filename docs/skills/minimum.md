# Minimum tool-skill content

Produce an English SKILL.md with YAML name and description and a descriptive body title.
Name identifies the capability; description explains when the Agent should select it.
Do not mechanically repeat that description.

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

## Capability scope and value

Define a reusable task or coherent task family by its starting inputs and useful result. Identify the non-obvious
interface choices, scientific conditions or data handoffs the guidance resolves. This is a
source-supported value hypothesis, not measured Agent benefit or a requirement for complexity.

Keep necessary preparation, invocation and result handling together. Changes to example data,
temperature, file count or configurable settings do not alone define separate capabilities.
Related uses can share a common core with modes selected by supplied data, environment or analysis
need. A mode being independently usable is not sufficient reason to split it into another package.
Keep separate packages when different scientific purposes, input/result meanings or incompatible
prerequisites make a common entrypoint confusing. Shared tool names, APIs or sequential steps alone
do not justify merging. A coherent task may use several tools. Check plausible input variation and
consequential promised modes without requiring every variant or an entire study.

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

## Required usage information

The execution Agent receives only the final package, not the build conversation or source
workspace. Essential external tools/resources need explicit official acquisition/setup entrypoints
and source-supported versions where relevant; build records do not substitute for usage information.

Every skill must convey these five kinds of information, with flexible organization and headings:

1. **Capability and selection.** Identify the tool and coherent capability. State boundaries
   only when they change selection, execution or result meaning.
2. **Environment and prerequisites.** Give the source-supported tool version/commit, installation
   command or official setup entry, and necessary external resources/hardware/credentials.
   Keep this in the body. Do not invent versions, duplicate a dependency tree or add generic warnings.
3. **Inputs and outputs.** Required inputs, preparation and principal results; formats, units,
   shapes, indices, paths or mutation when material. Prefer compact real keys, tables or small
   structures to scattered prose. Do not copy the full API or repeat obvious example details.
4. **Representative Usage.** Integrate a typical complete example with its necessary workflow
   explanations. Use real imports/commands and output access, creating an adaptable template.
   Distinguish replaceable example values from scientific requirements. Connect necessary data
   transformations and handoffs within the declared scope; identify genuinely external preparation.
   Completeness is not exhaustive lifecycle/API coverage. Do not reduce this to a shortest call.
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

One file is enough when adequate. Conditional references/scripts/assets are allowed; link their
purpose and use conditions. Keep normal-path correctness in the main file. No mandatory chapter
template, length target, file quota or coverage quotations. Build basis/review records stay outside
the pure package. This pipeline reviews sources and content; target tools/examples are not run.
