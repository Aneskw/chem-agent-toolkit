---
name: rdkit-recap-terminal-fragments
description: Use RDKit Recap.RecapDecompose and RecapHierarchyNode.GetLeaves to get terminal RECAP molecular fragments as dummy-atom SMILES from a parsed RDKit Mol. Select when an agent needs standard RECAP leaf fragments, not the full hierarchy, descriptors, or custom reaction rules.
---

# RDKit RECAP terminal fragments

Use `rdkit.Chem.Recap` to decompose a parsed molecule and extract the standard RECAP terminal fragments. This is molecular fragmentation, not descriptor calculation, and it does not add new reaction rules or scientific thresholds.

## Prerequisites

- Python package `rdkit` with `rdkit.Chem` importable.
- A parsed, non-`None` RDKit molecule, normally obtained with `Chem.MolFromSmiles`.

```python
from rdkit import Chem
from rdkit.Chem import Recap
```

## Normal path

```python
mol = Chem.MolFromSmiles('C1CC1Oc1ccccc1-c1ncc(OC)cc1')
if mol is None:
    raise ValueError('could not parse SMILES')

root = Recap.RecapDecompose(mol)
leaves = root.GetLeaves()

terminal_smiles = sorted(leaves.keys())
# ['*C1CC1', '*c1ccc(OC)cn1', '*c1ccccc1*']

first_leaf = leaves[terminal_smiles[0]]
leaf_mol = first_leaf.mol          # RDKit Mol for this terminal fragment
leaf_smiles = first_leaf.smiles    # canonical dummy-atom SMILES
```

`root.GetLeaves()` returns only terminal leaf nodes; use it instead of `root.children` or `root.GetAllChildren()` when the standard RECAP fragment set is needed.

## Inputs

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `mol` | `Chem.Mol` | required | parsed, non-`None` molecule. `RecapDecompose` immediately calls `Chem.MolToSmiles(mol, 1)`; invalid or `None` inputs fail there. Use `Chem.MolFromSmiles` and check for `None`. |
| `allNodes` | `dict` or `None` | `None` | optional node cache keyed by canonical SMILES. If the input SMILES is already in the cache, `RecapDecompose` returns the cached node before applying new decomposition options. |
| `minFragmentSize` | `int` | `0` | minimum explicit non-dummy atom count in each fragment product after a cut. Products below the cutoff make that product sequence invalid. |
| `onlyUseReactions` | iterable of `int` or `None` | `None` | restrict decomposition to zero-based reaction indices in `rdkit.Chem.Recap.reactions`. See `references/reaction_indices.md`. |

## Outputs

`Recap.RecapDecompose` returns a `RecapHierarchyNode`:

- `root.children`: dictionary of direct child SMILES -> `RecapHierarchyNode`.
- `root.GetAllChildren()`: dictionary of all descendant nodes (the full hierarchy).
- `root.GetLeaves()`: dictionary of terminal leaf nodes only, keyed by canonical SMILES containing dummy atoms `*`. Each value is a `RecapHierarchyNode` with `.mol` (RDKit `Mol`) and `.smiles`.

`children` can include an intermediate node that is not terminal, as in the source example where `children` has four entries but `GetLeaves()` has three.

## Common options

### `minFragmentSize`

Default `0` applies the built-in small-fragment filter. A product sequence is rejected if an individual product SMILES, after `pSmi.replace('*', '').replace('()', '')`, is one of `''`, `'C'`, `'CC'`, or `'CCC'`.

When `minFragmentSize > 0`, the filter instead rejects a product when:

```text
explicit_atom_count - dummy_atom_count < minFragmentSize
```

where explicit atom count is `prod.GetNumAtoms(onlyExplicit=True)` and dummy count is the number of `*` characters in the product SMILES. The default `''/C/CC/CCC` filter is not used in this branch.

### `allNodes`

Pass an empty dict to reuse nodes across decompositions:

```python
allNodes = {}
res1 = Recap.RecapDecompose(Chem.MolFromSmiles('c1ccccc1-c1ncccc1'), allNodes=allNodes)
res2 = Recap.RecapDecompose(Chem.MolFromSmiles('COc1ccccc1-c1ncccc1'), allNodes=allNodes)
```

Only reuse the same cache when decomposition options are the same. A populated cache returns the existing node for a previously seen input SMILES before applying new `minFragmentSize` or `onlyUseReactions` options.

### `onlyUseReactions`

Pass a sequence of zero-based reaction indices:

```python
root = Recap.RecapDecompose(mol, onlyUseReactions=[1])   # amide only
leaves = root.GetLeaves()
```

See `references/reaction_indices.md` for the index list.

## Valid empty results

An empty `leaves` dict is normal and means no terminal fragments survived decomposition. Documented source cases include:

- `CCCOCCC` with default settings: `res.children == {}` (so `GetLeaves()` is empty too).
- `CCCOCC` with `minFragmentSize=3`: `res.children == {}`.
- Cyclic or unreactive examples, such as `C1CCCCO1` for ether and `C1CC=CC1` for olefin, produce `len(res.GetLeaves()) == 0`.

Do not treat an empty dict as failure. Inspect input structure and the `onlyUseReactions`/`minFragmentSize` options before concluding that no reaction was found.

## Failure signals

- `Chem.MolFromSmiles` returns `None` for invalid SMILES; passing `None` to `RecapDecompose` will fail when it calls `Chem.MolToSmiles(mol, 1)`.
- Product fragments are passed to `Chem.SanitizeMol(prod)` inside the decomposition loop, and the loop continues to the next product if sanitization raises an exception. The input molecule is not sanitized by `RecapDecompose`.
- Reusing a populated `allNodes` cache with a different `minFragmentSize` or `onlyUseReactions` can return the prior cached decomposition for the same input SMILES, not a recomputation. Use a fresh cache per option set.

## License

The RDKit Recap implementation is BSD-3-Clause licensed. See `references/LICENSE.txt` for the license text.

## Reaction index reference

For `onlyUseReactions`, see `references/reaction_indices.md` for the zero-based indices and source reaction definitions.
