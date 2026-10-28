---
name: mlip-unit-consistent-error-audit
description: "Audit atomistic model errors across energy, force, and stress. Invoke for: benchmarking a potential against labeled structures; not for comparing stress errors before sign and Voigt conventions are reconciled."
license: MIT
---

# MLIP Unit-Consistent Error Audit

## Applicability

Use for atomistic potential evaluation when reference labels and model predictions are paired per structure. Do not silently omit failed structures from aggregate metrics.

## Input & Output

Input: structures, reference energy/forces/stress, model and conventions. Output: per-structure errors and aggregate MAE/RMSE for energy per atom, force components, and stress components with units.

## Procedure Guidance

Pair labels to structures by stable ID and verify atom count/order. Normalize total energy to per-atom energy only when the metric requests it; compare forces componentwise. Convert stress units and sign convention before computing error, and reorder Voigt components explicitly if source and model differ. Aggregate over the declared population and report failures separately. A good energy MAE does not imply acceptable forces or stress, so examine each channel independently.

## Success Criteria

All compared arrays have matched shapes, units, and conventions; aggregate errors reproduce their per-structure components.

## Matters & Troubleshooting

Mixed DFT functionals, relaxation states, and stress definitions can dominate apparent model error.
