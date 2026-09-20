---
name: prepare-single-product-reaction-sequences
description: >
  Draft procedure for filtering atom-mapped reaction data, splitting related reactions together, and constructing source and target sequences with separate reactant and reagent tokenization. Invoke for: Prepare single-product reaction examples for sequence-to-sequence learning, branching on canonicalizability, product count, atom contribution, and membership in the common-reagent vocabulary. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Prepare Single Product Reaction Sequences

This cited draft describes Prepare single-product reaction examples for sequence-to-sequence learning, branching on canonicalizability, product count, atom contribution, and membership in the common-reagent vocabulary. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://arxiv.org/pdf/1711.04810.pdf (source s1p1; SHA-256 6dfa50a0a880e1f699335c8d5b14500ad56904a852091bb9bea607d10f39e0f4)
- paper: https://arxiv.org/pdf/1711.04810.pdf (source s1p2; SHA-256 6dfa50a0a880e1f699335c8d5b14500ad56904a852091bb9bea607d10f39e0f4)
- paper: https://arxiv.org/pdf/1711.04810.pdf (source s1p3; SHA-256 6dfa50a0a880e1f699335c8d5b14500ad56904a852091bb9bea607d10f39e0f4)
- paper: https://arxiv.org/pdf/1711.04810.pdf (source s1p4; SHA-256 6dfa50a0a880e1f699335c8d5b14500ad56904a852091bb9bea607d10f39e0f4)
- paper: https://arxiv.org/pdf/1711.04810.pdf (source s1p5; SHA-256 6dfa50a0a880e1f699335c8d5b14500ad56904a852091bb9bea607d10f39e0f4)
- paper: https://arxiv.org/pdf/1711.04810.pdf (source s1p6; SHA-256 6dfa50a0a880e1f699335c8d5b14500ad56904a852091bb9bea607d10f39e0f4)
- paper: https://arxiv.org/pdf/1711.04810.pdf (source s1p7; SHA-256 6dfa50a0a880e1f699335c8d5b14500ad56904a852091bb9bea607d10f39e0f4)
- paper: https://arxiv.org/pdf/1711.04810.pdf (source s1p8; SHA-256 6dfa50a0a880e1f699335c8d5b14500ad56904a852091bb9bea607d10f39e0f4)
- paper: https://arxiv.org/pdf/1711.04810.pdf (source s1p9; SHA-256 6dfa50a0a880e1f699335c8d5b14500ad56904a852091bb9bea607d10f39e0f4)
- paper: https://arxiv.org/pdf/1711.04810.pdf (source s1p10; SHA-256 6dfa50a0a880e1f699335c8d5b14500ad56904a852091bb9bea607d10f39e0f4)

## Input & Output

Inputs:

- Atom-mapped reaction SMILES containing reactant, reagent, and product groups. (s1p3:L42-L43, s1p4:L40-L40)
- The set of 76 common reagents used to define the reagent vocabulary. (s1p5:L3-L4)

Outputs:

- Space-separated source sequences representing reactants followed by common reagents, paired with tokenized single-product targets. (s1p5:L9-L10)
- Training, validation, and test partitions in an 18:1:1 ratio, keeping reactions with the same reactants in one partition. (s1p4:L3-L4)

## Procedure Guidance

- Compare reaction strings without atom mapping to remove duplicates; discard reactions whose SMILES cannot be canonicalized with RDKit, and retain only single-product reactions. (s1p3:L47-L49, s1p3:L49-L50)
- Randomly partition the retained examples in an 18:1:1 ratio, assigning reactions with identical reactants but different reagents or products to the same partition. (s1p4:L3-L4)
- Use atom mappings to classify an input molecule as a reactant if it contributes atoms to the product; otherwise classify it as a reagent. (s1p4:L41-L42)
- Remove hydrogen atoms and atom mappings, canonicalize the molecules, and tokenize reactants and products atom-wise using the paper's regular expression. (s1p4:L42-L44, s1p5:L1-L2)
- For reagents in the common-reagent set, append distinct reagent tokens after the first '>' in occurrence order. Remove reagents outside that set. (s1p5:L5-L6)
- Construct source and target sequences with spaces between tokens and point tokens between individual molecules; apply the same preprocessing to every dataset. (s1p4:L17-L18, s1p5:L9-L11, s1p5:L11-L11)

## Matters & Troubleshooting

Resources:

- external_asset: https://zenodo.org/record/1004356#.Wd3LDY6l2EI — RDKit is the cited tool for canonicalization; the bibliography identifies the referenced release.
- external_asset: Schneider, Stieﬂ, and Landrum (2016), What’s What: The (Nearly) Deﬁnitive Guide to Reaction Role Assignment — The common-reagent set is attributed to this analysis, but its membership is not supplied.

Unknowns and limits:

- The full 76-reagent vocabulary and its exact token mapping are not supplied.
- No preprocessing implementation, RDKit API calls, or canonicalization options are supplied.
- The random seed and grouped partitioning algorithm are unspecified.
- Handling of absent or erroneous atom mappings is unspecified.
