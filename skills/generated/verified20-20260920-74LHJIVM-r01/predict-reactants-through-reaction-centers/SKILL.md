---
name: predict-reactants-through-reaction-centers
description: >
  Draft procedure for single-step retrosynthesis using EGAT to select bond disconnections and RGN to generate reactants from the resulting synthons. Invoke for: Given a product, predict its reaction center, split it into synthons, and decode candidate reactant sets. Use the auxiliary predicted bond count to select disconnections; evaluate complete predictions against reference reactants when available. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Predict Reactants Through Reaction Centers

This cited draft describes Given a product, predict its reaction center, split it into synthons, and decode candidate reactant sets. Use the auxiliary predicted bond count to select disconnections; evaluate complete predictions against reference reactants when available. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p1; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p2; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p3; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p4; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p5; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p6; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p7; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p8; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p9; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p10; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p11; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p12; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p13; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p14; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p15; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p16; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)
- paper: https://arxiv.org/pdf/2011.02893.pdf (source s1p17; SHA-256 370efa2febec1d019342f681faf4cd5d1a7fbd77375e1c8058737807d4b81846)

## Input & Output

Inputs:

- Target product represented as a molecular graph. (s1p3:L68-L69)
- Reaction type, if supplied, as additional conditioning information. (s1p5:L6-L7)

Outputs:

- Intermediate synthons produced by disconnecting the selected product bonds. (s1p5:L23-L24)
- Ranked candidate reactant sets represented in canonical SMILES. (s1p7:L7-L8)

## Procedure Guidance

- Construct molecular graphs with DGL and extract atom and bond features using RDKit. Add the reaction-type indicator when the type is known. (s1p6:L35-L36, s1p5:L6-L7)
- Use EGAT to predict per-bond disconnection probabilities and the auxiliary total disconnection count. Select that number of the most probable disconnection bonds. For the main-task-only ablation, binarize predictions at 0.5 instead. (s1p3:L68-L69, s1p7:L29-L32, s1p7:L19-L20)
- Disconnect the selected bonds to obtain synthons and convert their graphs to SMILES using RDKit, including chemically invalid synthons. (s1p5:L23-L24, s1p5:L33-L34)
- Build the RGN source from the optional reaction type, canonical product SMILES, and synthon SMILES. Separate product and synthons with <link> and join synthon SMILES with dots. (s1p5:L35-L36, s1p5:L47-L49)
- Generate reactants with the Transformer-based RGN using beam search with K=50, the paper's experimental setting. (s1p6:L4-L5, s1p7:L6-L8)
- For end-to-end evaluation, supply predicted synthons to RGN regardless of reaction-center correctness and compare the predicted reactant sets with ground truth. Count a prediction as correct only on exact set agreement. (s1p7:L61-L64, s1p7:L8-L9)

## Matters & Troubleshooting

Resources:

- external_asset: https://github.com/uta-smile/RetroXpert — The paper identifies this repository as the source of code; no implementation files are supplied in the snapshot.
- external_asset: https://www.rdkit.org — RDKit is used for chemical features and synthon SMILES conversion.

Unknowns and limits:

- No executable entry points, implementation files, dependency versions, or trained checkpoint locations are supplied.
- Beam termination, tie-breaking, invalid decoded SMILES handling, and candidate deduplication rules are unspecified.
- Exact agreement with a recorded reaction does not establish experimental feasibility; the paper notes that multiple valid syntheses may exist.
