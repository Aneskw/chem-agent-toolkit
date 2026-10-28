---
name: delaney-esol-scaffold-evaluation
description: "Load the bundled Delaney ESOL labels and construct a scaffold-disjoint evaluation split with DeepChem, preserving measured log-solubility units."
license: undetermined
---


# Delaney ESOL scaffold evaluation

Use a DeepChem environment with RDKit, NumPy and its supported dependencies ([installation](https://deepchem.readthedocs.io/en/latest/get_started/installation.html)). The checked loader/splitter source is DeepChem commit `455d07f3e17e880a4d980b5b0365e4a02b417e14`.

The fixed CSV is included at `resources/datasets/delaney-processed.csv`. Its feature field is `smiles`; the measured target is literally `measured log solubility in mols per litre`. Do not substitute the CSV's calculated ESOL values for that measured label.

```python
from pathlib import Path
import csv
import deepchem as dc

csv_path = Path("/path/to/skill/resources/datasets/delaney-processed.csv")
label = "measured log solubility in mols per litre"
loader = dc.data.CSVLoader(tasks=[label], feature_field="smiles",
                           featurizer=dc.feat.CircularFingerprint(size=1024))
dataset = loader.create_dataset(str(csv_path))
with csv_path.open(newline="", encoding="utf-8") as f:
    input_rows = sum(1 for _ in csv.DictReader(f))
assert len(dataset) == input_rows  # report rejected rows instead of silently changing evaluation cases
train, valid, test = dc.splits.ScaffoldSplitter().train_valid_test_split(
    dataset, frac_train=0.8, frac_valid=0.1, frac_test=0.1)
assert len(train) + len(valid) + len(test) == len(dataset)
```

`X` holds chosen features, `y` measured log-solubility labels, `w` task weights and `ids` the input SMILES. This example applies no label normalization. If fitting transformations for training, fit them only on training data and retain the inverse transform for reporting.

The [splitter](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/splits/splitters.py) keeps Bemis–Murcko scaffold groups together and allocates groups by size; fractions may be approximate and a seed does not randomize this deterministic scaffold grouping. Preserve the realized sample IDs, featurizer and library version for comparisons. Invalid SMILES can be omitted by featurization/splitting; inspect coverage instead of accepting a smaller dataset unnoticed.

[Fixed loader and label definition](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/delaney_datasets.py). Scaffold splitting is this dataset's recommended evaluation convention, not a universal rule for every chemistry task.
