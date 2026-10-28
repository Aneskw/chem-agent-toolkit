---
name: rdkit-recap-terminal-fragments
description: Use when extracting unique terminal molecular fragments with RDKit RECAP from SMILES, especially when distinguishing leaves from intermediate hierarchy nodes or interpreting empty results.
---

# RDKit RECAP terminal fragments

Use RDKit's existing RECAP implementation to obtain terminal fragments. This is molecular fragmentation, not descriptor calculation or a prediction of synthetic feasibility.

## Prerequisites and invocation

Use Python 3 with RDKit already installed, including `rdkit.Chem`, `rdkit.Chem.Recap` and `rdkit.Chem.rdChemReactions`. Run molecular code only inside an authorized Docker container; this package does not provision an environment or install dependencies.

The source baseline is RDKit commit `237a1d9027c800784afed8788540f38a3aa595f8`. The [original Recap.py](https://raw.githubusercontent.com/rdkit/rdkit/237a1d9027c800784afed8788540f38a3aa595f8/rdkit/Chem/Recap.py) is available directly at that pinned address. Use an RDKit build providing this behavior; compatibility with other versions has not been executed or established. Do not substitute the downloaded module alone for the RDKit dependency.

From this skill directory in the container, run the single delivered entry:

```sh
python scripts/terminal_fragments.py 'C1CC1Oc1ccccc1-c1ncc(OC)cc1'
```

It prints this JSON array to stdout and exits 0:

```json
["*C1CC1", "*c1ccc(OC)cn1", "*c1ccccc1*"]
```

Supply one quoted SMILES argument. The script imports `Chem` and `Recap`, parses with `Chem.MolFromSmiles`, then uses `root = Recap.RecapDecompose(mol)` and `leaves = root.GetLeaves()`. It returns `sorted(leaves.keys())`. There are no output files and no shared decomposition cache.

Input must parse to a molecule with at least one atom. Blank input, failed parsing and zero-atom input are rejected with exit 2 and a message on stderr, rather than returning an empty fragment list. Those checks are wrapper input handling, not chemical validity criteria. Missing dependencies and decomposition exceptions fail with a nonzero exit; do not reinterpret them as an empty result.

Disconnected SMILES are passed to RDKit as parsed: the wrapper does not remove salts, select a largest component, standardize charges or normalize tautomers. If such preparation is needed, decide it separately and record the transformed input. This skill makes no special guarantee about disconnected-input interpretation beyond passing the molecule to the upstream method.

## Interpret the result

- `GetLeaves()` returns a dictionary keyed by fragment SMILES, with `RecapHierarchyNode` values. For in-memory use, `leaves[smi].mol` gives the fragment molecule. The CLI serializes only the unique keys; it does not report occurrence counts or cleavage paths.
- Preserve `*` dummy attachment atoms. Removing them changes the fragment representation.
- `root.children` contains direct children. `root.GetAllChildren()` includes intermediate and terminal descendants. Neither is a substitute for `root.GetLeaves()`: the example above has 4 direct children, 5 descendants and 3 leaves.
- Leaves exclude the original root. If the root has no children, the result is `[]`, not the input molecule. With default settings, `CCCOCCC` is a documented successful empty case. Empty output means no retained terminal descendants under these rules and filters; it is not evidence of an invalid molecule or the absence of all conceivable cleavages.
- The entry uses default `minFragmentSize=0` and all built-in reactions. Default filtering rejects certain small products. A positive size threshold changes that filtering branch: the source test obtains `*CCC` from `CCCOCCC` with `minFragmentSize=3`. Do not silently change options to force a nonempty result.

These are algorithm outputs, not chemical or scientific validation. The source attributes RECAP to Lewell et al., JCICS 38, 511–522 (1998), but explicitly marks its aromatic nitrogen–aromatic carbon rule as outside the standard RECAP set.

## Source basis

The pinned Recap.py overview and example (lines 31–56), `GetLeaves` (110–118), decomposition/filtering (146–213), and tests `test1`, `test2`, `testMinFragmentSize` (223–298) support the invocation and interpretation above. The reaction definitions and extra-rule note are at lines 67–83. Example expectations are source-derived, not results of execution during authoring.

[LICENSES.txt](LICENSES.txt) preserves upstream notices for the adapted usage material and examples.