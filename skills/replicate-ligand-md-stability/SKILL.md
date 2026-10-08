---
name: replicate-ligand-md-stability
description: >-
  Judge binding-mode persistence across independent MD runs. Invoke for: ligand stability audits using trajectories and contacts; not for inferring binding affinity from a single RMSD trace.
license: MIT
compatibility: Protein-ligand topology, periodic trajectories, and atom selections
allowed-tools: Read, Bash
---

# Replicate Ligand MD Stability

## Applicability

Use when multiple trajectories sample the same proposed binding mode. The comparison requires consistent atom mapping and a declared analysis window.

## Credibility

**low confidence (Highly flexible).** The decision logic comes from a benchmark task; no trajectories were run for this skill.

## Reference

[Ligand MD stability task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/ligand-md-stability/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/ligand-md-stability/tests/test_outputs.py).

## Input & Output

Input: common topology, independent trajectories, reference frame/window, periodic box, stability thresholds. Output: per-replicate RMSD distribution, relative COM drift, persistent contacts, and consensus verdict.

## Procedure Guidance

Make ligand and protein whole under periodic boundaries first. Align each frame on protein atoms to that replicate's own reference, then measure ligand motion without separately fitting the ligand. Combine ligand RMSD with protein-relative COM drift and residue contact persistence; a low RMSD alone can hide translational or contact changes. Apply thresholds per replicate, then require a predefined replicate majority. Intersect contacts only across replicates that pass the stability criteria.

## Success Criteria

The verdict is traceable to all independent replicates, with atom selections, reference frame, and contact definition recorded.

## Matters & Troubleshooting

Short simulations, incorrect imaging, ligand symmetry, and unstable protein alignment can invalidate the verdict.
