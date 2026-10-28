---
name: rdkit-recap-terminal-fragments
description: Obtain unique terminal RECAP molecular fragments from SMILES with RDKit, distinguishing leaf fragments from the full hierarchy and recognizing valid empty results. Use for molecular fragmentation, not descriptor calculation.
---

# RECAP terminal molecular fragments

Use RDKit's existing RECAP implementation to decompose one molecule and report its unique terminal fragment SMILES. This implements RDKit's rules; it does not establish synthetic feasibility or chemical validity beyond that algorithm.

## Prerequisites and invocation

Use Python 3 with `rdkit.Chem` and `rdkit.Chem.Recap` already available in the authorized Docker container. Do not install dependencies or execute this workflow on the host. The implementation reference is RDKit commit `237a1d9027c800784afed8788540f38a3aa595f8`; no particular installed release has been verified against it. Obtain the implementation for inspection from the [pinned upstream source](https://raw.githubusercontent.com/rdkit/rdkit/237a1d9027c800784afed8788540f38a3aa595f8/rdkit/Chem/Recap.py), not a pipeline cache. Use an existing RDKit distribution for execution; the standalone module is not the complete dependency.

From this skill directory inside the container, run the delivered entry with one quoted SMILES argument:

```sh
python scripts/recap_terminal.py 'C1CC1Oc1ccccc1-c1ncc(OC)cc1'
```

The entry imports `from rdkit import Chem` and `from rdkit.Chem import Recap`, parses with `Chem.MolFromSmiles`, checks for a valid nonempty molecule, calls `root = Recap.RecapDecompose(mol)` with defaults, then returns `sorted(root.GetLeaves().keys())`. Each call uses fresh decomposition state. It writes no files.

The example produces this JSON (spacing is immaterial):

```json
{"fragments": ["*C1CC1", "*c1ccc(OC)cn1", "*c1ccccc1*"], "count": 3}
```

Replace the example argument with the user's SMILES. Blank strings, failed parsing and zero-atom molecules are rejected by this adapter. It does not normalize salts, select components or perform tautomer standardization. A disconnected SMILES, if parsed, is passed to RDKit unchanged as one Mol. Keep input identity separately if needed; output fragments are transformed structures.

## Interpret the result

- `fragments` is a sorted list of unique terminal fragment SMILES; `count` is its length, not an occurrence count. Preserve `*` dummy attachment atoms.
- `GetLeaves()` returns a dictionary keyed by SMILES whose values are hierarchy nodes; each node has `.mol`. The root is excluded. `root.children` gives immediate children; `root.GetAllChildren()` includes intermediate descendants. These are different outputs: the example has four immediate children, five descendants and three leaves.
- Exit 0 with `{"fragments": [], "count": 0}` is a valid result. For example, the independent input `CCCOCCC` has no accepted decomposition under defaults. Do not substitute the parent or conclude that the molecule is invalid.
- Terminal means no further accepted children under the selected implementation and filters. Defaults exclude certain small fragments. Changing `minFragmentSize` changes that behavior: the source test for `CCCOCCC` with size 3 gives one unique `*CCC`. This adapter deliberately uses defaults and exposes no tuning flags.
- Input failures produce JSON with `error: "invalid_input"` and exit 2. Missing dependencies or decomposition exceptions produce JSON with `error: "runtime_error"` and exit 1. Both include `message`; they are not successful empty results. CLI argument errors use argparse's stderr and exit 2. RDKit may also write diagnostics to stderr; interpret the exit code and stdout JSON together.

Source assertions provide useful comparison cases, not evidence that this installation has been tested. The pinned implementation includes an aromatic nitrogen–aromatic carbon rule explicitly marked as outside the standard RECAP set; do not claim exact identity with the original published algorithm.

For provenance, inspect the linked upstream module: overview/example at lines 31–56; hierarchy traversal at 97–138; decomposition and filtering at 146–213; example and empty-result tests at 223–235 and 279–302. The module attributes RECAP to Lewell et al., JCICS 38, 511–522 (1998). Consult [the retained upstream notices](references/LICENSE.txt) when redistributing copied examples or source-derived material.