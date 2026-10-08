---
name: polymorph-free-energy-comparison
description: >-
  Compare near-degenerate polymorphs using free energy rather than static energy alone. Invoke for: temperature-dependent polymorph ranking; not for claiming a phase preference from unconverged switching work.
license: MIT
compatibility: Consistent potential, equilibrated phases, and a free-energy calculation method
allowed-tools: Read, Bash
---

# Polymorph Free-Energy Comparison

## Applicability

Use when the energy gap is comparable to vibrational or sampling corrections. State whether the requested quantity is Helmholtz or Gibbs free energy and match the ensemble accordingly.

## Credibility

**low confidence (Highly flexible).** Derived from a benchmark task; no free-energy simulation was run here.

## Reference

[Polymorph free-energy task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/polymorph-free-energy/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/polymorph-free-energy/tests/test_outputs.py).

## Input & Output

Input: phase structures, temperature, potential and ensemble, free-energy method. Output: per-atom free energies, difference, uncertainty, and ranking confidence.

## Procedure Guidance

Evaluate phases with the same potential and thermodynamic reference. For nonequilibrium switching, use a reversible reference pathway and both forward and reverse work distributions; if hysteresis is comparable to the phase gap, increase switching time or sampling rather than declaring a winner. Compare uncertainties with the free-energy difference before ranking. Normalize by the same atom count or formula unit and disclose whether nuclear quantum effects are omitted.

## Success Criteria

The reported phase ordering is supported by a converged free-energy difference whose uncertainty is smaller than the claimed distinction.

## Matters & Troubleshooting

Different cell sizes, incomplete equilibration, phase transitions during switching, and pressure mismatch can corrupt absolute free energies.
