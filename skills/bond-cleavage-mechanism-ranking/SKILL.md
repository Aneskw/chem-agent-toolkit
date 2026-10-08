---
name: bond-cleavage-mechanism-ranking
description: >-
  Compare candidate bond cleavage under radical and ionic mechanisms. Invoke for: ranking weak bonds when the cleavage mechanism matters; not for predicting rates from bond energies alone.
license: MIT
compatibility: Molecular graph and a consistent energy method for each fragment charge and spin state
allowed-tools: Read, Bash
---

# Bond Cleavage Mechanism Ranking

## Applicability

Use for ranking specified single bonds by homolytic or heterolytic dissociation energy. Do not equate a low dissociation energy with the dominant experimental pathway without accounting for environment and barriers.

## Credibility

**low confidence (Highly flexible).** Adapted from a benchmark task and its output checks; no independent agent-effect or experimental validation has been run for this skill.

## Reference

[BDE benchmark task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/chemistry/bde-weak-bonds/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/chemistry/bde-weak-bonds/tests/test_outputs.py). Follow the benchmark's chosen potentials only when reproducing that task; otherwise select a method that covers the relevant charged and radical fragments.

## Input & Output

Input: molecular graph, eligible bonds, cleavage mechanism, environment, and energy method. Output: separate homolytic and heterolytic rankings, fragment charge/spin assignments, units, and excluded bonds with reasons.

## Procedure Guidance

Enumerate bonds on a hydrogen-complete graph when X-H cleavage is in scope. For homolysis, compare neutral radical fragments with the intact molecule on one energy scale. For heterolysis, evaluate both charge polarities; retain the lower valid energy and do not invent an unsupported isolated-ion reference. If a fragment type is outside the method's domain, mark that bond unresolved rather than transferring its homolytic score. Keep atom indices stable across fragmentation and verify every eligible bond appears once.

## Success Criteria

Each requested ranking covers exactly its eligible bonds, with internally consistent energy references and an explicit weakest bond for each mechanism.

## Matters & Troubleshooting

Solvent, counterions, spin contamination, and geometry relaxation can reverse rankings. Report these assumptions before interpreting a ranking as reactivity.
