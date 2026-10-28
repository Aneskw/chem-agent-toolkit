---
name: rdkit-recap-terminal-fragments
description: Generate terminal RECAP molecular fragments from a valid RDKit molecule using RecapDecompose and return only the standard leaf fragments with GetLeaves. Select this when the task is RECAP fragmentation, not general descriptor calculation or non-RECAP fragmentation.
---

# RDKit RECAP terminal fragments

## Capability and boundary

This skill exposes RDKit's RECAP fragmentation (`rdkit.Chem.Recap`) for one coherent objective: decompose a sanitizable RDKit molecule and retrieve the terminal fragment set, i.e. the standard RECAP leaf fragments.

- Use `Recap.RecapDecompose(mol)` when the input is already a valid RDKit `Mol`.
- Use `root.GetLeaves()` for the standard terminal fragments. `root.children` is only one hierarchy level and `root.GetAllChildren()` includes intermediate hierarchy nodes; do not use them for the standard fragment set.
- The empty leaf dict is a valid result, not a failure, when no RECAP-cleavable bonds survive or only forbidden tiny fragments are produced.

Out of scope: descriptor calculation, non-RECAP fragmentation, and any chemical/scientific validity claim beyond the documented RECAP reactions in the inspected source.

## Prerequisites

- Python 3 with RDKit installed and importable. The package does not install dependencies.
- Inspected source snapshot: `rdkit/Chem/Recap.py` at commit `237a1d9027c800784afed8788540f38a3aa595f8` (BSD-3-Clause). Source: https://raw.githubusercontent.com/rdkit/rdkit/237a1d9027c800784afed8788540f38a3aa595f8/rdkit/Chem/Recap.py
- Full license text: `references/LICENSE.txt`.

## Inputs

- One or more SMILES strings that `Chem.MolFromSmiles` accepts and that `Chem.MolToSmiles(mol, 1)` can canonicalize.
- If `Chem.MolFromSmiles(smiles)` returns `None`, the SMILES is invalid for this skill. Hand it to the caller as an invalid-input error instead of passing `None` to `RecapDecompose`.
- Optional parameters:
  - `minFragmentSize` (default `0`): minimum non-dummy heavy-atom count for a product. It replaces the default tiny-fragment filter.
  - `onlyUseReactions`: a sequence of 0-based indices into the source `reactionDefs` tuple. Indices are specific to this source order and may differ in other RDKit versions.
  - `allNodes`: optional dictionary for cross-molecule fragment deduplication. The shipped CLI does not expose it; Python callers can pass it directly.

## Normal invocation

Run the single delivered script from the package root:

```text
python scripts/get_recap_leaves.py "C1CC1Oc1ccccc1-c1ncc(OC)cc1"
```

Expected terminal-fragment line:

```text
C1CC1Oc1ccccc1-c1ncc(OC)cc1	3	*C1CC1,*c1ccc(OC)cn1,*c1ccccc1*
```

JSON output is available with `--json`.

For interactive Python use:

```text
from rdkit import Chem
from rdkit.Chem import Recap
mol = Chem.MolFromSmiles("C1CC1Oc1ccccc1-c1ncc(OC)cc1")
root = Recap.RecapDecompose(mol)
leaves = root.GetLeaves()
for smi, node in leaves.items():
    print(smi, Chem.MolToSmiles(node.mol, 1))
```

The Python snippet above is shown in a text fence only; the executable delivery is the script under `scripts/`.

## Outputs

- The script prints one line per input: canonical input SMILES, leaf count, and comma-separated sorted leaf fragment SMILES.
- With `--json`, it prints `{canonical_input_smiles: [sorted_leaf_smiles]}`.
- In Python, `root.GetLeaves()` returns a dictionary keyed by fragment SMILES whose values are `RecapHierarchyNode` objects. Access fragment molecules with `node.mol`.

## Result interpretation and checks

- A non-empty leaf set means at least one RECAP reaction cleaved the molecule into accepted terminal fragments.
- An empty leaf set or a `0` count is a valid negative, for example:
  - `CCCOCCC` produces no children and no leaves because default filtering rejects tiny products.
- `--min-fragment-size N` changes the acceptance filter. Example: `--min-fragment-size 3` applied to `CCCOCCC` yields `*CCC`.
- The script exits non-zero and prints an error when any SMILES is invalid.
- Inspect the returned fragment SMILES after execution; success is an API/result-shape check, not scientific validation.

## Reaction-index caveat

`--only-use-reactions` takes comma-separated integer indices, e.g. `--only-use-reactions 0,1`. They are positional indices in the source `reactionDefs` tuple. Do not assume these indices are stable across RDKit versions.
