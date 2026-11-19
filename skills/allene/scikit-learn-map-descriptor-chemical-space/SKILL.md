---
name: scikit-learn-map-descriptor-chemical-space
description: Fit a shared scikit-learn PCA map for prepared compound and reference descriptor tables, project additional collections, and interpret coordinates, descriptor weights and explained variance.
---

# Map compound collections in a common PCA space

## Prepare the environment and tables

Use **scikit-learn 1.9.1 with Python >=3.11**. Follow the [official installation instructions](https://scikit-learn.org/stable/install.html) for an isolated environment and install the pinned release with `python -m pip install scikit-learn==1.9.1`. NumPy is a dependency; the example otherwise uses the Python standard library. See the [PCA API](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html) for interface details.

Start with numeric descriptors already calculated and preprocessed. Descriptor selection, units, scaling and the population used to estimate preprocessing parameters are supplied decisions. PCA centers each descriptor using the fitting population's mean; it does **not** scale descriptors. If scaling is part of the policy, apply the same fitted preprocessing to both tables before this workflow, without fitting a separate scaler for each collection.

Prepare these external inputs in the working directory:

| Input | Contract |
| --- | --- |
| `fit.csv` | UTF-8 header CSV; one compound per row, `id`, `collection`, and the declared numeric descriptor columns. All rows define the PCA fitting population. |
| `other.csv` | Same fields and descriptor meanings; additional compounds to project. Header-only is allowed when there are no additional compounds. |
| `policy.json` | `descriptor_columns`: ordered, unique descriptor names; `preprocessing`: description of the applied transformations, units and fitted preprocessing parameters or their accessible artifact; `fit_population`: description of the included collections and sampling. |

Use at least three descriptors and three fitting rows for the three-component example. Values must be finite; missing-value handling is an upstream decision. Do not include identifiers or collection labels as descriptors. Give rows stable identifiers, unique within each collection. Column order is aligned by name below; units and descriptor definitions must already match.

Choose the fitting population deliberately. To derive a joint compound/reference basis, include those collections together in `fit.csv`. To preserve a reference-derived basis, fit only those references and place the new compounds in `other.csv`. Independently fitting PCA per collection produces different coordinate systems.

## Fit once and project

The following template reads the supplied inputs and writes `pca-map.json` in the working directory, replacing an existing file of that name. The choice of three components and the full SVD solver is an example configuration. Whitening is disabled to retain variance scales; input copying is enabled.

```python
import csv
import json
import numpy as np
from sklearn.decomposition import PCA

with open("policy.json", encoding="utf-8") as f:
    policy = json.load(f)
columns = policy["descriptor_columns"]
if (len(columns) < 3 or len(set(columns)) != len(columns)
        or {"id", "collection"}.intersection(columns)):
    raise ValueError("Declare at least three unique descriptor columns")

def read_table(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not {"id", "collection", *columns}.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing columns in {path}")
        rows = list(reader)
    keys = [(r["collection"], r["id"]) for r in rows]
    if any(not c or not i for c, i in keys) or len(set(keys)) != len(keys):
        raise ValueError(f"Missing or duplicate collection/id in {path}")
    X = np.array([[float(r[c]) for c in columns] for r in rows],
                 dtype=float).reshape(len(rows), len(columns))
    if not np.isfinite(X).all():
        raise ValueError(f"Nonfinite descriptors in {path}")
    return rows, X

fit_rows, X_fit = read_table("fit.csv")
other_rows, X_other = read_table("other.csv")
if len(X_fit) < 3 or not np.any(np.ptp(X_fit, axis=0) > 0):
    raise ValueError("Need at least three fitting rows and nonzero variation")

pca = PCA(n_components=3, svd_solver="full", whiten=False, copy=True)
Z_fit = pca.fit_transform(X_fit)
Z_other = pca.transform(X_other) if len(X_other) else np.empty((0, 3))

def coordinates(rows, Z, role):
    return [dict(id=r["id"], collection=r["collection"], role=role,
                 PC1=float(z[0]), PC2=float(z[1]), PC3=float(z[2]))
            for r, z in zip(rows, Z)]

result = {
    "software": "scikit-learn==1.9.1",
    "policy": policy,
    "parameters": {"n_components": 3, "svd_solver": "full",
                   "whiten": False, "copy": True},
    "coordinates": coordinates(fit_rows, Z_fit, "fit")
                   + coordinates(other_rows, Z_other, "projected"),
    "descriptor_columns": columns,
    "components": pca.components_.tolist(),
    "mean": pca.mean_.tolist(),
    "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
}
with open("pca-map.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, allow_nan=False)
```

Retain `pca` and the fitted upstream preprocessing in the active session for further projections. Call `pca.transform` on additional tables in the same descriptor order and preprocessing space. Calling `fit` or `fit_transform` again replaces the basis.

## Inspect and interpret the map

- `coordinates` contains one record per input row with identifiers, collection, fit/projected role and three scores. Plot PC1/PC2, PC1/PC3 or PC2/PC3, grouping records by collection. These are transformed coordinates; original input tables remain unchanged.
- `components` has shape `(3, n_descriptors)`: row `k` gives PC `k+1` axis coefficients, in `descriptor_columns` order. Inspect large absolute coefficients to identify descriptors contributing strongly to an axis, interpreting them in the declared preprocessing space. These coefficients are not automatically feature–PC correlation coefficients.
- `explained_variance_ratio` has three fractions in descending component order. Multiply by 100 for axis percentages; sum them for retained variance. They describe the fitting population, not variance explained within each projected collection.
- `mean` is the fitting population's descriptor mean in the preprocessed space. Keep it, the axes and the preprocessing policy alongside the coordinates for traceability.

Low retained variance means the three-dimensional view omits substantial variation. Rank-deficient fitting data can yield zero-variance axes; an entirely constant fitting matrix is rejected by the template. An empty projection table yields no projected records. Missing columns, malformed numeric values, NaN/infinity and invalid fitting size fail before PCA. Resolve those input problems upstream rather than silently deleting rows or changing the descriptor set. Proximity in this descriptor map alone does not establish shared biological activity.
