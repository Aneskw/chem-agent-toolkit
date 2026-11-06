# Minimum tool-skill content

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


Docker delivery: add runtime.json and one compact body section with image pull and execution
commands (identify the shell). Explain once that files under the mounted directory persist locally.
Use image reference {{image}} until host finalization; host replaces it with a verified registry digest.
Do not force saving the typical example as a particular filename. Later examples contain ordinary
tool code, without repeated Docker wrappers. State that a compatible local environment may run
the same code; detailed versions, dependencies and required external resources are in runtime.json.
The host generates runtime.json from the environment contract, then checks actual observations.
Do not put build provenance, review reports or execution tests in the Skill.


The single Docker section must include a noninteractive execution command (caller script or tool
CLI); an interactive shell/REPL alone is insufficient. Filenames and mounted directories are examples,
not compulsory user paths. Important scientific outputs require their definitions and units or
unitless conventions, not just column names. Semantic review enforces these material usage details.
runtime.json is host-owned. Environment findings return to environment preparation, not to the author.
