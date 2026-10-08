---
name: microstate-aware-virtual-screening
description: >-
  Compare docking protocols at parent-compound and replicate level. Invoke for: virtual screens with enumerated ligand microstates and multiple seeds; not for choosing a protocol from its single best pose.
license: MIT
compatibility: Docking scores, microstate-to-parent map, pose validity results, and replicate labels
allowed-tools: Read, Bash
---

# Microstate-Aware Virtual Screening

## Applicability

Use when each parent has multiple protonation or tautomeric docking entries. A parent with more enumerated microstates must not receive extra statistical weight.

## Credibility

**low confidence (Highly flexible).** Based on a benchmark protocol; no prospective enrichment or skill-effect result is asserted.

## Reference

[Docking enrichment task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/docking-microstate-enrichment/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/docking-microstate-enrichment/tests/test_outputs.py).

## Input & Output

Input: scores and valid-pose flags by microstate and seed, parent map, actives/decoys, redocking control. Output: parent-level protocol rankings, replicate variability, control diagnosis, and follow-up parents.

## Procedure Guidance

Discard invalid poses before aggregating. Within each seed, reduce microstates to one declared parent summary; then compare seeds as independent replicates. Do not pool all microstates or cherry-pick the luckiest seed. Check redocking's top-ranked pose before trusting enrichment; the best-of-many pose is only diagnostic. Compare active recovery, decoy-panel sensitivity, and leave-one-seed-out ranking stability. If these disagree, report a qualified recommendation or no winner instead of optimizing to one favorable metric.

## Success Criteria

The recommended protocol survives its declared robustness gates and the final follow-up list uses parent IDs, not microstate IDs.

## Matters & Troubleshooting

Docking scores are not binding free energies; labels, decoy composition, and protein preparation can dominate apparent enrichment.
