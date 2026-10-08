---
name: quasi-harmonic-volume-scan
description: >-
  Guard QHA thermal-expansion estimates against bad volume windows and phonons. Invoke for: finite-temperature equilibrium volumes from an atomistic potential; not for fitting an unconstrained polynomial to sparse volumes.
license: MIT
compatibility: Relaxation, phonon force constants, Brillouin-zone sampling, and equation-of-state fitting
allowed-tools: Read, Bash
---

# Quasi-Harmonic Volume Scan

## Applicability

Use for quasi-harmonic thermal expansion when vibrational free energy varies with volume. It does not handle strongly anharmonic phases without additional validation.

## Credibility

**low confidence (Highly flexible).** The safeguards are drawn from a benchmark task; no QHA calculation was reproduced here.

## Reference

[Lithium QHA task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/li-qha-simulation/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/li-qha-simulation/tests/test_outputs.py).

## Input & Output

Input: crystal, potential, temperatures, volume window, phonon setup. Output: sampled static/vibrational energies, equilibrium volumes, free energies, expansion coefficients and diagnostics.

## Procedure Guidance

Relax the structure before centering a volume scan. At each sampled volume, compute phonons on a supercell and integrate over a q-mesh; Gamma-only frequencies can miss soft acoustic contributions. Check every volume for significant imaginary modes, separating small acoustic numerical noise from real instability; rerun a poisoned volume instead of integrating it. Fit F(V,T) with a physically motivated equation of state, then require each temperature's minimum to lie inside the sampled range. If a minimum touches the edge, extend the window before reporting thermal expansion.

## Success Criteria

All temperature minima are interior and phonon-validated, with volume and free-energy curves sufficient to reproduce the fit.

## Matters & Troubleshooting

Volume versus linear-strain percentages differ by approximately a factor of three for small strains; record which convention defines the scan.
