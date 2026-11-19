---
name: rdkit-compare-natural-product-likeness-and-qed
description: Calculate and compare RDKit natural-product-likeness and QED distributions for curated compound collections and supplied reference sets, retaining identifiers and NP fragment coverage.
---

# Compare natural-product and drug likeness

Use two complementary descriptors to characterize collections: NP-likeness measures resemblance to natural-product fragments, while QED summarizes drug-like molecular properties. Start with curated structures and collection labels; reference-set acquisition and salt, protonation, tautomer and explicit-hydrogen policies are supplied preparation. Apply the same preparation across collections. Neither descriptor measures biological efficacy.

## Setup and resources

Use **RDKit 2026.09.1** (PyPI version `2026.9.1`). A representative supported environment is 64-bit CPython 3.11 on Windows; matching wheels are also published for Linux and macOS. Follow the [official installation guide](https://www.rdkit.org/docs/Install.html); in the intended Python environment, the pinned installation is:

```console
python -m pip install rdkit==2026.9.1
```

Obtain these two files from the official [Release_2026_09_1 NP_Score directory](https://github.com/rdkit/rdkit/tree/Release_2026_09_1/Contrib/NP_Score), saving both in `NP_Score/` under the working directory:

- [npscorer.py](https://raw.githubusercontent.com/rdkit/rdkit/Release_2026_09_1/Contrib/NP_Score/npscorer.py)
- [publicnp.model.gz](https://raw.githubusercontent.com/rdkit/rdkit/Release_2026_09_1/Contrib/NP_Score/publicnp.model.gz), kept as the original binary gzip file.

Keep the scorer and model from this same tag. `readNPModel()` loads the compressed pickle model; obtain it from the official source above. QED is included in RDKit.

## Inputs and result files

The normal path uses UTF-8 `compounds.csv` with these columns:

| Column | Meaning |
| --- | --- |
| `compound_id` | Nonempty identifier, unique within its collection |
| `collection` | Nonempty query/reference collection label |
| `smiles` | Curated SMILES; no 3D coordinates required |

For example, this illustrative format is not a reference dataset:

```csv
compound_id,collection,smiles
q1,query,CCOc1ccccc1
r1,reference,CC(=O)Oc1ccccc1C(=O)O
```

For SDF input instead, iterate `Chem.SDMolSupplier(path)`, handle `None` records, and obtain identifiers and collection labels from declared SD properties or an external mapping. Feed the valid molecules into the same scoring calls below; do not infer collection labels from chemistry.

The example writes `likeness.csv` with one row per input record, including failures, and `likeness-ecdf.csv` containing empirical cumulative distributions for valid scores. Existing files at these paths are overwritten. Input files and original SMILES strings are retained unchanged.

## Score and compare collections

Run the following Python example from the directory containing `compounds.csv` and `NP_Score/`. It loads the NP model once and uses QED's default average descriptor weights.

```python
import csv
import sys
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path
from rdkit import Chem, rdBase
from rdkit.Chem import QED

np_dir = Path('NP_Score').resolve()
sys.path.insert(0, str(np_dir))
import npscorer

model = npscorer.readNPModel(str(np_dir / 'publicnp.model.gz'))
rows = []
groups = defaultdict(list)
seen = set()
with open('compounds.csv', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    required = {'compound_id', 'collection', 'smiles'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('Required columns: compound_id, collection, smiles')
    for line, src in enumerate(reader, start=2):
        row = {k: src[k] or '' for k in required}
        row.update(input_line=line, rdkit_version=rdBase.rdkitVersion,
                   np_score='', np_coverage='', qed='', status='ok')
        key = (row['collection'], row['compound_id'])
        if any(not row[k].strip() for k in required):
            row['status'] = 'missing_input'
        elif key in seen:
            raise ValueError(f'Duplicate collection/identifier at line {line}')
        else:
            seen.add(key)
            mol = Chem.MolFromSmiles(row['smiles'])
            if mol is None or mol.GetNumAtoms() == 0:
                row['status'] = 'invalid_or_empty_molecule'
            else:
                result = npscorer.scoreMolWConfidence(mol, model)
                row.update(np_score=result.nplikeness,
                           np_coverage=result.confidence, qed=QED.qed(mol))
                for metric in ('np_score', 'qed'):
                    groups[(row['collection'], metric)].append(row[metric])
        rows.append(row)

if not rows:
    raise ValueError('No compound records in input')
fields = ['input_line', 'compound_id', 'collection', 'smiles',
          'rdkit_version', 'np_score', 'np_coverage', 'qed', 'status']
with open('likeness.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

with open('likeness-ecdf.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['collection', 'metric', 'value', 'fraction_le', 'n_valid'])
    for (collection, metric), values in sorted(groups.items()):
        values.sort()
        for value in sorted(set(values)):
            writer.writerow([collection, metric, value,
                             bisect_right(values, value) / len(values), len(values)])

for collection in sorted({r['collection'] for r in rows}):
    subset = [r for r in rows if r['collection'] == collection]
    valid = sum(r['status'] == 'ok' for r in subset)
    print(collection, 'valid:', valid, 'rejected:', len(subset) - valid)
```

Plot `fraction_le` against `value` as a step curve, comparing collections separately for each metric. At a score threshold, the ECDF is the fraction of valid molecules scoring at or below it. Ties receive the same cumulative fraction; collections are normalized separately, with `n_valid` recording their sizes.

## Interpret results and failures

| Output | Interpretation |
| --- | --- |
| `np_score` | More positive means more NP-like according to the supplied fragment model; it is not a probability. |
| `np_coverage` | Fraction of distinct fingerprint features found in the NP model, between 0 and 1. It measures model coverage, not confidence in bioactivity or a calibrated probability of natural origin. |
| `qed` | Higher means more drug-like according to QED's property desirability model; it is not a probability of clinical success. |
| `status` | Only `ok` records enter the ECDF; other rows retain identifiers and blank score fields for correction. |

Inspect coverage and rejected counts alongside score distributions. A collection with no valid records produces no ECDF rows; this is not a low-likeness result. The example does not remove chemically duplicate structures: decide that preparation policy before comparing collections.

A missing scorer raises an import error; a missing, corrupt or incorrectly downloaded model prevents model loading. RDKit parsing can emit diagnostics and return `None`. Unexpected scoring exceptions terminate this example before its output-writing stage; do not treat that termination as a completed comparison.

Use the same RDKit release, model and preparation policy for every collection in a comparison. The [QED API documentation](https://www.rdkit.org/docs/source/rdkit.Chem.QED.html) explains its weighting variants and notes that implementation-dependent property calculations can differ from the original QED publication.
