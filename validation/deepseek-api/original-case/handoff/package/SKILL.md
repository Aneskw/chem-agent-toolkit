---
name: rdkit-recap-terminal-fragments
description: Obtain unique terminal molecular fragments with RDKit RECAP from SMILES or an RDKit molecule, and interpret empty results and hierarchy levels. Use for molecular fragmentation, not descriptor calculation.
---

# RDKit RECAP terminal fragments

Use Python with RDKit already available, including `rdkit.Chem`, `rdkit.Chem.Recap` and reaction support. Run business code only inside an authorized Docker container; do not install dependencies or run it on the host. No external dataset is needed.

The source baseline is RDKit commit `237a1d9027c800784afed8788540f38a3aa595f8`, [Recap.py](https://github.com/rdkit/rdkit/blob/237a1d9027c800784afed8788540f38a3aa595f8/rdkit/Chem/Recap.py). The exact source can be obtained from that repository at that commit; a standalone copy of Recap.py does not replace an installed RDKit. No minimum release or compatibility across releases is established here. Record `rdkit.__version__` when reporting reproducibility.

## Normal path

Input is one nonempty SMILES string parsed with normal RDKit sanitization. This continuous example uses the upstream demonstration by default. Save this Python block as `terminal_fragments.py` in your working directory inside the container, then run `python terminal_fragments.py` or `python terminal_fragments.py 'CCCOCCC'` there. A single quoted argument supplies an alternative molecule.

```python
import json
import sys
from rdkit import Chem
from rdkit.Chem import Recap

smiles = sys.argv[1] if len(sys.argv) == 2 else 'C1CC1Oc1ccccc1-c1ncc(OC)cc1'
if len(sys.argv) > 2 or not smiles.strip():
    raise SystemExit('Provide exactly one nonempty SMILES argument, or no arguments for the example.')
try:
    mol = Chem.MolFromSmiles(smiles)
except Exception as exc:
    raise SystemExit(f'SMILES parsing failed: {exc}')
if mol is None or mol.GetNumAtoms() == 0:
    raise SystemExit('SMILES did not produce a nonempty molecule.')
root = Recap.RecapDecompose(mol)
leaves = root.GetLeaves()
print(json.dumps(sorted(leaves)))
```

Stdout is a JSON array of unique terminal-fragment SMILES, sorted for stable presentation. The default example returns `["*C1CC1", "*c1ccc(OC)cn1", "*c1ccccc1*"]` (source lines 38–56). Preserve `*`: these are dummy attachment atoms introduced by the fragmentation rules, not text to clean away.

For an existing valid, sanitized RDKit `Mol`, begin directly at `root = Recap.RecapDecompose(mol)`. `leaves` maps fragment SMILES to `RecapHierarchyNode` objects; obtain a fragment molecule with `leaves[fragment_smiles].mol`. Keep the root if also inspecting parent relationships. The JSON output does not serialize molecule objects or the hierarchy. Parsing/serialization and the explicit nonempty-input guard above are adapter behavior, not new chemistry rules.

## Interpret the result

- `root.children` contains immediate children; `root.GetAllChildren()` contains all descendants; `root.GetLeaves()` contains only terminal descendants. The example has 4 immediate children, 5 descendants and 3 leaves. Do not substitute one collection for another.
- Keys deduplicate fragments by SMILES. Their count is neither fragment multiplicity nor a count of cleavage events. Sorting controls presentation only.
- `[]` is successful when no terminal descendants are retained. The root is not returned as its own leaf. `CCCOCCC` returns no fragments under default settings; the source also explicitly tests zero leaves for `C1CNS(=O)(=O)CC1`. A valid empty result does not prove there are no potentially cleavable bonds: reaction matching and product filters both affect the output.
- Failed parsing, absent RDKit, or decomposition exceptions are failures, not empty fragment sets. The example exits nonzero on failure; RDKit diagnostics may appear on stderr. Do not replace an exception with `[]`. Arbitrary objects, `None` and unsanitized molecules are outside this workflow's input contract; this source does not specify exhaustive parser exception behavior.

Use a fresh default decomposition per independent input. Passing shared `allNodes` creates shared hierarchy state and may return a previously stored root before applying new settings (lines 146–158).

Keep default parameters for the normal path. If a user explicitly needs size filtering, `RecapDecompose(mol, minFragmentSize=3)` compares product atom counts after excluding dummy atoms; it replaces the default special rejection of empty/methyl/ethyl/propyl fragments, rather than simply adding a stricter filter. For `CCCOCCC`, that setting gives one unique leaf, `*CCC` (lines 180–195 and 279–302). A rejected small product can disqualify its whole product sequence. Reaction subsets and custom rules are outside this skill's normal path.

These are results of the supplied RDKit implementation. Its reaction definitions include an aromatic nitrogen–aromatic carbon rule explicitly marked as outside standard RECAP (lines 81–82). Successful execution establishes neither synthetic feasibility nor chemical/scientific validation.

## Source grounding

Recap.py lines 31–56 provide the overview and example; lines 97–118 and 134–138 define terminal traversal; lines 146–213 implement decomposition and filtering. Tests at lines 223–235, 279–302 and 574–605 support the hierarchy counts and valid empty results. Algorithm attribution: Lewell et al., JCICS 38, 511–522 (1998), as cited by the implementation; the paper itself was not inspected. See [license notices](references/LICENSE.txt) for the source notices accompanying the adapted example.