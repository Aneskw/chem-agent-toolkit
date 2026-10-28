---
name: rdkit-recap-terminal-fragments
description: Get terminal RECAP molecular fragments from a valid sanitized RDKit Mol. Use when the task needs leaf-node RECAP fragments as canonical SMILES with dummy '*' cut markers and valid empty results, not descriptor calculation or all intermediate hierarchy nodes.
---

# RDKit RECAP terminal fragments

This skill returns terminal (leaf) RECAP fragments for one sanitized RDKit molecule. It calls `rdkit.Chem.Recap.RecapDecompose` and then `GetLeaves()` on the returned `RecapHierarchyNode`. It is molecular fragmentation, not descriptor calculation; the upstream reaction tuple, hierarchy, and filtering rules are used unchanged.

## Boundary that changes interpretation

The inspected RDKit `Recap.py` reaction tuple contains an aromatic nitrogen - aromatic carbon cleavage at index 10. The source comment marks it `*NOTE* this is not part of the standard recap set.` Because `RecapDecompose` loops over the full tuple when `onlyUseReactions` is omitted, this upstream implementation applies index 10 by default. Use `--only-use-reactions` or the Python `onlyUseReactions` argument to select an explicit reaction subset.

## Prerequisites

- Python 3 with RDKit importable:
  ```python
  from rdkit import Chem
  from rdkit.Chem import Recap
  ```
- A valid sanitized RDKit `Mol`. The normal CLI path parses with `Chem.MolFromSmiles`; `None` means invalid/unparseable SMILES.

## Inputs and outputs

Input: one SMILES string.
Optional CLI inputs:
- `--min-fragment-size N`: discard products whose explicit non-dummy atom count is less than `N`.
- `--only-use-reactions LIST`: comma-separated zero-based reaction indices.

Output: one JSON object printed to stdout:
```
{"input_smiles": "<input>", "leaves": {"<canonical_fragment_smiles>": "<same canonical_fragment_smiles>"}}
```
`leaves` maps each terminal fragment's canonical SMILES to itself. Use `leaves.keys()` to iterate fragments. A `*` atom is a dummy atom marking the cut site, not a real atom type. The `leaves` value is the same canonical SMILES because the script serializes each leaf `node.mol` with `Chem.MolToSmiles(..., 1)`.

## Normal path

From the skill root, run:

```bash
python scripts/recap_leaves.py "C1CC1Oc1ccccc1-c1ncc(OC)cc1"
```

Expected stdout:

```json
{"input_smiles": "C1CC1Oc1ccccc1-c1ncc(OC)cc1", "leaves": {"*C1CC1": "*C1CC1", "*c1ccc(OC)cn1": "*c1ccc(OC)cn1", "*c1ccccc1*": "*c1ccccc1*"}}
```

Direct Python use:

```python
from rdkit import Chem
from rdkit.Chem import Recap

mol = Chem.MolFromSmiles("C1CC1Oc1ccccc1-c1ncc(OC)cc1")
if mol is None:
    raise ValueError("invalid SMILES")
hierarchy = Recap.RecapDecompose(mol)
leaves = hierarchy.GetLeaves()
# leaves maps canonical fragment SMILES -> RecapHierarchyNode
# fragment_mol = leaves["*C1CC1"].mol
```

Repeated Python decompositions may share `allNodes` by passing a dict to `RecapDecompose` or to the script's `terminal_fragment_smiles` function; the CLI does not expose this in-memory cache.

Optional filtering examples:

```bash
python scripts/recap_leaves.py "CCCOCCC" --min-fragment-size 3
python scripts/recap_leaves.py "C1CC1C(=O)NC1OC1" --only-use-reactions 1
```

## Reaction index table

| Index | Reaction |
| ---: | --- |
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
| 10 | aromatic nitrogen - aromatic carbon (source marks as not standard) |
| 11 | sulphonamide |

## Result interpretation and checks

- Exit 0 means `RecapDecompose` returned a hierarchy, but `leaves` may be empty. Empty is a valid, meaningful outcome.
- Valid empty examples:
  - `CCCOCCC` — no terminal leaves under default small-fragment rejection.
  - `C1CC1C(=O)CC1OC1 --only-use-reactions 1` — amide reaction has no matching product in this input.
- Exit 1 means the SMILES could not be parsed or `RecapDecompose` raised an exception; a message is written to stderr.
- Do not treat `*` atoms as wildcards or real atoms in downstream property calculation; they are bond-cut markers.
- This skill does not validate chemical plausibility beyond RDKit's sanitization and RECAP filtering.

## Packaged source

The implementation is grounded in RDKit `rdkit/Chem/Recap.py` at commit `237a1d9027c800784afed8788540f38a3aa595f8` (BSD 3-Clause). `references/LICENSE.txt` contains the license. `scripts/recap_leaves.py` adds only SMILES input validation and JSON output around the upstream calls.
