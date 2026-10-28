---
name: rdkit-recap-terminal-fragments
description: Obtain unique terminal molecular fragments with RDKit RECAP when a task needs RecapDecompose/GetLeaves results, including correct interpretation of empty decompositions and terminal versus intermediate fragments. Use for molecular fragmentation, not descriptors.
---

Use RDKit's default RECAP reactions to decompose one molecular SMILES into terminal descendant fragments. The adapter returns unique fragment SMILES, not fragment occurrence counts or a full hierarchy.

## Run

Prerequisites: Python 3 with RDKit, including `rdkit.Chem` and `rdkit.Chem.Recap`, already available in the approved Docker container. Run business code only in that container. This package neither installs dependencies nor provisions an environment. The inspected implementation is RDKit commit `237a1d9027c800784afed8788540f38a3aa595f8`; compatibility with other versions must be checked against the examples below. No release version is inferred from the commit.

From this skill's directory inside the container, run the single entry:

```sh
python scripts/recap_fragments.py --smiles 'C1CC1Oc1ccccc1-c1ncc(OC)cc1'
```

Expected stdout, with exit status 0:

```json
{"fragments": ["*C1CC1", "*c1ccc(OC)cn1", "*c1ccccc1*"]}
```

Replace the quoted value with the user's molecular SMILES. Supply only a SMILES string, not a filename, molecule name, reaction SMARTS, or a batch of records. Quote it to protect shell metacharacters. No input file is mutated and no output file is written.

The implementation imports `Chem` from `rdkit` and `Recap` from `rdkit.Chem`, parses with `Chem.MolFromSmiles`, then calls `root = Recap.RecapDecompose(mol)` and `sorted(root.GetLeaves().keys())`. It leaves `allNodes`, `minFragmentSize`, and `onlyUseReactions` at defaults, so each invocation constructs an independent hierarchy. The adapter only adds input guards, sorting, and JSON serialization.

## Interpret the result

- `fragments` is a sorted list of unique terminal-fragment SMILES. Keep `*` dummy atoms: they represent cleavage attachment points in the reaction definitions. Do not strip them to turn fragments into supposedly complete molecules.
- `root.children` contains immediate children; `root.GetAllChildren()` includes intermediate and terminal descendants. `root.GetLeaves()` contains only terminal descendants keyed by SMILES, with node objects as values. A node's `.mol` exposes its RDKit molecule. The normal example has four immediate children, five descendants, and three leaves.
- A valid empty result is `{"fragments": []}` with exit status 0. For an independent example, use `--smiles 'CCCOCCC'`: the source tests show no accepted children under the defaults. `GetLeaves()` does not insert an unchanged parent when no children exist. Empty results can reflect product filtering, not just absence of a matching cleavage.
- Default filtering excludes certain small products. Changing `minFragmentSize` changes that filtering and may change emptiness; this adapter intentionally exposes the default workflow only.

Blank input, parsing failure, or a zero-atom molecule produces an `invalid_input` JSON error and exit status 2. Missing arguments are reported by argparse on stderr with status 2. Dependency/import or decomposition failures produce a `runtime_error` JSON error with status 1; loader failures may also produce a Python traceback. RDKit may emit diagnostic messages on stderr. Check exit status before treating stdout as a successful fragment result; never substitute an empty list for an error.

A successful call demonstrates execution of RDKit's implemented rules, not chemical feasibility, synthetic accessibility, or scientific validation. The inspected implementation includes a reaction explicitly marked outside the standard RECAP set, so do not claim exact equivalence to every detail of the original publication.

For original source acquisition, the inspected passages, and algorithm/version attribution, consult [sources.md](references/sources.md). When redistributing source-derived material, retain the [upstream notices](references/LICENSE.txt).
