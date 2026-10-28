# Minimum tool-skill content

Produce an English SKILL.md with YAML name and description. Name identifies the capability;
description explains when the Agent should select it. Do not mechanically repeat that description.

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
   Mark external inputs, handoffs and alternative paths. Match the candidate's declared starting
   conditions; completeness is not exhaustive lifecycle/API coverage. Do not reduce this to a shortest call.
   Exact numerical output is optional; never fabricate an execution result.
5. **Result interpretation.** Explain how to use the output, tool-specific meaningful empty
   outcomes and failure signals. Predictions, measurements and scientific conclusions are distinct.

Write for a capable Agent. Omit introductory background, repeated caveats, obvious instructions,
line-by-line code translations and option catalogs without decision value. Keep important
pitfalls, defaults and data mappings. Compact prose, lists, tables and code are choices, not quotas.

One file is enough when adequate. Conditional references/scripts/assets are allowed; link their
purpose and use conditions. Keep normal-path correctness in the main file. No mandatory chapter
template, length target, file quota or coverage quotations. Build basis/review records stay outside
the pure package. This pipeline reviews sources and content; target tools/examples are not run.
