---
name: symmetry-aware-redocking-control
description: "Validate redocking with symmetry-corrected in-place RMSD. Invoke for: checking whether a docking protocol recovers its known pose; not for post hoc superposing the docked ligand into success."
license: MIT
---

# Symmetry-Aware Redocking Control

## Applicability

Use for self-docking controls with chemically equivalent atom mappings. If reference and docking frames differ, align receptors first, not ligands.

## Input & Output

Input: crystallographic reference ligand, score-ordered docked poses, atom mapping and success threshold. Output: per-pose heavy-atom RMSD, top-pose gate, and best-pose diagnostic.

## Procedure Guidance

Enumerate chemically valid symmetry permutations, including ring automorphisms where applicable, and take the minimum in-place heavy-atom RMSD over those mappings. Do not rigidly align each docked pose to the reference because that removes translational and rotational docking error. Judge the protocol using the top-scored pose against a predefined threshold. Report the minimum RMSD across all poses separately; a good lower-ranked pose diagnoses a ranking problem but does not turn a failed top-pose gate into a pass.

## Success Criteria

Every pose has a symmetry-aware RMSD and the pass/fail gate is computed solely from pose one.

## Matters & Troubleshooting

Atom-order mismatch, missing hydrogens, tautomer changes, or receptor-frame mismatch require explicit mapping or invalidate the comparison.

## RDKit in-place implementation

With RDKit installed and chemically matching SDF poses already in the same receptor frame:

```python
from rdkit import Chem
from rdkit.Chem import rdMolAlign

reference = Chem.RemoveHs(reference_mol)
pose = Chem.RemoveHs(docked_mol)
rmsd_angstrom = rdMolAlign.CalcRMS(pose, reference)
```

`CalcRMS` searches symmetry mappings without fitting coordinates. `GetBestRMS` performs alignment and is inappropriate for this gate. Check matching chemical identity, atom completeness and coordinate units first; for restricted/custom mappings pass the documented list of atom-pair maps. Many symmetric atoms can make exhaustive mapping expensive; if limiting `maxMatches`, record that limit rather than claiming an exhaustive minimum.

Source: [RDKit alignment API](https://www.rdkit.org/docs/source/rdkit.Chem.rdMolAlign.html).
