---
name: conformer-ensemble-population
description: "Decide which relaxed conformers matter thermally. Invoke for: ranking molecular conformers or computing Boltzmann populations; not for assigning experimental stereoisomer populations without equilibration evidence."
license: MIT
---

# Conformer Ensemble Population

## Applicability

Use when a single optimized structure may misrepresent a flexible molecule. Distinguish conformers from distinct stereoisomers, protonation states, or tautomers.

## Input & Output

Input: structure, temperature, search budget, geometry metric, and energy method. Output: unique relaxed conformers, relative energies, normalized populations, and structures in a coordinate-preserving format.

## Procedure Guidance

Generate a diverse initial ensemble, relax all candidates using one energy method, and cluster the relaxed structures before population calculation. If many starts collapse into one geometry, count it once unless sampling weights justify degeneracy. Convert energy differences to one unit before applying exp(-delta E/kBT), normalize over the retained ensemble, and disclose when free-energy corrections or conformational degeneracies are omitted. Expand the search if the lowest-energy structures are still appearing at the budget boundary.

## Success Criteria

Populations sum to approximately one, ranks follow increasing energy, and every reported geometry corresponds to its energy record.

## Matters & Troubleshooting

Energy-only Boltzmann weights are not full solution populations; solvent and entropy may change the ordering.

## Population calculation

For distinct conformer energies `E` in kJ/mol and `T > 0` in kelvin, NumPy arithmetic is:

```python
relative = E - E.min()
weights = np.exp(-1000.0 * relative / (8.314462618 * T))
populations = weights / weights.sum()
```

Import `numpy as np`; `E` must be a finite, nonempty array. These are energy-only weights unless `E` contains consistently defined free energies. Multiply by justified physical degeneracies before normalization when required; repeated optimizer starts are not degeneracies.
