---
name: train-downstream-precursor-generation-on-upstream-prediction-errors
description: >-
  Align intermediate fragments with target reactants, augment sequence ordering, and expose a downstream generator to upstream training errors while keeping end-to-end evaluation separate from evaluation with reference intermediates. Invoke for: choosing a paper-backed procedure when task evidence or constraints change; do not treat this draft as experimentally validated.
license: undetermined
compatibility: Research draft; inspect source-specific dependencies and data before use
allowed-tools: Read
---

# Train Downstream Precursor Generation On Upstream Prediction Errors

Align intermediate fragments with target reactants, augment sequence ordering, and expose a downstream generator to upstream training errors while keeping end-to-end evaluation separate from evaluation with reference intermediates. Use only for the task settings supported by the cited papers and pinned implementations. Do not use it as a generic reaction predictor or assume a successful agent effect.

## Credibility

**Low confidence (Highly flexible)** as an abstracted agent procedure: source locations were checked, while semantic merging and agent utility require human review. Research state: `procedural_skill_candidate`.

## Reference

- `74LHJIVM/train-reactant-generation-to-correct-synthon-errors`: RetroXpert: Decompose Retrosynthesis Prediction like a Chemist (https://arxiv.org/pdf/2011.02893v1); implementation https://github.com/uta-smile/RetroXpert at `321cc3daf2f3a7ac9ab5b37dde5b666b338e1ed5`. Validated source locations: s1p16:L36-L39, s1p5:L35-L36, s1p5:L50-L51, s1p6:L1-L5, s1p6:L18-L19, s1p6:L19-L20, s1p6:L21-L22, s1p6:L28-L29, s1p6:L4-L5, s1p6:L9-L11, s1p7:L54-L55, s1p7:L62-L64, s1p7:L7-L9, s2:L120-L121, s2:L157-L159, s4:L183-L189, s4:L328-L331, s8:L132-L134, s8:L161-L162, s8:L164-L167, s8:L170-L175, s8:L190-L193, s8:L192-L193, s8:L196-L199.

## Input & Output

Inputs depend on the chosen variant:

- Training products, ground-truth synthons and reactants, plus EGAT predictions on the training set.

Expected outputs:

- A reactant-generation model intended to correct reaction-center errors, with end-to-end predictions evaluated against reference reactants.
- An error-augmented training source/target pair, retaining the ordinary augmented samples and appending failed-prediction samples.

## Procedure Guidance

- **When** Constructing ordinary product-plus-synthon training pairs. **Do** Align reactants to synthons by shared mapped atoms and add reversed synthon/reactant ordering under the chosen source's eligibility condition. **Avoid** Silently equate the paper's multi-synthon condition with the repository's condition that skips single-reactant examples. (supported by 74LHJIVM/train-reactant-generation-to-correct-synthon-errors).
- **When** Upstream reaction-center predictions on training data fail the guided center check. **Do** Realign reference reactants to the predicted synthons, remove mapping numbers, tokenize, and append these examples without reversal to the ordinary augmented corpus; use [RXN_0] for unknown reaction types in the described repository flow. **Avoid** Include successful predictions in the error-only additions or claim that producing augmented files proves the trainer consumed them. (supported by 74LHJIVM/train-reactant-generation-to-correct-synthon-errors).
- **When** Evaluating the complete retrosynthesis pipeline. **Do** Send every predicted synthon set to the reactant generator, including sets from incorrect centers, and assess top-N canonical reactant-set agreement. Reserve reference synthons for isolated generator evaluation. **Avoid** Filter out incorrect centers or report evaluation with reference synthons as end-to-end performance. (supported by 74LHJIVM/train-reactant-generation-to-correct-synthon-errors).

Deduplication recommendation: `keep_separate`; This capability governs training-data construction and stage-aware evaluation. It is distinct from reaction-center prediction, inference-only retrosynthesis, and standalone candidate scoring. Their pipeline relationships do not establish duplication.

## Matters & Troubleshooting

- Successful training, error correction, and benefit on new data are not established.
- Original augmentation gains require qualification because of the repository's information-leak correction.
- Consumption of error-augmented files by training is unverified; the supplied inventory also differs from the README's preprocessing script name.
- Exact-match evaluation does not establish chemical feasibility and may reject valid alternative reactants.
- Catalog overlap note for retroxpert-evaluate-bond-disconnection: related upstream evaluation, not downstream training augmentation.
- Catalog overlap note for chem-retro-candidate-evaluation: overlapping final exact-match scoring, not the training capability.
- Catalog overlap note for retroprime-two-stage-retrosynthesis: related staged inference goal with a different mechanism and scope.
- Catalog comparisons use supplied package descriptions only; full package behavior must be inspected before any duplicate or variant consolidation.
- All deduplication actions are proposals for human review, not authorization for automatic semantic merging.
- Evidence is limited to supplied summaries and evidence identifiers; unavailable source text was not inspected.
- Do not count this candidate as an executable or agent-validated skill.
