---
name: potential-consistent-thermochemistry
description: >-
  Keep reaction thermochemistry on one model and standard-state scale. Invoke for: deriving equilibrium constants from computed species energies and frequencies; not for substituting remembered experimental values.
license: MIT
compatibility: Geometry, frequency, and partition-function calculations for all reaction species
allowed-tools: Read, Bash
---

# Potential-Consistent Thermochemistry

## Applicability

Use for model-predicted reaction enthalpy, entropy, free energy, and equilibrium constant. Do not mix energies from one potential with frequencies or elemental references from another without a documented correction.

## Credibility

**low confidence (Highly flexible).** Based on a benchmark calculation contract; the numerical workflow has not been run here.

## Reference

[Gas thermochemistry task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/chemistry/gas-thermochemistry-equilibrium/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/chemistry/gas-thermochemistry-equilibrium/tests/test_outputs.py).

## Input & Output

Input: balanced reaction, temperature, pressure convention, model identity, and species structures. Output: delta H, delta S, delta G, K, units, standard state, and model provenance.

## Procedure Guidance

First check stoichiometry, charge, and spin. Optimize and evaluate all species with the same potential, then use consistent translational, rotational, and vibrational partition functions. If a frequency calculation yields a true unstable mode, resolve it before treating the structure as an equilibrium species. Form reaction quantities by stoichiometric sums, check delta G = delta H - T delta S, then compute dimensionless K = exp(-delta G/RT) with delta G in J/mol. Compare with experiment only as an external validation, never as a replacement for the requested model prediction.

## Success Criteria

The reported thermodynamic identities and units are mutually consistent, and every species contribution comes from the stated method.

## Matters & Troubleshooting

Low frequencies, conformer mixtures, symmetry numbers, and standard-state conversion can dominate small free-energy differences.
