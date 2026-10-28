# Minimum tool-skill content

Produce an English SKILL.md with YAML name and description. The name identifies the capability;
description explains when the Agent should select it. Do not repeat that description mechanically.

Every skill must convey these four kinds of information, with flexible organization and headings:

1. **Capability and necessary boundary.** Identify the tool and coherent capability. State limits
   only when they change tool selection, execution or result meaning.
2. **Inputs and outputs.** Required inputs and principal results; formats, units, shapes, indices,
   paths or mutation only when needed. For many fields use compact real keys/tables. Do not copy
   the full API or repeat obvious example details.
3. **Usable invocation.** A complete minimal normal path using real imports/commands and result
   access. State essential dependencies/resources before needed. Explicitly identify continuous
   steps, independent alternatives and external inputs when ambiguity would affect use.
4. **Result interpretation/checks.** Explain the minimum tool-specific usable-result checks,
   meaningful empty outcomes and failure signals. Execution is not scientific validity.

One file is enough when adequate. Conditional references/scripts/examples/resources/assets are allowed, but only inside those role directories (`SKILL.md` is the sole top-level file; licence and notice text belongs in `references/`). Link them with their purpose and when they are needed. Keep normal-path correctness in the main file.
No mandatory chapter template, length target, file quota or author coverage quotations.
Add content only when it helps selection, correct execution or interpretation. Omit generic
boilerplate, build logs, internal evidence IDs and verification verdicts from runtime instructions.
