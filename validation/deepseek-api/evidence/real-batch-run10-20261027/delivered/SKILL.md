---
name: rdkit-recap-terminal-fragments
description: Extract unique terminal molecular fragments from SMILES or RDKit molecules using RECAP. Use when terminal fragments, their attachment markers, or empty fragmentation results are needed, rather than molecular descriptors.
---

Use RDKit's existing RECAP decomposition with default rules. The delivered entry is [scripts/recap_fragments.py](scripts/recap_fragments.py); it adds input checks and JSON output, not new chemistry.

## Prerequisites and normal path

Use an authorized Docker container with Python 3 and RDKit already available, including `rdkit.Chem`, `rdkit.Chem.Recap` and `rdkit.Chem.rdChemReactions`. Do not install dependencies or run molecular processing on the host. No external dataset or model weights are required.

The source baseline is RDKit commit `237a1d9027c800784afed8788540f38a3aa595f8`; no released RDKit version was established from the supplied snapshot. Obtain RDKit through your approved environment provisioning process. The pinned [upstream implementation](https://raw.githubusercontent.com/rdkit/rdkit/237a1d9027c800784afed8788540f38a3aa595f8/rdkit/Chem/Recap.py) identifies the algorithm being wrapped; downloading that file alone does not supply RDKit's compiled dependencies. Record the installed RDKit version when comparing results.

From the skill directory inside that container, run this complete example:

```sh
python scripts/recap_fragments.py 'C1CC1Oc1ccccc1-c1ncc(OC)cc1'
```

Expected stdout is one JSON object:

```json
{"fragments": ["*C1CC1", "*c1ccc(OC)cn1", "*c1ccccc1*"]}
```

For another working directory, use the absolute path to the delivered script. The sole positional argument is one quoted SMILES string. The script writes no files. Exit 0 means decomposition completed, including when `fragments` is empty. `fragments` is a sorted list of unique terminal-fragment SMILES, not occurrence counts or a descriptor vector.

For an existing molecule, the underlying continuous Python path is:

```python
from rdkit import Chem
from rdkit.Chem import Recap

mol = Chem.MolFromSmiles('C1CC1Oc1ccccc1-c1ncc(OC)cc1')
if mol is None or mol.GetNumAtoms() == 0:
    raise ValueError('Expected a valid nonempty molecule')
root = Recap.RecapDecompose(mol)
leaves = root.GetLeaves()
fragment_smiles = sorted(leaves.keys())
fragment_molecules = [leaves[smi].mol for smi in fragment_smiles]
```

Replace the parsing step with an already sanitized, nonempty RDKit `Mol` when one is available. The script also exposes `terminal_fragments(mol)` for this use. Do not pass raw strings or `None` to `RecapDecompose`. The adapter does not strip salts, normalize tautomers or perform additional structure curation.

## Interpret results and failures

- `root.children` contains immediate children; `root.GetAllChildren()` includes intermediate descendants. Use `root.GetLeaves()` for terminal descendants. In the example above those three interfaces return 4, 5 and 3 distinct SMILES respectively.
- Preserve `*` dummy attachment atoms. These mark fragmentation attachment sites; deleting them changes the returned structures. Dictionary keys collapse repeated structures, so a leaf count is not a count of bond cleavages or fragment occurrences.
- An empty leaf set is valid. As an independent example, `python scripts/recap_fragments.py 'CCCOCCC'` returns `{"fragments": []}` with exit 0. Default filtering rejects small products here. A childless root does not appear in its own leaf dictionary; never substitute the unchanged parent for an empty result.
- Defaults matter: `minFragmentSize=0` still filters products reduced to empty, C, CC or CCC after dummy-marker removal. A positive minimum changes filtering; do not silently tune it to force results. Keep fresh default `allNodes` state and all default reactions for this workflow.
- The adapter rejects blank input, failed SMILES parsing and zero-atom molecules with exit 2 and a JSON `error` value (`empty_input`, `invalid_smiles`, or `empty_molecule`). RDKit may also emit parsing diagnostics on stderr. Missing or extra CLI arguments produce argparse diagnostics and exit 2. Dependency or decomposition failures are nonzero execution errors, not successful empty results. Non-string and unsanitized Python inputs are outside the supported input contract.

These outputs describe RDKit's RECAP implementation, not experimentally validated fragments, synthesis feasibility or chemical suitability. The source explicitly includes an aromatic nitrogen–aromatic carbon rule outside the standard RECAP set. For source locations, interpretation details and attribution, consult [references/source.md](references/source.md); redistribution notices are in [references/LICENSE.txt](references/LICENSE.txt).
