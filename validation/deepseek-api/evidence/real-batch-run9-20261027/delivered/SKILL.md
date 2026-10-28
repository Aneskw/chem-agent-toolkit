---
name: rdkit-recap-terminal-fragments
description: Extract terminal molecular fragments with RDKit RECAP when a task needs unique fragment SMILES or fragment molecules, including correct interpretation of empty decompositions. Use for molecular fragmentation, not descriptor calculation.
---

# RECAP terminal fragments

Use RDKit's `Recap.RecapDecompose(mol)` followed by `root.GetLeaves()` to obtain terminal fragments under its default reaction and filtering rules. This packages an existing algorithm; fragment output does not establish synthetic feasibility or scientific validity.

## Prerequisites and input

Use an existing Python 3 environment with RDKit, including `rdkit.Chem` and `rdkit.Chem.rdChemReactions`. Execute chemistry only inside the permitted Docker container; do not install dependencies or run chemistry on the host. The source baseline is RDKit commit `237a1d9027c800784afed8788540f38a3aa595f8`, not a tested release requirement. The command reports the installed RDKit version; compatibility must be checked against the example below. No external data files are needed.

Supply one SMILES string representing a nonempty molecule. The adapter rejects blank strings, parsing failure and zero-atom molecules. These are input-handling rules, not a claim of chemical validation. It performs no desalting, tautomer normalization or other standardization; the molecule parsed by RDKit is the input to RECAP.

## Normal path

From the skill directory inside the container, run this independent example (replace the quoted SMILES for another input):

```sh
python scripts/recap_terminal.py --smiles 'C1CC1Oc1ccccc1-c1ncc(OC)cc1'
```

The single executable entry is [scripts/recap_terminal.py](scripts/recap_terminal.py). It imports `Chem` and `Recap` from RDKit, parses with `Chem.MolFromSmiles`, checks the input, calls `Recap.RecapDecompose(mol)` with defaults, then returns `root.GetLeaves()`. Each invocation creates an independent decomposition; it does not share `allNodes` state.

Successful stdout is one JSON object with `fragments` (a sorted list of unique SMILES) and `rdkit_version` (the installed version). It writes no files. For the example, `fragments` must be:

```json
["*C1CC1", "*c1ccc(OC)cn1", "*c1ccccc1*"]
```

For in-process use, the delivered module's `terminal_leaves(smiles)` returns RDKit's dictionary of SMILES to hierarchy nodes. Obtain a fragment molecule with `leaves[smi].mol`; molecules are not serialized in the CLI JSON. The function raises `ValueError` for its input boundary failures. See the linked script for the complete importable implementation.

## Interpretation and failure outcomes

- `root.children` describes immediate products; `root.GetAllChildren()` includes intermediate and terminal descendants; `root.GetLeaves()` includes only descendant nodes with no children. In the source example these have counts 4, 5 and 3 respectively. The root is not itself returned as a leaf.
- Dictionary keys identify unique fragment structures, not counts of fragment occurrences or a stoichiometric product list. Preserve `*` dummy attachment atoms in the returned SMILES.
- `CCCOCCC` yields `fragments: []` with defaults. This is a successful empty decomposition, not invalid input; never replace it with the original molecule. Empty output can reflect the filtering rules, not simply absence of a cleavable bond.
- The default `minFragmentSize=0` still filters products: after removing dummy markers and empty branches, the implementation excludes empty, C, CC and CCC fragments. Changing size or reaction settings changes the result; this entry deliberately exposes only defaults.
- RDKit includes an aromatic nitrogen-aromatic carbon cleavage explicitly marked as outside the standard RECAP set. Describe output as this RDKit implementation's RECAP fragments, not exact reproduction of every published rule.

The CLI exits 0 for a computed result, including an empty list. Invalid input exits 2 with a JSON `error` of `invalid_input` on stdout; RDKit may also emit parsing diagnostics on stderr. A missing RDKit import exits 1 with `dependency_unavailable`; a decomposition exception exits 1 with `decomposition_failed`. Do not reinterpret these failures as an empty fragment set. Wrong CLI arguments use argparse's stderr usage message and exit 2.

For source acquisition, exact passage references and version caveats, consult [references/source.md](references/source.md). When redistributing the source-derived examples, retain [references/LICENSE.txt](references/LICENSE.txt).