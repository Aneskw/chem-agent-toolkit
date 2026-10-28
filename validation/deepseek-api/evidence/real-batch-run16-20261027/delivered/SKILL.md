---
name: rdkit-recap-terminal-fragments
description: Extract terminal RECAP molecular fragments with RDKit RecapDecompose and GetLeaves. Use for molecular fragmentation, not descriptor calculation, when empty results are valid.
---

# RDKit RECAP terminal fragments

Extract the standard terminal RECAP fragment set from a sanitized RDKit molecule.
This is molecular fragmentation, not descriptor calculation. Uses the upstream
RDKit implementation from `rdkit/Chem/Recap.py` at commit
`237a1d9027c800784afed8788540f38a3aa595f8` (BSD 3-Clause); see
`references/LICENSE.txt` for attribution and licence terms.

## Capability and boundary

- Call `rdkit.Chem.Recap.RecapDecompose(mol)` to decompose one molecule.
- Use `root.GetLeaves()` for the standard terminal fragment set.
- Use `root.children` for immediate products and `root.GetAllChildren()` for
  all hierarchy descendants when full hierarchy matters.
- Empty `children` or empty `leaves` is a valid result, not an error.
- The caller must provide a sanitized `rdkit.Chem.rdchem.Mol`. Sending `None`
  or an unsanitized Mol is an invalid input boundary; `RecapDecompose` does no
  SMILES parsing or caller-facing input validation.
- No new reaction rules are defined. Exact standard RECAP compliance is not
  claimed because the source reaction set includes an aromatic N-aromatic C
  rule marked "not part of the standard recap set".

## Inputs and outputs

| Input | Type/format | Required | Meaning |
|---|---:|---|---|
| `mol` | `rdkit.Chem.rdchem.Mol` | yes | sanitized molecule; e.g. `Chem.MolFromSmiles(...)`, checked not `None` |
| `allNodes` | dict or `None` | no | shared node cache keyed by canonical SMILES; `None` starts a new cache |
| `minFragmentSize` | int | no | minimum non-dummy atom count per product; default `0` |
| `onlyUseReactions` | iterable of int or `None` | no | 0-based indices into the upstream reaction tuple; `None` tries all |

Reaction indices are fixed by upstream `reactionDefs`:

| Index | Reaction |
|---:|---|
| 0 | urea |
| 1 | amide |
| 2 | ester |
| 3 | amines |
| 4 | cyclic amines |
| 5 | ether |
| 6 | olefin |
| 7 | aromatic nitrogen - aliphatic carbon |
| 8 | lactam nitrogen - aliphatic carbon |
| 9 | aromatic carbon - aromatic carbon |
| 10 | aromatic nitrogen - aromatic carbon (non-standard; source notes this is not part of standard RECAP) |
| 11 | sulphonamide |

Return value: `rdkit.Chem.Recap.RecapHierarchyNode`.

- `root.smiles` is the canonical input SMILES produced by `Chem.MolToSmiles(mol, 1)`.
- `root.children` is a dict of immediate child nodes keyed by canonical fragment
  SMILES containing `*` dummy atoms.
- `root.GetAllChildren()` returns all descendant nodes keyed by canonical SMILES.
- `root.GetLeaves()` returns terminal leaf nodes keyed by canonical SMILES; each
  node's `.mol` is the fragment Mol. This is the normal terminal fragment set.

Fragment keys are canonical SMILES from `Chem.MolToSmiles(prod, 1)` and include
`*` dummy atoms.

## Normal path

Prerequisite: RDKit must already be installed and importable in the execution
environment. The recipe uses only `rdkit.Chem` and `rdkit.Chem.Recap`.

```python
from rdkit import Chem
from rdkit.Chem import Recap

SMILES = "C1CC1Oc1ccccc1-c1ncc(OC)cc1"
mol = Chem.MolFromSmiles(SMILES)
if mol is None:
    raise ValueError(f"Invalid SMILES: {SMILES}")

root = Recap.RecapDecompose(mol)
leaves = root.GetLeaves()

print(sorted(leaves.keys()))
# ['*C1CC1', '*c1ccc(OC)cn1', '*c1ccccc1*']
```

This input demonstrates terminal-vs-hierarchy counts from the upstream
docstring: immediate children `len(root.children) == 4`,
`len(root.GetAllChildren()) == 5`, and terminal leaves
`len(root.GetLeaves()) == 3`.

## Optional filters

Restrict to the amide reaction (index `1`) and require non-dummy atom count at
least 1 per product:

```python
mol = Chem.MolFromSmiles("C1CC1C(=O)NC1OC1")
if mol is None:
    raise ValueError("Invalid SMILES")
root = Recap.RecapDecompose(mol, onlyUseReactions=[1])
print(sorted(root.GetLeaves().keys()))
# ['*C(=O)C1CC1', '*NC1CO1']
```

Filter semantics from the source:

- When `minFragmentSize == 0` (default), a product sequence is rejected if any
  product after replacing `*` and removing empty branches has SMILES `''`, `'C'`,
  `'CC'`, or `'CCC'`.
- When `minFragmentSize > 0`, the default small fragment filter is replaced:
  each product is rejected when `explicit_atom_count - number_of_dummy_atoms`
  is less than `minFragmentSize`.

## Result interpretation and failure signals

- Validate the molecule before calling `RecapDecompose`; `Chem.MolFromSmiles`
  returns `None` for invalid SMILES. Passing invalid input causes downstream
  `Chem.MolToSmiles`/reaction errors, not a dedicated validation exception.
- Check `isinstance(root, Recap.RecapHierarchyNode)` to confirm decomposition
  was attempted.
- Empty results are meaningful: `RecapDecompose(Chem.MolFromSmiles("CCCOCCC")).children == {}`
  when no reaction applies or all products are filtered. Do not treat an empty
  leaf dict as a failure.
- Use `GetLeaves()` for terminal fragments; use `GetAllChildren()` only when you
  explicitly need non-terminal intermediates too.
- This skill does not provide chemical or scientific validation beyond the
  documented upstream RECAP algorithm.
