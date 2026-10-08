---
name: convex-hull-reference-scale
description: >-
  Evaluate phase stability only against compatible competing-phase energies. Invoke for: energy-above-hull calculations; not for comparing a new model energy to a hull built on an unrelated reference scale.
license: MIT
compatibility: Target and competing phase structures with one consistent energy model
allowed-tools: Read, Bash
---

# Convex Hull Reference Scale

## Applicability

Use when judging thermodynamic stability of a composition against known competing phases. A single target energy cannot establish energy above hull without a compatible reference set.

## Credibility

**low confidence (Highly flexible).** The benchmark defines a hull task; no hull calculation or agent comparison was performed for this skill.

## Reference

[Convex-hull benchmark task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/convex-hull-stability/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/convex-hull-stability/tests/test_outputs.py).

## Input & Output

Input: target structure/composition, competing-phase set, consistent energies and relaxation policy. Output: decomposition products and energy above hull per atom with model provenance.

## Procedure Guidance

If the target and competing phases were evaluated with different potentials or DFT settings, recompute or apply a justified compatibility correction before hull construction. Include stable elemental endpoints and relevant intermediate compositions; missing competitors can make an unstable target look stable. Normalize energies and compositions consistently, solve the lowest-energy mixture at the target composition, then subtract its energy from the target energy. Flag an incomplete phase set rather than reporting the result as definitive stability.

## Success Criteria

The target and hull energies share one reference scale, and a decomposition or stability certificate supports the reported energy-above-hull value.

## Matters & Troubleshooting

Metastability, finite-temperature effects, and kinetic persistence are not captured by a zero-K hull alone.
