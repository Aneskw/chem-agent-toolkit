---
name: build-encoded-reaction-space
description: Build a numeric, encoded Cartesian reaction domain from component option lists for EDBO workflows. Use when preparing a candidate reaction space from reagents, solvents, catalysts, substrates, or numeric conditions; this skill does not select experiments or optimize measured yields.
---

# Build an encoded reaction space with EDBO

Use EDBO’s `reaction_space` when you have component choices and need the model-ready domain plus a way to recover the original component identities. Supply one list per component. Choose an encoding for each component whose values need special handling; default encoding is one-hot encoding.

## Setup

The inspected upstream snapshot is EDBO `0.1.0` (repository commit [`9b41eac3f6d9e520547702fd5b0c7ef6441625a4`](https://github.com/b-shields/edbo/tree/9b41eac3f6d9e520547702fd5b0c7ef6441625a4)). Its [README installation instructions](https://github.com/b-shields/edbo/blob/9b41eac3f6d9e520547702fd5b0c7ef6441625a4/README.md) specify Python 3.7.5, RDKit, Mordred, PyTorch 1.3.1, then EDBO. Use the upstream package and environment appropriate to this legacy snapshot:

```bash
conda create --name edbo python=3.7.5
conda activate edbo
conda install -c rdkit rdkit
conda install -c rdkit -c mordred-descriptor mordred
conda install -c pytorch pytorch=1.3.1
pip install git+https://github.com/b-shields/edbo.git@9b41eac3f6d9e520547702fd5b0c7ef6441625a4
```

The repository’s `setup.py` identifies version `0.1.0` and declares package dependencies. For molecular inputs, install the README’s RDKit and Mordred prerequisites. The `resolve` option also calls name-to-SMILES resolution through the package’s NIH lookup helper; provide SMILES directly if name resolution is unavailable or unreliable.

## Prepare and build

`reaction_space` accepts a dictionary mapping component labels to option lists. Supported encodings are `ohe` (categorical one-hot), `mordred` or `smiles` (Mordred descriptors from SMILES), `numeric` (numeric values as supplied), and `resolve` (compound names resolved to SMILES, then Mordred descriptors). If an encoding is omitted, the component is one-hot encoded. A supplied descriptor DataFrame takes precedence over an encoding for the same component; its first column must identify the component values, followed by descriptor columns.

This example uses SMILES for the catalyst, one-hot categories for base and solvent, and numeric temperatures. Replace these illustrative inputs with the actual options for the reaction. `mordred` inputs must be valid SMILES strings.

```python
from edbo.feature_utils import reaction_space

components = {
    "catalyst": ["CC(=O)O", "O=C(O)c1ccccc1"],  # illustrative SMILES
    "base": ["K2CO3", "Cs2CO3"],
    "solvent": ["THF", "MeCN"],
    "temperature_C": [25, 60],
}
encodings = {
    "catalyst": "mordred",
    "base": "ohe",
    "solvent": "ohe",
    "temperature_C": "numeric",
}

reaction = reaction_space(components, encoding=encodings)
model_domain = reaction.data
original_component_index = reaction.get_experiments([0, 1])
```

`reaction_space` builds the Cartesian product of component options, expands each component’s descriptors across that index, and by default cleans, decorrelates (threshold `0.95`), and min–max scales the resulting numeric features. The index in `reaction.base_data` preserves original component values; `get_experiments` retrieves these identities by row position. Pass `clean=False`, `decorrelate=False`, or `standardize=False` only when the downstream workflow specifically requires unprocessed features. EDBO’s `BO_express` constructor invokes this same builder and can be used instead when you intend to continue directly into its optimization interface.

## Read the result

- `reaction.data` is the transformed numeric feature table intended as the model domain. Its rows correspond to the Cartesian component combinations.
- `reaction.get_experiments(row_positions)` returns original component values for those rows using the stored component index headers. Pass row positions, not DataFrame index labels from an unrelated table.
- `reaction.base_data` retains the unprocessed expanded table used by the `Data` container; use `get_experiments` for compact component identity lookup.

If a component does not encode successfully, inspect its values and selected encoding. Mordred failures can produce missing descriptor values; with `dropna=True` in the component encoder, descriptors containing missing values are removed. `resolve` may fail for compound names and can prompt for SMILES or one-hot fallback through EDBO’s interactive helper. For unattended preparation, prefer explicit SMILES, one-hot encoding, numeric values, or a user-prepared descriptor matrix. A feature table is an encoded search domain; it contains no measured reaction outcomes and does not itself recommend an experiment.
