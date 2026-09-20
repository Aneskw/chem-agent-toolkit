---
name: gln-constrained-retrosynthesis-search
description: >
  Draft procedure for single-step retrosynthesis that filters templates by structural compatibility, optionally conditions on a reaction class, and uses hierarchical beam search to select reactants. Invoke for: Given a target molecule and GLN scoring functions, restrict the search to matching templates, generate compatible reactants, and select the highest-scoring template–reactant proposal. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Gln Constrained Retrosynthesis Search

This cited draft describes Given a target molecule and GLN scoring functions, restrict the search to matching templates, generate compatible reactants, and select the highest-scoring template–reactant proposal. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p1; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p2; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p3; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p4; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p5; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p6; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p7; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p8; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p9; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p10; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p11; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p12; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p13; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p14; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)
- paper: https://arxiv.org/pdf/2001.01408.pdf (source s1p15; SHA-256 79e0d76657f2a638375ef01308796a6089759aceae85a9314f2bb9f6ea79aeac)

## Input & Output

Inputs:

- Target product molecule O. (s1p3:L20-L22)
- Retrosynthesis templates and GLN template and reactant scoring functions. (s1p3:L43-L45)
- Beam size k and, when available, an expert-specified reaction type c. (s1p7:L6-L6, s1p4:L12-L14)

Outputs:

- A selected reactant set and associated template, ranked by the combined template and reactant score. (s1p7:L13-L15)

## Procedure Guidance

- Restrict templates to known rules whose product-side pattern matches a subgraph of the target. Treat matching as necessary for model support, rather than sufficient evidence of chemical feasibility. (s1p3:L31-L33, s1p3:L41-L43)
- If the reaction type is given, further restrict templates to that type. (s1p4:L15-L16)
- For accelerated inference, retain the k reaction centers with the highest v1 scores. Score corresponding valid templates using v2 and retain the k templates with the highest combined v1 + v2 scores. (s1p7:L6-L9, s1p7:L10-L13)
- For each retained template, enumerate all product-pattern matches, instantiate the reactant-pattern atoms for each match, and copy connected atoms and atom properties from the product. The paper operationalizes this with RDKit runReactants and improved stereochemistry handling. (s1p6:L66-L70, s1p7:L1-L2)
- Require the number of reactants to equal the number of template reactant patterns, with a permutation matching each reactant to its corresponding pattern. Finish by selecting the compatible proposal with the largest total w1 + w2 score. (s1p3:L38-L40, s1p7:L13-L15)
- When ground-truth reactants are available, verify prediction accuracy by exact comparison of RDKit-generated canonical SMILES for the reactant sets. (s1p7:L34-L36)

## Matters & Troubleshooting

Resources:

- external_asset: RDKit — Provides the reaction-template application operation used by the paper.
- external_asset: https://github.com/connorcoley/rdchiral — Referenced implementation for improved stereochemistry handling during template application.

Unknowns and limits:

- No implementation source files or trained model weights are supplied.
- Exact API signatures, dependency versions, and executable inference commands are not specified.
- Behavior for empty matching support, duplicate proposals, and score ties is not specified.
- Exact-match evaluation does not establish chemical feasibility; the paper notes that multiple reasonable syntheses may exist.
