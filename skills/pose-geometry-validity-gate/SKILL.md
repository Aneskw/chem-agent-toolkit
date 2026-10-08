---
name: pose-geometry-validity-gate
description: >-
  Reject malformed docked poses before ranking or refinement. Invoke for: ligand geometry screening of pose ensembles; not for claiming receptor compatibility when no receptor is supplied.
license: MIT
compatibility: Molecular structures with 3D coordinates and an appropriate pose-validation tool
allowed-tools: Read, Bash
---

# Pose Geometry Validity Gate

## Applicability

Use before interpreting docking scores when output geometries may be corrupted. Distinguish ligand-only checks from protein-ligand interaction checks.

## Credibility

**low confidence (Highly flexible).** Adapted from a benchmark task; no prospective docking improvement is claimed.

## Reference

[Pose quality task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/pose-quality-filter/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/pose-quality-filter/tests/test_outputs.py).

## Input & Output

Input: ordered pose records and a named validation configuration. Output: valid/invalid pose IDs, failed checks, and unmodified valid coordinates.

## Procedure Guidance

Select validation checks according to available context: without a receptor, use ligand geometry only and do not infer absence of clashes with protein. Run all configured binary checks, including bond geometry and aromatic planarity; a favorable docking score never overrides an invalid geometry. Preserve original pose identifiers and ordering, and export only passing records without silently reoptimizing coordinates. If a tool cannot parse a record, classify it as unassessed/failed rather than dropping it.

## Success Criteria

Every input pose has one explicit disposition and the retained coordinate file contains exactly the accepted poses.

## Matters & Troubleshooting

Validation thresholds are tool-version dependent. Record the configuration and version; ligand-only acceptance is not a binding-pose validation.
