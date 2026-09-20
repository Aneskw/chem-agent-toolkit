---
name: select-reaction-smiles-augmentation
description: >
  Draft procedure for choosing training and inference augmentation for a single-step retrosynthesis Transformer, including full-reaction randomization, reactant shuffling, and optional mixed-direction training. Invoke for: Choose augmentation according to whether target reaction information is available and whether the objective prioritizes top-1 or top-5 prediction; preserve canonical examples and evaluate on held-out reactions. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Select Reaction Smiles Augmentation

This cited draft describes Choose augmentation according to whether target reaction information is available and whether the objective prioritizes top-1 or top-5 prediction; preserve canonical examples and evaluate on held-out reactions. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

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

- Reaction pairs represented as product SMILES inputs and reactant/reagent SMILES targets. (s1p3:L30-L33)
- A prediction objective distinguishing top-1 accuracy from recovering the recorded reaction among the top-5 suggestions. (s1p4:L24-L26)

Outputs:

- Augmented training reactions with at least one canonical copy per reaction and product-only augmentation for retrosynthesis test inputs. (s1p2:L82-L86)

## Procedure Guidance

- Generate alternative valid SMILES by randomizing the starting atom and graph traversal direction. (s1p2:L56-L58)
- For training with multiple augmentations, augment both products and reactant/reagent targets; optionally shuffle reactant order as the xNS protocol. (s1p3:L63-L66, s1p3:L73-L75)
- If using mixed-direction training, reverse product and reactant/reagent roles and add a dot to distinguish the direct reactions in this retrosynthesis-centered protocol. (s1p4:L7-L10)
- Treat augmentation count as objective-dependent: the paper's top-1 experiments favored x20S or x10M, whereas its highest top-5 result favored x5M. Use these as study-specific reference choices rather than universal optima. (s1p4:L21-L23, s1p4:L42-L45)
- Keep at least one canonical copy in every training augmentation scenario. At retrosynthesis inference, augment only the product because the target reactants and reagents are unavailable. (s1p2:L82-L85, s1p2:L85-L86)
- Evaluate held-out test reactions after training finishes, without using them during model development. (s1p2:L96-L98)

## Matters & Troubleshooting

Resources:

- external_asset: https://github.com/bigchem/synthesis — The paper identifies this repository as the source of augmentation code; its implementation is absent from the supplied inventory.

Unknowns and limits:

- The supplied bundle lacks the augmentation implementation and Supplementary Methods.
- Exact tokenization, Transformer configuration, training commands, dependency versions, and random-seed handling are not supplied.
- The reported augmentation optima are dataset-specific and are not established for new reaction collections.
