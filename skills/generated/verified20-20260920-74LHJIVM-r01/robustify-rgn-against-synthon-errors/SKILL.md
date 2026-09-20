---
name: robustify-rgn-against-synthon-errors
description: >
  Draft training and evaluation procedure that aligns reactant ordering with synthons and augments RGN training with EGAT errors so the generator can learn to recover from incorrect reaction centers. Invoke for: Create aligned synthon/reactant training pairs, reverse ordinary multi-synthon examples, add unsuccessful EGAT training predictions without reversing them, and verify recovery using predicted synthons at evaluation. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Robustify Rgn Against Synthon Errors

This cited draft describes Create aligned synthon/reactant training pairs, reverse ordinary multi-synthon examples, add unsuccessful EGAT training predictions without reversing them, and verify recovery using predicted synthons at evaluation. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

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

- Training reactions containing products and reference reactants, from which ground-truth reaction centers and synthons can be derived. (s1p6:L36-L37)
- EGAT synthon predictions on the training reactions, including predictions that disagree with ground truth. (s1p6:L17-L19)

Outputs:

- Augmented RGN training examples containing aligned ordinary examples, reversed multi-synthon examples, and unreversed erroneous synthon predictions. (s1p6:L28-L29, s1p6:L18-L20)
- A trained RGN intended to recover desired reactants from incorrect synthons, assessed through end-to-end reactant prediction. (s1p6:L21-L22)

## Procedure Guidance

- Compare product and reactant graphs to label disconnections. Use atom mappings when available; for unmapped reactions, use RDKit substructure matching for the comparison. (s1p6:L36-L37, s1p6:L38-L39)
- Split products using ground-truth reaction centers, convert synthons to SMILES, and align target reactant ordering with source synthon ordering. (s1p6:L42-L43, s1p6:L9-L11)
- When an ordinary training example has at least two synthons, add an example with both synthons and corresponding reactants in reverse order. (s1p6:L28-L29, s1p5:L50-L51)
- Run EGAT on training products and add unsuccessful synthon predictions as RGN training inputs for the desired reactants. Do not reverse these error-derived augmentation examples. (s1p7:L47-L49, s1p6:L17-L20)
- Train RGN on the augmented data. In the USPTO-50K configuration, train for 300,000 steps, save every 10,000 steps, and average the last ten checkpoints as the final model. (s1p7:L52-L53, s1p7:L2-L4)
- Evaluate recovery by passing all predicted synthons to RGN, including incorrect reaction centers. Separately use ground-truth synthons to assess the RGN upper bound; do not gate end-to-end decoding on correct reaction-center identification. (s1p16:L36-L39, s1p7:L54-L56)

## Matters & Troubleshooting

Resources:

- external_asset: https://github.com/uta-smile/RetroXpert — Referenced implementation and processed USPTO-full data; neither implementation files nor data are included in the supplied snapshot.

Unknowns and limits:

- The supplied evidence does not specify how erroneous synthons are aligned with target reactants when their counts or correspondences differ.
- DGL and OpenNMT are named as implementations, but package versions, invocation syntax, and implementation files are absent.
- The referenced SMILES tokenization regular expression is not reproduced in the supplied text.
- No successful training or evaluation execution is established by this extraction.
