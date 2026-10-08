---
name: template-guided-docking-box
description: >-
  Transfer a bound ligand into an apo target before defining a docking box. Invoke for: template-supported pocket localization; not for a target lacking reliable structural correspondence.
license: MIT
compatibility: Aligned protein structures and ligand coordinates in a common length unit
allowed-tools: Read, Bash
---

# Template-Guided Docking Box

## Applicability

Use when a homologous or matched ligand-bound template identifies the likely binding site. If alignment is poor or the pocket rearranges substantially, treat the box as provisional.

## Credibility

**low confidence (Highly flexible).** Based on a benchmark geometry task; docking success has not been measured here.

## Reference

[Ligand box task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/ligand-box-definition/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/ligand-box-definition/tests/test_outputs.py).

## Input & Output

Input: template complex, apo target, atom correspondence, ligand ID, coordinate unit. Output: protein-alignment RMSD, transferred ligand, pocket residues, box center and edge lengths.

## Procedure Guidance

Resolve alternate locations consistently and fit corresponding protein atoms with a proper rotation, never a reflection. Apply that protein-derived transform to the ligand; do not fit ligand atoms to the target independently. Identify nearby residues by atom proximity, then include entire selected residues in the box point set when a residue-complete pocket is required. Pad the resulting coordinate extent, impose a documented minimum size, and inspect whether the box still includes the transferred ligand and plausible flexible side chains.

## Success Criteria

The transformed ligand and all selected pocket atoms lie within a box whose construction and alignment error are reported.

## Matters & Troubleshooting

Mismatched residue numbering, alternate conformers, missing loops, and protonation can make a geometrically valid box biologically wrong.
