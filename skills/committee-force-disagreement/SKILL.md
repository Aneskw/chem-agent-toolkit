---
name: committee-force-disagreement
description: >-
  Rank structures for expensive labeling using MLIP committee disagreement. Invoke for: active-learning triage across independently trained atomistic models; not for ranking uncalibrated absolute-energy spread.
license: MIT
compatibility: Multiple compatible force predictors and the same structures for every model
allowed-tools: Read, Bash
---

# Committee Force Disagreement

## Applicability

Use when a model committee predicts energies and forces on the same candidate structures. Decide whether models share an energy reference before comparing absolute energies.

## Credibility

**low confidence (Highly flexible).** Motivated by a benchmark's reference-level caveat; no labeling-efficiency result has been measured here.

## Reference

[Committee uncertainty task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/machine-learning/committee-uncertainty-flagging/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/machine-learning/committee-uncertainty-flagging/tests/test_outputs.py).

## Input & Output

Input: candidate structures, committee checkpoint identities, predictions and target batch size. Output: per-structure energy spread, force disagreement, and ranked labeling candidates.

## Procedure Guidance

Verify identical atom ordering and units across models. If models have different atomic reference energies or training levels, report energy spread only as context and rank by force disagreement. Compute sample standard deviation across model forces for every atom/component, then one RMS over those component deviations. If the committee is effectively identical or out-of-domain in the same direction, disagreement may understate error; add diversity or external validation before declaring certainty. Select a labeling batch only after recording a deterministic tie rule.

## Success Criteria

The batch follows the declared uncertainty measure, with one comparable score per structure and no hidden energy-reference mixing.

## Matters & Troubleshooting

Committee spread measures disagreement, not calibrated predictive error; force magnitudes and structure size can affect interpretation.
