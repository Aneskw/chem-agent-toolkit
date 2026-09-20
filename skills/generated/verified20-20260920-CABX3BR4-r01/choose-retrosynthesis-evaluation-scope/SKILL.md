---
name: choose-retrosynthesis-evaluation-scope
description: >
  Draft evaluation policy for deciding when to emphasize largest-reactant recovery and multiple suggestions, while retaining full-reaction metrics for comparison. Invoke for: Select evaluation scope according to whether the task concerns principal molecular transformations or exact reactant recovery, and interpret exact-match metrics in light of reagent ambiguity. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Choose Retrosynthesis Evaluation Scope

This cited draft describes Select evaluation scope according to whether the task concerns principal molecular transformations or exact reactant recovery, and interpret exact-match metrics in light of reagent ambiguity. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://www.nature.com/articles/s41467-020-19266-y.pdf (source s1p1; SHA-256 1f073de5ac5ce97182dd8eac2aa73960b25e29a3f4a3e86c9626a575eac0f8d8)
- paper: https://www.nature.com/articles/s41467-020-19266-y.pdf (source s1p2; SHA-256 1f073de5ac5ce97182dd8eac2aa73960b25e29a3f4a3e86c9626a575eac0f8d8)
- paper: https://www.nature.com/articles/s41467-020-19266-y.pdf (source s1p3; SHA-256 1f073de5ac5ce97182dd8eac2aa73960b25e29a3f4a3e86c9626a575eac0f8d8)
- paper: https://www.nature.com/articles/s41467-020-19266-y.pdf (source s1p4; SHA-256 1f073de5ac5ce97182dd8eac2aa73960b25e29a3f4a3e86c9626a575eac0f8d8)
- paper: https://www.nature.com/articles/s41467-020-19266-y.pdf (source s1p5; SHA-256 1f073de5ac5ce97182dd8eac2aa73960b25e29a3f4a3e86c9626a575eac0f8d8)
- paper: https://www.nature.com/articles/s41467-020-19266-y.pdf (source s1p6; SHA-256 1f073de5ac5ce97182dd8eac2aa73960b25e29a3f4a3e86c9626a575eac0f8d8)
- paper: https://www.nature.com/articles/s41467-020-19266-y.pdf (source s1p7; SHA-256 1f073de5ac5ce97182dd8eac2aa73960b25e29a3f4a3e86c9626a575eac0f8d8)
- paper: https://www.nature.com/articles/s41467-020-19266-y.pdf (source s1p8; SHA-256 1f073de5ac5ce97182dd8eac2aa73960b25e29a3f4a3e86c9626a575eac0f8d8)
- paper: https://www.nature.com/articles/s41467-020-19266-y.pdf (source s1p9; SHA-256 1f073de5ac5ce97182dd8eac2aa73960b25e29a3f4a3e86c9626a575eac0f8d8)
- paper: https://www.nature.com/articles/s41467-020-19266-y.pdf (source s1p10; SHA-256 1f073de5ac5ce97182dd8eac2aa73960b25e29a3f4a3e86c9626a575eac0f8d8)
- paper: https://www.nature.com/articles/s41467-020-19266-y.pdf (source s1p11; SHA-256 1f073de5ac5ce97182dd8eac2aa73960b25e29a3f4a3e86c9626a575eac0f8d8)

## Input & Output

Inputs:

- Ranked retrosynthesis predictions and corresponding target molecules. (s1p7:L26-L27)
- The evaluation goal and whether reference reactions contain conditions, solvents, salts, or other components that do not form the product. (s1p7:L3-L6, s1p6:L66-L68)

Outputs:

- An evaluation reporting MaxFrag top-n for principal transformations and traditional top-n for comparability, with explicit limitations concerning alternative valid reactants. (s1p7:L41-L45, s1p7:L44-L45)

## Procedure Guidance

- When evaluating the principal transformation rather than detailed reaction conditions, emphasize recovery of the largest reactant using MaxFrag. (s1p6:L61-L64, s1p6:L69-L70)
- If reference reactions include nonparticipating reagents or conditions, use MaxFrag to reduce their influence on evaluation. (s1p7:L19-L23)
- Compare predicted and target molecules by exact match. For MaxFrag, report the percentage of correctly predicted largest fragments. (s1p7:L26-L27, s1p6:L108-L108)
- When multiple starting materials could produce the same product, examine top-n rather than only top-1. Treat this as partial mitigation: neither exact-match metric recognizes every chemically valid alternative. (s1p7:L31-L36)
- Also report traditional top-n scores when comparison with prior studies is required. (s1p7:L44-L45)

## Matters & Troubleshooting

Resources:

- None identified.

Unknowns and limits:

- The supplied text does not specify the exact fragment-size definition or how ties between largest fragments are resolved.
- No evaluation implementation or callable scoring API is supplied.
- Exact-match success does not establish experimental feasibility, reaction yield, or completeness of a multistep route.
