---
name: predict-reactants-through-reaction-centers
description: "Guide a configured RetroXpert-style EGAT/RGN pipeline through center selection, synthon encoding and end-to-end evaluation without confusing oracle centers with predictions."
license: undetermined
---


# Reaction-center-to-reactant pipeline guidance

Use with an already configured EGAT center predictor, its matching RGN decoder/tokenizer, and their training-compatible chemistry preprocessing. Required input: product graph/SMILES, optional known reaction class, and those model artifacts/interfaces. This Skill organizes the two-stage method; it does not bundle the predictors or supply an executable inference adapter.

## Usage

1. Featurize the product with the same RDKit/DGL graph conventions and atom order used for EGAT training. Unknown reaction class must remain unknown rather than being taken from test labels.
2. Use EGAT's auxiliary predicted disconnection count to choose that many highest-scoring product bonds. The paper's 0.5 threshold belongs to a main-task-only ablation; it is not interchangeable with the count-based path.
3. Disconnect selected bonds and retain atom correspondence. Use the model's synthon serialization, including chemically incomplete synthons; ordinary sanitization can discard exactly the intermediates RGN was trained to complete.
4. Construct the RGN source using its real token vocabulary/order: optional class, canonical product, `<link>`, then dot-joined synthon strings. A literal-looking prompt without the matching tokenizer is insufficient.
5. Decode ranked reactant sets with the configured beam policy (the source experiments used 50). Preserve invalid/empty outputs and IDs. Compare canonical reactant sets under a declared stereo/map policy when references exist.

Output per input: chosen center bonds/count, intermediate synthon encoding, ranked reactant sets and stage failures. For end-to-end evaluation always pass **predicted** synthons, including erroneous centers, into RGN. Report oracle-center evaluation separately; filtering to correctly predicted centers inflates apparent system quality.

If only product SMILES is available and the configured models/interfaces are absent, identify those missing inputs rather than inventing model calls. Source: [RetroXpert paper](https://arxiv.org/abs/2011.02893); the paper's historical repository is `uta-smile/RetroXpert`, whose README was not retrievable during this review. No currently available deployment interface is asserted here.
