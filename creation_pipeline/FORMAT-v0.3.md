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

## Research admission gate

The YAML shape is necessary but insufficient. Treat a database query, wrapper,
scorer or missing-resource preflight as an **atomic resource package**, even if
its entry file is named `SKILL.md`. Promote a candidate to a research-level
chemical skill only after all of these are recorded:

1. A supplied primary document provides a cited chemical method or evaluation
   rationale, and a pinned implementation or data source shows how it is
   operationalized. A pinned repository implementation can establish
   implementation behavior; repository README text alone is not authoritative
   evidence for a method decision. The pipeline is not restricted to the
   literature tables bundled with this repository.
2. The procedure contains at least one explicit branch that changes what the
   agent does depending on task goal, evidence, uncertainty, or failure. It
   cannot be only a command invocation, input schema or checklist.
3. Its relation to existing packages is reviewed: reuse atomic resources,
   split unrelated operations and merge duplicate decision policies.
4. In matched held-out tasks, compare no additional material, the exact source
   text used for extraction, and the generated Skill. Predeclare correctness,
   scope failures and token measures. A pass on a packaged script alone is not
   evidence of a Skill effect.

Until step 4, label the document `procedural_skill_candidate`; do not count it
as a validated skill or claim that it improves agent reasoning.
