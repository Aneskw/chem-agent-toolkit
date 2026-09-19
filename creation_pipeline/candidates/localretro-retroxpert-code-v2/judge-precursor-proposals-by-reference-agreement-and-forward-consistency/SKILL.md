---
name: judge-precursor-proposals-by-reference-agreement-and-forward-consistency
description: >-
  Distinguish agreement with recorded reactants from recovery of the desired product under a supplied forward model, using explicit matching and stereochemistry rules. Invoke for: choosing a paper-backed procedure when task evidence or constraints change; do not treat this draft as experimentally validated.
license: undetermined
compatibility: Research draft; inspect source-specific dependencies and data before use
allowed-tools: Read
---

# Judge Precursor Proposals By Reference Agreement And Forward Consistency

Distinguish agreement with recorded reactants from recovery of the desired product under a supplied forward model, using explicit matching and stereochemistry rules. Use only for the task settings supported by the cited papers and pinned implementations. Do not use it as a generic reaction predictor or assume a successful agent effect.

## Credibility

**Low confidence (Highly flexible)** as an abstracted agent procedure: source locations were checked, while semantic merging and agent utility require human review. Research state: `procedural_skill_candidate`.

## Reference

- `2GFR874J/evaluate-retrosynthesis-exact-match-and-round-trip`: Deep Retrosynthetic Reaction Prediction using Local Reactivity and Global Attention (https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8549044/fullTextXML); implementation https://github.com/kaist-amsg/LocalRetro at `eba83e72efabeb854fec86c865e8743c295a8a1e`. Validated source locations: s1:L175-L176, s1:L176-L177, s1:L177-L179, s1:L179-L181, s1:L182-L183, s1:L183-L184.

## Input & Output

Inputs depend on the chosen variant:

- Desired target products and a pretrained Molecular Transformer forward-synthesis model.
- Predicted reactant sets and ground-truth reactants represented as canonical SMILES.

Expected outputs:

- Exact-match accuracy and round-trip accuracy for the evaluated predictions.

## Procedure Guidance

- **When** Predicted and reference reactant sets are available as canonical SMILES. **Do** Assess exact set agreement; when reference stereocenters lack specified stereoinformation, apply the stated atom-and-connectivity matching exception. **Avoid** Extend that exception to references with specified stereochemistry or silently substitute later repository metrics. (supported by 2GFR874J/evaluate-retrosynthesis-exact-match-and-round-trip).
- **When** Assessing round-trip correctness with the specified pretrained forward model available. **Do** Accept a proposal if it matches the reference reactants or its forward prediction matches the desired product. **Avoid** Require both conditions, equate forward consistency with experimental feasibility, or substitute an unspecified forward model. (supported by 2GFR874J/evaluate-retrosynthesis-exact-match-and-round-trip).

Deduplication recommendation: `review_duplicate`; chem-retro-candidate-evaluation describes the same evaluation task. Human review should check whether its stereochemistry exception and round-trip acceptance logic match this candidate before treating them as duplicates.

## Matters & Troubleshooting

- Canonicalization, product equivalence, forward-model checkpoint and inference configuration remain unspecified.
- Invalid inputs, duplicates, and forward-model failure handling are unresolved.
- No evaluation results or execution success are established.
- Catalog overlap note for chem-retro-candidate-evaluation: direct capability overlap; proposed duplicate subject to matching-rule review.
- Catalog overlap note for localtransform-forward-prediction: related forward-model resource checking, but neither this evaluation capability nor the specified Molecular Transformer.
- Catalog comparisons use supplied package descriptions only; full package behavior must be inspected before any duplicate or variant consolidation.
- All deduplication actions are proposals for human review, not authorization for automatic semantic merging.
- Evidence is limited to supplied summaries and evidence identifiers; unavailable source text was not inspected.
- Do not count this candidate as an executable or agent-validated skill.
