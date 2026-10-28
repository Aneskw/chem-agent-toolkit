---
name: rdkit-recap-terminal-fragments
description: >
  Use RDKit RECAP decomposition to retrieve terminal fragment nodes from a molecule and interpret an empty leaf dictionary.
---

# RDKit RECAP terminal fragments

Use `rdkit.Chem.Recap.RecapDecompose()` followed by `GetLeaves()` when you need the terminal nodes of a RECAP hierarchy. The returned leaves are a dictionary keyed by fragment SMILES; each value is a hierarchy node. This skill covers terminal fragments and empty leaf results, not traversal of the full hierarchy or configuration of decomposition reactions.

## Input & Output

Pass an RDKit molecule to `RecapDecompose(mol)`. The result is a hierarchy node. Call `result.GetLeaves()` to obtain a dictionary of terminal child nodes keyed by SMILES; access a leaf molecule through its node’s `.mol` attribute.

An empty dictionary means the hierarchy has no terminal child nodes. The source’s embedded tests include molecules for which decomposition returns a hierarchy with no children, so an empty result can be valid.

## Usage

Install the RDKit Python package in the Python environment that runs this code. The inspected source does not specify a required RDKit version.

```python
from rdkit import Chem
from rdkit.Chem import Recap

mol = Chem.MolFromSmiles('C1CC1Oc1ccccc1-c1ncc(OC)cc1')
result = Recap.RecapDecompose(mol)
leaves = result.GetLeaves()
assert len(leaves) == 3
leaf = leaves['*C1CC1']
leaf_molecule = leaf.mol
```

## Result Checks

Confirm that `RecapDecompose()` returned a hierarchy node and inspect `GetLeaves()` for the terminal fragment nodes. A nonempty leaf dictionary provides SMILES keys and nodes; use a node’s `.mol` when a molecule object is needed. If the dictionary is empty, interpret it as no terminal child nodes in the returned hierarchy. For example, the source test for `CCCOCCC` expects the root to have no children, hence no leaves.