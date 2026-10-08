---
name: defect-formation-reference
description: >-
  Keep defect and elemental chemical-potential energies on one scale. Invoke for: vacancy formation-energy calculations; not for inserting literature chemical potentials into a different model's total energies.
license: MIT
compatibility: Bulk and defect structures, consistent potential, and elemental reference structures
allowed-tools: Read, Bash
---

# Defect Formation Reference

## Applicability

Use for neutral vacancy formation energies under declared chemical-potential conditions. Charged defects additionally require Fermi-level and finite-size corrections not covered here.

## Credibility

**low confidence (Highly flexible).** Adapted from a benchmark vacancy task; no defect calculations were performed for this package.

## Reference

[MgO vacancy task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/mgo-vacancy-energy/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/mgo-vacancy-energy/tests/test_outputs.py).

## Input & Output

Input: bulk structure, vacancy species/site, supercell, relaxation protocol, elemental references. Output: defect formation energy, each energy term, chemical potential and convergence limits.

## Procedure Guidance

Relax bulk and defect with compatible settings; hold or relax lattice vectors according to a stated finite-concentration approximation. Build pristine and defective supercells from the same relaxed parent. Obtain elemental reference *structures* from an authoritative source, then evaluate their energies using the same potential as the supercells. For a removed neutral atom, calculate E_defect - E_pristine + mu_removed. If an elemental structure or chemical environment is missing, mark the formation energy blocked rather than substituting an experimental chemical potential unnoticed.

## Success Criteria

All reported energy terms share one potential/reference and reproduce the stated formation-energy formula.

## Matters & Troubleshooting

Supercell size, magnetic state, oxygen reference and chemical-potential bounds can change the result.
