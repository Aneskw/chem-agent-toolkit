---
name: rdkit-recap-terminal-fragments
description: Decompose an RDKit molecule into RECAP terminal molecular fragments and return terminal leaf fragments as canonical SMILES with '*' attachment points. Use for standard RECAP terminal fragmentation, not descriptor calculation or full hierarchy traversal.
---

# RDKit RECAP terminal fragments

Prerequisites:
- Python 3.8+ and an RDKit installation where `from rdkit import Chem` works.
- The examples below come from the RDKit `rdkit/Chem/Recap.py` source at commit `237a1d9027c800784afed8788540f38a3aa595f8`; canonical SMILES can differ slightly across RDKit versions, so confirm outputs in the target environment.

Input and output:
- Input: a single SMILES string on the command line. The script parses it with `Chem.MolFromSmiles` and sanitizes it before calling `Recap.RecapDecompose`. A pre-sanitized RDKit `Mol` can also be passed directly when using the Python API; the caller must handle a `None`/invalid mol first.
- Output: one JSON object, `{"leaves": [<terminal fragment SMILES>, ...]}`. The list is sorted lexicographically; each key is the canonical product SMILES from RDKit with attachment points represented as `*` atoms. This is molecular fragmentation, not descriptor calculation.

Normal path:
```bash
python scripts/recap_leaves.py 'C1CC1Oc1ccccc1-c1ncc(OC)cc1'
```
```text
{"leaves": ["*C1CC1", "*c1ccc(OC)cn1", "*c1ccccc1*"]}
```

Direct API equivalent (shown for completeness; do not use as the package entry):
```text
from rdkit import Chem
from rdkit.Chem import Recap

mol = Chem.MolFromSmiles('C1CC1Oc1ccccc1-c1ncc(OC)cc1')
root = Recap.RecapDecompose(mol)
leaves = root.GetLeaves()   # dict SMILES -> RecapHierarchyNode
print(sorted(leaves.keys()))
```

Boundary: terminal vs hierarchy:
- `RecapDecompose` returns `RecapHierarchyNode`.
- `root.children` are immediate children; `root.GetAllChildren()` returns all descendants; only `root.GetLeaves()` returns terminal leaves. For the example above, immediate children count is 4, all descendants count is 5, terminal leaves count is 3. Use GetLeaves for standard RECAP terminal fragments.

Valid empty results:
- A valid empty result is `{"leaves": []}`, exit 0.
- This occurs when no permitted cleavable bond exists or all products are rejected by the small-fragment filter. Source examples include `CCCOCCC` default (no children), `C1CCCCO1` (ring-only ether has no leaves), and protonated forms such as `c1ccccc1[n+]1ccccc1`.
- The default small-fragment filter rejects products whose dummy-stripped SMILES is `''`, `'C'`, `'CC'`, or `'CCC'`. With `--min-fragment-size N`, it rejects products whose explicit atom count minus `*` dummy count is below N.

Optional controls:
- `--min-fragment-size N`: e.g. `CCCOCCC` with `--min-fragment-size 3` yields `{"leaves": ["*CCC"]}`.
- `--only-use-reactions 1,2`: comma-separated reaction-definition indices. Reaction 0 urea, 1 amide, 2 ester, 3 amines, 4 cyclic amines, 5 ether, 6 olefin, 7 aromatic N-aliphatic C, 8 lactam N-aliphatic C, 9 aromatic C-aromatic C, 10 aromatic N-aromatic C (not standard), 11 sulphonamide.

Failure signals:
- Exit 0 means decomposition completed, including empty leaves. Exit 2 means invalid SMILES or an RDKit error; the output is `{"error": "<message>"}`. Do not interpret error output as fragments.
- Execution and successful fragmentation are not chemical validation. The results are the documented RECAP algorithm outputs.

License:
- RDKit is BSD 3-Clause. See `references/LICENSE.txt`.
