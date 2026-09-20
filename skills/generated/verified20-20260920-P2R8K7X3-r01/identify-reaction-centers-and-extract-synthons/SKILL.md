---
name: identify-reaction-centers-and-extract-synthons
description: >
  Draft procedure for selecting reaction centers from a product graph and extracting synthons, including the fallback when no center is identified. Invoke for: Score product atom pairs, select centers above a threshold, and disconnect their bonds to obtain synthons. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Identify Reaction Centers And Extract Synthons

This cited draft describes Score product atom pairs, select centers above a threshold, and disconnect their bonds to obtain synthons. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://arxiv.org/pdf/2003.12725.pdf (source s1p1; SHA-256 d06c825be76b51dd24c8a6d1b8c0a8a01731bb0b82796bdc952eca0bdd39a2ad)
- paper: https://arxiv.org/pdf/2003.12725.pdf (source s1p2; SHA-256 d06c825be76b51dd24c8a6d1b8c0a8a01731bb0b82796bdc952eca0bdd39a2ad)
- paper: https://arxiv.org/pdf/2003.12725.pdf (source s1p3; SHA-256 d06c825be76b51dd24c8a6d1b8c0a8a01731bb0b82796bdc952eca0bdd39a2ad)
- paper: https://arxiv.org/pdf/2003.12725.pdf (source s1p4; SHA-256 d06c825be76b51dd24c8a6d1b8c0a8a01731bb0b82796bdc952eca0bdd39a2ad)
- paper: https://arxiv.org/pdf/2003.12725.pdf (source s1p5; SHA-256 d06c825be76b51dd24c8a6d1b8c0a8a01731bb0b82796bdc952eca0bdd39a2ad)
- paper: https://arxiv.org/pdf/2003.12725.pdf (source s1p6; SHA-256 d06c825be76b51dd24c8a6d1b8c0a8a01731bb0b82796bdc952eca0bdd39a2ad)
- paper: https://arxiv.org/pdf/2003.12725.pdf (source s1p7; SHA-256 d06c825be76b51dd24c8a6d1b8c0a8a01731bb0b82796bdc952eca0bdd39a2ad)
- paper: https://arxiv.org/pdf/2003.12725.pdf (source s1p8; SHA-256 d06c825be76b51dd24c8a6d1b8c0a8a01731bb0b82796bdc952eca0bdd39a2ad)
- paper: https://arxiv.org/pdf/2003.12725.pdf (source s1p9; SHA-256 d06c825be76b51dd24c8a6d1b8c0a8a01731bb0b82796bdc952eca0bdd39a2ad)
- paper: https://arxiv.org/pdf/2003.12725.pdf (source s1p10; SHA-256 d06c825be76b51dd24c8a6d1b8c0a8a01731bb0b82796bdc952eca0bdd39a2ad)

## Input & Output

Inputs:

- A product molecular graph represented by an adjacency matrix and node features. (s1p3:L68-L70)
- A reaction-center score threshold and a choice between highest-scoring and top-k selection. (s1p4:L32-L36)

Outputs:

- Connected synthon subgraphs after bond disconnection, or the original product graph if no reaction center is identified. (s1p4:L39-L43)

## Procedure Guidance

- Compute product node embeddings and a graph embedding with an L-layer R-GCN and readout. (s1p3:L145-L148)
- Concatenate the two endpoint embeddings, bond-type feature, and product graph embedding; obtain a reactivity score using a feedforward network and sigmoid. If the reaction type is known, append its embedding to the network input. (s1p4:L3-L5, s1p4:L11-L16, s1p4:L14-L16)
- Select the highest-scoring atom pair above the threshold. Use top-k pairs above the threshold when greater route diversity warrants additional inference time. (s1p4:L32-L38)
- Disconnect the selected reaction-center bonds and extract connected subgraphs. If no center is identified, retain the entire product as a synthon. (s1p4:L39-L43)

## Matters & Troubleshooting

Resources:

- None identified.

Unknowns and limits:

- The numerical reaction-center threshold is not supplied.
- No implementation files, callable interface, or trained model checkpoint are supplied.
- The handling of multiple selected centers as separate hypotheses versus simultaneous disconnections is not fully specified.
