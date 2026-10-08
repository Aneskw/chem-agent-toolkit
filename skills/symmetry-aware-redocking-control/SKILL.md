---
name: symmetry-aware-redocking-control
description: >-
  Validate redocking with symmetry-corrected in-place RMSD. Invoke for: checking whether a docking protocol recovers its known pose; not for post hoc superposing the docked ligand into success.
license: MIT
compatibility: Reference and docked ligand coordinates in the same receptor frame
allowed-tools: Read, Bash
---

# Symmetry-Aware Redocking Control

## Applicability

Use for self-docking controls with chemically equivalent atom mappings. If reference and docking frames differ, align receptors first, not ligands.

## Credibility

**low confidence (Highly flexible).** The benchmark specifies this gate; the skill itself has not been independently evaluated.

## Reference

[Symmetry redocking task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/symmetry-redocking-rmsd/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/symmetry-redocking-rmsd/tests/test_outputs.py).

## Input & Output

Input: crystallographic reference ligand, score-ordered docked poses, atom mapping and success threshold. Output: per-pose heavy-atom RMSD, top-pose gate, and best-pose diagnostic.

## Procedure Guidance

Enumerate chemically valid symmetry permutations, including ring automorphisms where applicable, and take the minimum in-place heavy-atom RMSD over those mappings. Do not rigidly align each docked pose to the reference because that removes translational and rotational docking error. Judge the protocol using the top-scored pose against a predefined threshold. Report the minimum RMSD across all poses separately; a good lower-ranked pose diagnoses a ranking problem but does not turn a failed top-pose gate into a pass.

## Success Criteria

Every pose has a symmetry-aware RMSD and the pass/fail gate is computed solely from pose one.

## Matters & Troubleshooting

Atom-order mismatch, missing hydrogens, tautomer changes, or receptor-frame mismatch require explicit mapping or invalidate the comparison.
