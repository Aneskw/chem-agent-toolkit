---
name: rdkit-recap-terminal-fragments
description: Generate RDKit RECAP terminal molecular fragments from a valid RDKit Mol using RecapDecompose and GetLeaves; select for molecular fragmentation when terminal leaves, not full hierarchy or descriptor calculation, are needed.
---

# RDKit RECAP terminal fragments

## Capability and boundary
This skill invokes the RDKit implementation of the RECAP algorithm from Lewell et al. and returns the terminal fragment set via `RecapHierarchyNode.GetLeaves()`. It fragments molecules only; output indicates algorithm-recognized bond breaks and does not imply synthetic feasibility, bioactivity, or chemical validation beyond the documented RECAP rules.

The terminal leaves are the standard RECAP result. Use `GetLeaves()`, not `children` (first-level reaction products) or `GetAllChildren()` (all hierarchy nodes), when terminal fragments are desired.

## Prerequisites
- Python 3 with the `rdkit` package installed, for example with `pip install rdkit` if it is not already available.
- The source imports `rdkit.Chem` and `rdkit.Chem.rdChemReactions`.
- A valid RDKit `Mol` object. Normally obtain it with `Chem.MolFromSmiles` and reject `None`.

## Inputs
- `mol`: a sanitized RDKit `Mol`.
- Optional arguments to `RecapDecompose(mol, allNodes=None, minFragmentSize=0, onlyUseReactions=None)`:
  - `allNodes`: an optional dictionary reused across calls to share hierarchy nodes by canonical input SMILES.
  - `minFragmentSize`: when greater than 0, discard a product if its non-dummy heavy-atom count is less than this value.
  - `onlyUseReactions`: if given, an iterable of reaction indices to apply; all other reaction indices are skipped.

Even with default `minFragmentSize=0`, `RecapDecompose` applies a built-in small-fragment filter: a product is discarded when its SMILES, after removing `*` and then `()`, is one of `''`, `'C'`, `'CC'`, or `'CCC'`. This is independent of `minFragmentSize`.

## Outputs
- `root = Recap.RecapDecompose(mol)` is a `RecapHierarchyNode`.
- `root.GetLeaves()` returns a `dict` keyed by canonical fragment SMILES.
- Each key contains `*` dummy atoms at broken bonds; each value is a `RecapHierarchyNode` whose `.mol` is the isolated fragment Mol.
- The returned dictionary may be empty; see valid empty outcomes below.

## Normal path
Only one Python example is executable in this skill:

```python
from rdkit import Chem
from rdkit.Chem import Recap

smiles = 'C1CC1Oc1ccccc1-c1ncc(OC)cc1'
mol = Chem.MolFromSmiles(smiles)
if mol is None:
    raise ValueError(f'Invalid SMILES: {smiles!r}')

root = Recap.RecapDecompose(mol)
leaves = root.GetLeaves()
for fragment_smiles, node in leaves.items():
    fragment_mol = node.mol  # isolated fragment Mol with '*' dummy atoms

print(sorted(leaves.keys()))
```

Expected terminal leaf keys for this molecule (from the source doctest):
`['*C1CC1', '*c1ccc(OC)cn1', '*c1ccccc1*']`.
Sort keys before comparing because fragment SMILES order is not guaranteed.

## Result interpretation and checks
- Success: `leaves` is a dict; each key is a fragment SMILES, and each value's `.mol` is a valid RDKit `Mol`.
- Direct children: `root.children` gives first-level bond-break products (4 keys for the doctest molecule), not the terminal set.
- Full hierarchy: `root.GetAllChildren()` includes intermediate nodes (`*c1ccccc1-c1ccc(OC)cn1`, `*c1ccccc1OC1CC1`) that are not terminal fragments.
- Valid empty `GetLeaves()` outcomes include:
  - No reaction SMARTS matches the input under the selected/default reaction set, for example `C1CC=CC1` with the default decomposition returns no leaves.
  - The built-in default small-fragment filter drops all products even though a reaction matches, for example `CCCOCCC` with defaults: the ether reaction matches, but both `*CCC` products are removed by the default small-fragment rule.
  - `minFragmentSize` filters all products, for example `CCCOCC` with `minFragmentSize=3` returns no leaves.
  - Charged/protonated forms do not match the documented definitions, for example `c1ccccc1[n+]1ccccc1`.
- Invalid input: `Chem.MolFromSmiles` returns `None` for unparsable SMILES; pass a valid `Mol`, never `None`, to `RecapDecompose`.

## Reaction filtering
Indices accepted by `onlyUseReactions` in source order:
0 urea, 1 amide, 2 ester, 3 amines, 4 cyclic amines, 5 ether, 6 olefin, 7 aromatic N-aliphatic C, 8 lactam N-aliphatic C, 9 aromatic C-aromatic C, 10 aromatic N-aromatic C, 11 sulfonamide.
Index 10 is present but comments in the source note it is *not part of the standard RECAP set*; `RecapDecompose` applies it by default unless filtered with `onlyUseReactions`.

## License
This skill documents the RDKit `Recap.py` API. RDKit is BSD-3-Clause licensed; see [references/LICENSE.txt](references/LICENSE.txt).
