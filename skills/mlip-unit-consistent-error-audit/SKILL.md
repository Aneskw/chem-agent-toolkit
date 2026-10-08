---
name: mlip-unit-consistent-error-audit
description: >-
  Audit atomistic model errors across energy, force, and stress. Invoke for: benchmarking a potential against labeled structures; not for comparing stress errors before sign and Voigt conventions are reconciled.
license: MIT
compatibility: Matched structures, labeled energy/force/stress arrays, and a runnable potential
allowed-tools: Read, Bash
---

# MLIP Unit-Consistent Error Audit

## Applicability

Use for atomistic potential evaluation when reference labels and model predictions are paired per structure. Do not silently omit failed structures from aggregate metrics.

## Credibility

**low confidence (Highly flexible).** Derived from a benchmark contract; no model was evaluated as part of creating this skill.

## Reference

[MLIP error task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/machine-learning/mlip-error-benchmark/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/machine-learning/mlip-error-benchmark/tests/test_outputs.py).

## Input & Output

Input: structures, reference energy/forces/stress, model and conventions. Output: per-structure errors and aggregate MAE/RMSE for energy per atom, force components, and stress components with units.

## Procedure Guidance

Pair labels to structures by stable ID and verify atom count/order. Normalize total energy to per-atom energy only when the metric requests it; compare forces componentwise. Convert stress units and sign convention before computing error, and reorder Voigt components explicitly if source and model differ. Aggregate over the declared population and report failures separately. A good energy MAE does not imply acceptable forces or stress, so examine each channel independently.

## Success Criteria

All compared arrays have matched shapes, units, and conventions; aggregate errors reproduce their per-structure components.

## Matters & Troubleshooting

Mixed DFT functionals, relaxation states, and stress definitions can dominate apparent model error.
