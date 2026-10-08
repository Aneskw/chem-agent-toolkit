---
name: conformer-ensemble-population
description: >-
  Decide which relaxed conformers matter thermally. Invoke for: ranking molecular conformers or computing Boltzmann populations; not for assigning experimental stereoisomer populations without equilibration evidence.
license: MIT
compatibility: Conformer generator and a common geometry optimization and energy method
allowed-tools: Read, Bash
---

# Conformer Ensemble Population

## Applicability

Use when a single optimized structure may misrepresent a flexible molecule. Distinguish conformers from distinct stereoisomers, protonation states, or tautomers.

## Credibility

**low confidence (Highly flexible).** The guidance is grounded in a benchmark task, not in a measured skill-versus-baseline improvement.

## Reference

[Conformer benchmark task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/chemistry/conformer-boltzmann-ranking/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/chemistry/conformer-boltzmann-ranking/tests/test_outputs.py).

## Input & Output

Input: structure, temperature, search budget, geometry metric, and energy method. Output: unique relaxed conformers, relative energies, normalized populations, and structures in a coordinate-preserving format.

## Procedure Guidance

Generate a diverse initial ensemble, relax all candidates using one energy method, and cluster the relaxed structures before population calculation. If many starts collapse into one geometry, count it once unless sampling weights justify degeneracy. Convert energy differences to one unit before applying exp(-delta E/kBT), normalize over the retained ensemble, and disclose when free-energy corrections or conformational degeneracies are omitted. Expand the search if the lowest-energy structures are still appearing at the budget boundary.

## Success Criteria

Populations sum to approximately one, ranks follow increasing energy, and every reported geometry corresponds to its energy record.

## Matters & Troubleshooting

Energy-only Boltzmann weights are not full solution populations; solvent and entropy may change the ordering.
