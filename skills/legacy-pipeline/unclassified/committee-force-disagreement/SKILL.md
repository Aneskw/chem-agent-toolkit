---
name: committee-force-disagreement
description: "Rank structures for expensive labeling using MLIP committee disagreement. Invoke for: active-learning triage across independently trained atomistic models; not for ranking uncalibrated absolute-energy spread."
license: MIT
---



# Committee Force Disagreement

## Applicability

Use when a model committee predicts energies and forces on the same candidate structures. Decide whether models share an energy reference before comparing absolute energies.


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


## Computing the declared score

Given finite force predictions `F` with shape `(models, atoms, 3)` in the same units and atom order, require at least two models. With NumPy:

```python
component_std = F.std(axis=0, ddof=1)
force_disagreement = float((component_std ** 2).mean() ** 0.5)
```

This is RMS component disagreement, not the maximum atomic force deviation. Record that definition; do not compare numbers from different definitions as if interchangeable.
