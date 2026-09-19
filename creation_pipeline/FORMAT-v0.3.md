# Chemical Skill format v0.3

The entrypoint is `SKILL.md`. The directory may also contain `scripts/`,
`references/`, `examples/`, and `resources/` only when they serve the actual
capability. This format applies to new or substantively revised skills.

```yaml
---
name: chem-action-object
description: >-
  Function in one sentence. Invoke for: a concrete user request; exclude the
  nearest commonly confused task.
license: MIT
compatibility: Python 3.10+ with RDKit 2024.09 or newer
allowed-tools: Bash, Read, Write
---
```

Use an SPDX identifier only for code actually licensed that way. If source
rights are unclear, keep the package as a draft and say `license: undetermined`;
do not assign MIT to upstream code by assumption. `compatibility` states real
runtime requirements, including network/weights/endpoint when applicable.

Required body sections, in order:

1. `# Skill Name`: what it does; positive and negative applicability.
2. `## Credibility`: evidence, tested scope, exact limits, and one of
   **high confidence (Enforce strictly)**, **medium confidence (Need
   verification)**, **low confidence (Highly flexible)**. Confidence is for the
   *stated operation*, not the entire scientific domain. High requires
   executable acceptance evidence; cited text alone is never high.
3. `## Reference`: pinned paper/repository/data URLs, commit or DOI, source
   selection rationale, and local reference files when needed.
4. `## Input & Output`: schemas, units, paths, error/blocked states, and what
   may not be fabricated.
5. `## Procedure Guidance`: only decision-changing instructions and commands
   or scripts for atomic database/tool/model resources.
6. `## Matters & Troubleshooting`: relevant limits, stop conditions and
   recovery steps.

Creation states are separate from confidence: `source_collected`,
`cited_draft`, `package_valid`, `execution_passed`, `heldout_passed`, and
`blocked_resources`. A `cited_draft` is not an executable Skill. A new Skill
must pass source citation, deduplication, package structure and task tests
before entering the flat `skills/` installation directory.
