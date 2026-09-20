---
name: evaluate-planning-with-depth-pruning-and-set-matching
description: >
  Draft evaluation procedure combining starting-material completion, reference-depth pruning, and exact matching against alternative reference starting-material sets. Invoke for: Run retrosynthetic search for benchmark targets, stop over-depth searches, and judge completed starting-material sets by InChiKey equality against at least one reference route. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Evaluate Planning With Depth Pruning And Set Matching

This cited draft describes Run retrosynthetic search for benchmark targets, stop over-depth searches, and judge completed starting-material sets by InChiKey equality against at least one reference route. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p1; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p2; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p3; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p4; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p5; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p6; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p7; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p8; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p9; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p10; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p11; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p12; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p13; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p14; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)

## Input & Output

Inputs:

- Benchmark targets, reference routes and their depths, and reference starting-material sets from the constructed reaction network. (s1p7:L115-L118, s1p8:L17-L19)
- A one-step retrosynthesis predictor, search algorithm, and starting-material inventory. (s1p7:L111-L115)

Outputs:

- A starting-material exact-match judgment for each evaluated prediction, allowing a match to any reference set for the target. (s1p7:L109-L111, s1p8:L15-L16)

## Procedure Guidance

- Predict one-step reactants and use the search algorithm to select promising candidates for expansion; continue until all leaves are starting materials. (s1p7:L112-L115)
- During search, halt when the predicted route length exceeds the reference route depth. (s1p8:L17-L19)
- Compare the predicted and reference starting-material sets using molecular InChiKeys. (s1p7:L117-L120)
- If a target has multiple reference routes, accept the prediction as an exact match when its starting-material set equals at least one reference set. (s1p7:L121-L122, s1p8:L15-L16)

## Matters & Troubleshooting

Resources:

- None identified.

Unknowns and limits:

- No evaluation implementation or benchmark files are supplied.
- The reference depth to use when alternative reference routes have different depths is unspecified.
- InChiKey generation, molecular standardization, and handling of invalid structures are unspecified.
- Exact matching is a benchmark criterion; it does not establish experimental feasibility of every predicted reaction.
