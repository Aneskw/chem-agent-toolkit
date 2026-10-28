---
name: identify-reaction-centers-and-extract-synthons
description: "Select a scored product bond and extract graph components, with explicit no-center fallback and distinction between graph synthons and valid reactants."
license: undetermined
---


# Select a reaction center and extract synthons

Use after a trained center predictor has scored existing product bonds. Input: product graph with stable atom IDs, bond scores, and a task/model-selected threshold. Output: selected bond ID and connected graph components, or the unchanged graph when no score exceeds the threshold. This Skill does not supply the trained R-GCN scorer.

## Usage

1. Check that score endpoints refer to the same atom ordering and existing edges in the product graph. Reject missing/nonfinite scores; do not confuse logits with probabilities.
2. For the single-center path, choose the highest-scoring bond strictly above the threshold. Resolve equal scores deterministically by stable bond ID. No qualifying bond means the whole product remains one synthon.
3. Copy the graph, remove that edge, and find connected components. Preserve atom IDs, element/charge/stereo annotations and remaining bond types. Cutting a ring bond may leave a connected graph; do not force two components.
4. Hand these graph synthons to the downstream model's own encoding. Bond deletion can leave chemically incomplete fragments; do not silently add groups or sanitize them into unrelated molecules.

Illustration: graph edges `(0,1),(1,2),(2,3)` with chosen bond `(1,2)` gives atom sets `{0,1}` and `{2,3}`. This describes graph partitioning, not chemically valid reactant completion.

For top-k diversity, retain which cut produced which hypothesis. Do not silently interpret several high-scoring bonds as simultaneous cuts; that requires the model's explicit multi-center convention. Numerical thresholds are model/task inputs, not universal constants.

Source: [G2Gs reaction-center and synthon procedure](https://arxiv.org/abs/2003.12725).
