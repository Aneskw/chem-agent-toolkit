---
name: attach-semi-template-residuals
description: >
  Draft procedure for converting a synthon into a reactant by applying a semi-template under a reaction-center matching constraint. Invoke for: Map semi-template atoms and bonds, match its left side to the synthon with the reaction center inside the matched region, and replace the left side with the right side. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Attach Semi Template Residuals

This cited draft describes Map semi-template atoms and bonds, match its left side to the synthon with the reaction center inside the matched region, and replace the left side with the right side. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://arxiv.org/pdf/2202.08205.pdf (source s1p1; SHA-256 82f45d345e57976e82046ceebc6c35a5e48e96bb2e40b1248aeade653532e49e)
- paper: https://arxiv.org/pdf/2202.08205.pdf (source s1p2; SHA-256 82f45d345e57976e82046ceebc6c35a5e48e96bb2e40b1248aeade653532e49e)
- paper: https://arxiv.org/pdf/2202.08205.pdf (source s1p3; SHA-256 82f45d345e57976e82046ceebc6c35a5e48e96bb2e40b1248aeade653532e49e)
- paper: https://arxiv.org/pdf/2202.08205.pdf (source s1p4; SHA-256 82f45d345e57976e82046ceebc6c35a5e48e96bb2e40b1248aeade653532e49e)
- paper: https://arxiv.org/pdf/2202.08205.pdf (source s1p5; SHA-256 82f45d345e57976e82046ceebc6c35a5e48e96bb2e40b1248aeade653532e49e)
- paper: https://arxiv.org/pdf/2202.08205.pdf (source s1p6; SHA-256 82f45d345e57976e82046ceebc6c35a5e48e96bb2e40b1248aeade653532e49e)
- paper: https://arxiv.org/pdf/2202.08205.pdf (source s1p7; SHA-256 82f45d345e57976e82046ceebc6c35a5e48e96bb2e40b1248aeade653532e49e)
- paper: https://arxiv.org/pdf/2202.08205.pdf (source s1p8; SHA-256 82f45d345e57976e82046ceebc6c35a5e48e96bb2e40b1248aeade653532e49e)
- paper: https://arxiv.org/pdf/2202.08205.pdf (source s1p9; SHA-256 82f45d345e57976e82046ceebc6c35a5e48e96bb2e40b1248aeade653532e49e)
- paper: https://arxiv.org/pdf/2202.08205.pdf (source s1p10; SHA-256 82f45d345e57976e82046ceebc6c35a5e48e96bb2e40b1248aeade653532e49e)
- paper: https://arxiv.org/pdf/2202.08205.pdf (source s1p11; SHA-256 82f45d345e57976e82046ceebc6c35a5e48e96bb2e40b1248aeade653532e49e)
- paper: https://arxiv.org/pdf/2202.08205.pdf (source s1p12; SHA-256 82f45d345e57976e82046ceebc6c35a5e48e96bb2e40b1248aeade653532e49e)
- paper: https://arxiv.org/pdf/2202.08205.pdf (source s1p13; SHA-256 82f45d345e57976e82046ceebc6c35a5e48e96bb2e40b1248aeade653532e49e)

## Input & Output

Inputs:

- A synthon, its reaction center, and a semi-template. (s1p12:L14-L14)

Outputs:

- A candidate reactant obtained by applying the semi-template to the synthon. (s1p12:L15-L15)

## Procedure Guidance

- Once the reaction center, synthon, and corresponding semi-template are available, map atoms within the template and then map its bonds. (s1p6:L12-L14, s1p12:L4-L4, s1p12:L10-L10)
- Match the left template to the synthon, accepting only matches whose matching area contains the reaction center. (s1p12:L5-L6)
- For a qualifying match, remove the left template and add the right template to produce the candidate reactant. (s1p12:L7-L8, s1p12:L15-L15)

## Matters & Troubleshooting

Resources:

- None identified.

Unknowns and limits:

- Table 7 refers to detailed open-source implementation, but provides no file path; no repository files are supplied.
- Atom and bond mapping details, tie-breaking among multiple qualifying matches, and behavior when no match qualifies are not specified.
- Explicit post-attachment chemical validation and error-handling rules are not supplied.
