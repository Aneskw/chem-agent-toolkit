---
name: synthesis-precursor-evidence
description: >-
  Recommend experimentally reported precursor sets with source-level evidence. Invoke for: retrieving synthesis routes for a target material; not for presenting charge-balanced hypothetical reactants as published recipes.
license: MIT
compatibility: Access to full synthesis records or text-mined records with paper identifiers
allowed-tools: Read, Bash
---

# Synthesis Precursor Evidence

## Applicability

Use when the user asks for previously reported experimental starting-material combinations. A plausible stoichiometric equation alone is not publication evidence.

## Credibility

**low confidence (Highly flexible).** Based on a benchmark retrieval task; no literature set was verified for this package.

## Reference

[Precursor recommendation task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/synthesis-precursor-recommendation/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/synthesis-precursor-recommendation/tests/test_outputs.py).

## Input & Output

Input: target formula, synthesis database or literature corpus, allowed process conditions. Output: distinct precursor sets, source identifiers, experimental context, and unresolved ambiguities.

## Procedure Guidance

Normalize target composition before search, including accepted polymorph or dopant distinctions. For each candidate set, inspect the cited experimental methods and distinguish actual precursors from solvents, atmosphere, carbon sources, and intermediate products. Canonicalize formulas and hydration states for deduplication, but retain the original text and citation. If fewer than the requested number of distinct *published* sets can be verified, report the shortfall rather than padding with conjectural variants.

## Success Criteria

Every recommended set is linked to a specific experimental record and distinct after formula normalization.

## Matters & Troubleshooting

Text-mining errors and inaccessible methods sections require a lower-confidence label, not an invented citation.
