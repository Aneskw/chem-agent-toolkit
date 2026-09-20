---
name: correct-and-filter-semi-template-pairs
description: >
  Draft procedure for refining semi-template predictions using information from paired synthons and rejecting pairs unsupported by the training distribution. Invoke for: Predict semi-template classes for paired synthons, jointly correct their predictions, and discard pairs with zero training-set prior probability. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Correct And Filter Semi Template Pairs

This cited draft describes Predict semi-template classes for paired synthons, jointly correct their predictions, and discard pairs with zero training-set prior probability. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

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

- A synthon, its dual synthon from the same product, the product, and the predicted reaction atom set. (s1p5:L55-L58)
- Semi-template classes consisting of the top 150 templates and one uncovered-class label. (s1p5:L52-L54)
- The training-set prior distribution of predicted semi-template pairs. (s1p6:L9-L11)

Outputs:

- Refined semi-template predictions, with zero-prior pairs discarded. (s1p5:L88-L91, s1p6:L10-L11)

## Procedure Guidance

- Extract atom features with stacked DRGATs and concatenate mean-pooled features for reaction-center atoms, the synthon, its dual synthon, and the product. (s1p5:L59-L63, s1p5:L64-L68)
- Use the initial softmax classifier to predict a semi-template class, then concatenate its learnable class embedding with the synthon representation. (s1p5:L69-L72, s1p5:L85-L88)
- For paired synthons, process their augmented representations jointly with a multi-layer transformer and classify the refined representations. (s1p5:L81-L85, s1p5:L95-L99)
- Check each predicted pair against the training-set prior distribution; discard it if its prior probability is zero. (s1p6:L9-L11)

## Matters & Troubleshooting

Resources:

- external_asset: https://github.com/DeepGraphLearning/torchdrug/ — Referenced framework and G2G implementation underlying the paper's implementation settings; the supplied bundle contains no implementation files.

Unknowns and limits:

- The bundle supplies no SemiRetro implementation files, trained weights, or concrete template vocabulary.
- Transformer depth, attention-head count, and construction details for the pair prior are not specified.
- Handling of a single synthon, more than two synthons, uncovered-class predictions, or rejection of every candidate pair is not specified.
