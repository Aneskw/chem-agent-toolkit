---
name: tool-task-name
description: >
  State the task and the requests or conditions that should trigger this skill.
---

# Skill Name

Identify the tool and the task it performs. State only the capability boundaries that affect tool selection or result interpretation. Avoid repeating the description.

## Input & Output

Describe required inputs and primary outputs. Include formats, units, index
conventions, path resolution, or in-place changes only when needed for correct use.
Explain optional parameters only when they affect common calls or are easy to misuse.
Do not reproduce the full API reference or repeat unambiguous details from the example.

## Usage

Provide one complete, minimal example using the real API or command. Include necessary imports, input preparation, invocation, and result access.

Explain additional steps or branches only when the example cannot express them clearly.

State special prerequisites only when required: dependencies, version constraints,
credentials, remote connections, resources, or working directories. Put them before the call that needs them; omit a separate environment section when unnecessary.

If supporting files are needed, link each file with a specific condition for reading it. Keep essential correctness requirements in this main file.

## Result Checks

State the tool-specific minimum checks for a usable result. Explain empty results or failure signals and the necessary response when relevant.

Distinguish successful execution from valid output or a supported scientific conclusion where these differ.

These four information requirements are mandatory; their headings and length are flexible. Merge sections when this improves clarity. Add content only when it changes tool selection, correct execution, or result interpretation. Omit empty sections, generic advice, and duplicated instructions. Remove these authoring instructions when producing an actual skill.
