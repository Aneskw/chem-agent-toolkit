---
name: rdkit-recap-terminal-fragments
description: Extract unique terminal molecular fragments with RDKit RECAP when a task needs fragment SMILES or molecule objects, including correct interpretation of empty results and hierarchy levels. Not for descriptor calculation.
---

# RDKit RECAP terminal fragments

Use `Recap.RecapDecompose(mol).GetLeaves()` for terminal fragments under RDKit's default RECAP rules. This is an algorithmic decomposition, not a prediction of synthetic feasibility or experimental products.

## Prerequisites and normal path

Use Python 3 with an existing RDKit installation exposing `rdkit.Chem` and `rdkit.Chem.Recap`. Execute only inside an authorized Docker container; do not install dependencies or run this computation on the host. Missing RDKit is a setup failure, not an empty fragmentation result.

The source reference is RDKit commit `237a1d9027c800784afed8788540f38a3aa595f8`; a corresponding release version is not established by the supplied source. Use a compatible installed RDKit and record its version when reproducibility matters. Source acquisition links and exact behavioral passages are in [references/source.md](references/source.md); no source download is needed at runtime.

Inside the container, from this skill's directory, run the delivered entry:

```sh
python scripts/terminal_fragments.py 'C1CC1Oc1ccccc1-c1ncc(OC)cc1'
```

Expected stdout is one JSON object:

```json
{"fragments": ["*C1CC1", "*c1ccc(OC)cn1", "*c1ccccc1*"]}
```

Replace the quoted argument with the input SMILES. No input or output files are needed. The entry emits sorted, unique terminal SMILES; order is a serialization convention, not a chemical ranking. Keep `*` dummy attachment atoms intact.

The script imports `Chem` from `rdkit` and `Recap` from `rdkit.Chem`, parses with `Chem.MolFromSmiles`, then calls `Recap.RecapDecompose(mol)` and `root.GetLeaves()`. For in-process use, its `terminal_leaves(smiles)` function returns the original dictionary of nodes: use `leaves[smi].mol` for the RDKit molecule and `sorted(leaves)` for SMILES. Molecule objects are not serialized by the CLI.

## Input and failure boundaries

Supply one nonempty SMILES string accepted by RDKit's default parser. The wrapper rejects blank strings, parse failures and zero-atom molecules with exit 2 and a JSON `error`; RDKit may additionally emit diagnostic text on stderr. These guards are interface choices, not RECAP chemistry rules. Missing arguments are argparse errors on stderr. Unexpected decomposition errors remain nonzero failures and are never converted into empty fragments.

The entry performs no salt stripping, tautomer normalization, charge adjustment or other explicit standardization. Disconnected structures and unusual chemistry have no additional validity guarantee here; do not silently choose a component or infer chemical suitability from parsing success. Existing RDKit Mol objects can be passed directly to the upstream API after appropriate caller validation; the CLI accepts only SMILES.

## Interpret the result

- `root.children` contains immediate products. `root.GetAllChildren()` includes intermediate descendants. `root.GetLeaves()` includes only terminal descendants, excluding the input root.
- SMILES keys deduplicate nodes: the output is a set-like collection, not fragment counts, a stoichiometric equation or a partition of the input atoms.
- An empty list with exit 0 is valid. For example, the independent input `CCCOCCC` produces `{"fragments": []}` with defaults. Do not substitute the input molecule. The source filters certain small products, so empty does not prove the absence of chemically cleavable bonds.
- Keep default `allNodes=None` for independent inputs. Shared dictionaries can reuse an existing hierarchy. Changing `minFragmentSize` or `onlyUseReactions` changes the result and is outside this entry's default workflow.
- This RDKit implementation includes a rule explicitly marked outside the standard published RECAP set. Describe results as RDKit RECAP outputs, not exact reproduction or validation of the paper.

For provenance, filter details or redistribution, consult [source notes](references/source.md) and [BSD notices](references/LICENSE.txt).
