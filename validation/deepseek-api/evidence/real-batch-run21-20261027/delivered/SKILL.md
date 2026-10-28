---
name: rdkit-recap-terminal-fragments
description: Decompose an RDKit molecule with RecapDecompose and return terminal RECAP fragments via GetLeaves. Use when a pre-built RDKit Mol must be split into RECAP leaves and terminal fragments must be distinguished from intermediate hierarchy nodes.
---

# RDKit RECAP terminal fragments

This skill packages the standard RDKit `Recap` terminal-fragment operation.
It takes an RDKit `Mol`, decomposes it into a `RecapHierarchyNode` tree, and
returns the terminal leaf fragments through `GetLeaves()`. Use
`GetAllChildren()` only when the caller needs the full hierarchy, including
intermediate nodes that are not terminal fragments.

## Prerequisites

- Python 3 with RDKit installed; the runtime imports are:

```text
from rdkit import Chem
from rdkit.Chem import Recap
```

- No external data files, model weights, or services.

## Inputs

| Name | Required | Meaning |
| --- | --- | --- |
| `mol` | yes | A valid RDKit `Mol` object built by e.g. `Chem.MolFromSmiles`. |
| `minFragmentSize` | no | Integer minimum count of non-dummy atoms per fragment; default `0`. |
| `onlyUseReactions` | no | Iterable of zero-based reaction indices to restrict cleavage reactions; default `None` means all built-in reactions. |

The input molecule must already exist. If using `Chem.MolFromSmiles`, check
for `None` before calling `RecapDecompose`; a SMILES parser failure is an
invalid input, not an empty result.

## Outputs

- `root`: a `RecapHierarchyNode` for the input molecule.
- `root.GetLeaves()`: dictionary keyed by canonical SMILES of terminal leaf
  nodes. Each leaf node has `.mol` and `.smiles`.
- `root.GetAllChildren()`: dictionary keyed by canonical SMILES of all
  descendant nodes, including intermediate nodes.
- `root.children`: direct child dictionary. A child with its own children is
  an intermediate node and appears in `GetAllChildren()` but not
  `GetLeaves()`.
- Empty dictionaries are valid. For example, propane-chain ether `CCCOCCC`
  returns a truthy root with `root.children == {}` under the default settings.

## Normal path

Use the delivered command-line runner for terminal leaves:

```text
python scripts/recap_leaves.py --smiles 'C1CC1Oc1ccccc1-c1ncc(OC)cc1'
```

Expected terminal leaves (one per line):

```text
*C1CC1
*c1ccc(OC)cn1
*c1ccccc1*
```

Equivalent Python API path:

```text
from rdkit import Chem
from rdkit.Chem import Recap

mol = Chem.MolFromSmiles('C1CC1Oc1ccccc1-c1ncc(OC)cc1')
if mol is None:
    raise ValueError('invalid SMILES')

root = Recap.RecapDecompose(mol)
leaves = root.GetLeaves()
print(sorted(leaves.keys()))
```

To inspect the full hierarchy rather than terminal leaves, either call
`root.GetAllChildren()` in Python or use `--mode all` with the delivered
script.

## Result interpretation and checks

- Terminal leaf keys are canonical RDKit SMILES containing dummy atom `*` at
  cleavage sites. Compare after RDKit canonicalization, not by hand-written
  exact strings in arbitrary order.
- A leaf is terminal only when `len(node.children) == 0`. Nodes with children
  are hierarchy intermediates; they may look like fragments but are not final
  RECAP results.
- `no terminal leaves` from the script is a valid empty decomposition, not an
  error. The same is true for `root.GetLeaves() == {}`.
- `Invalid SMILES` from the script means the input could not be parsed into a
  Mol and the exit status is non-zero.
- The operation is molecular fragmentation. It applies the documented RECAP
  reaction definitions and does not establish chemical or scientific validity
  beyond that algorithm.

## Boundaries

- Input is a pre-built RDKit `Mol`, not a raw SMILES string. The script wraps
  SMILES parsing for convenience, but Python callers must pass a `Mol`.
- `onlyUseReactions` indexes the source `reactionDefs` tuple. To view the
  mapping in an installed RDKit, use
  `from rdkit.Chem import Recap; print(Recap.reactionDefs)`, or inspect the
  upstream source noted in `references/source_note.md`.
- The source does not specify an exception type for passing `None` or an
  invalid `Mol` directly to `RecapDecompose`; do not rely on a particular
  exception from that call.

## License and source

The packaged API behavior comes from RDKit's `rdkit/Chem/Recap.py` under the
BSD 3-Clause license. See `references/LICENSE.txt` and
`references/source_note.md`.
