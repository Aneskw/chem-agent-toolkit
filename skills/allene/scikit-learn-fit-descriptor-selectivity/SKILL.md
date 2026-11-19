---
name: scikit-learn-fit-descriptor-selectivity
description: Fit and evaluate ordinary-least-squares models of molecular descriptors against supplied enantioselectivity targets in delta-delta-G units, using fixed features and explicit training/validation partitions.
---

# Descriptor regression for enantioselectivity

Use scikit-learn to fit an unweighted multivariable linear model and assess prediction on a supplied held-out partition. Start with prepared descriptors and signed ΔΔG‡ targets. Descriptor generation, ee conversion and feature selection are separate upstream tasks.

## Prepare the environment and inputs

Use **scikit-learn 1.9.1** with a compatible 64-bit Python 3 environment. Follow the [official installation guide](https://scikit-learn.org/stable/install.html) to create and activate an isolated environment, then install the pinned release:

```sh
python -m pip install scikit-learn==1.9.1
```

The example uses NumPy, a scikit-learn dependency. Supply these external inputs in memory; no published dataset is bundled:

| Input | Contract |
| --- | --- |
| `X_train`, `X_valid` | Dense finite numeric arrays, shapes `(n_train, p)` and `(n_valid, p)`, with `p >= 1`. Identical ordered feature columns, units and transformations. |
| `y_train`, `y_valid` | Finite numeric vectors, shapes `(n_train,)` and `(n_valid,)`. One signed ΔΔG‡ target per row, with the same energy unit and enantiomer/sign convention in both partitions. |
| `feature_names` | `p` unique names in matrix-column order. Retain descriptor units and transformation definitions alongside these names. |
| `train_ids`, `valid_ids` | Sample identifiers in matrix-row order; unique and disjoint across partitions. Keep the supplied membership fixed. |

Use at least two samples in each partition for R² evaluation. Confirm descriptor rows, targets and IDs refer to the same reactions before fitting. If preparation includes learned scaling or other fitted transforms, those must have been fitted on training data and applied unchanged to validation data. Do not estimate preparation parameters or choose features using held-out targets.

Record `target_unit` (for example, `"kcal/mol"` if that is the supplied unit) and `target_sign_convention` from the data provider. Do not infer the sign convention from the magnitudes. Coefficients apply to the supplied transformed descriptor scale.

### Optional training-fitted standardization

When standardization is part of the selected model, apply it before the fitting
template below, retaining feature order and sample IDs:

```python
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler().fit(X_train)
X_train = scaler.transform(X_train)
X_valid = scaler.transform(X_valid)
```

Do not fit the scaler on validation rows. Retain it with the model and use
`model.predict(scaler.transform(X_new))` for new raw descriptor rows. Coefficients
then describe target-energy change per training standard deviation, and the
intercept corresponds to training-mean descriptors. The raw-input branch needs
no scaler. Never apply standardized coefficients directly to raw descriptors.

## Fit and inspect predictions

This template consumes the prepared variables above. The parameter choices are ordinary unconstrained least squares with an intercept and the documented default tolerance; no sample weights or positivity constraint are used. `copy_X=True` protects the input matrix from estimator overwrite. See the [LinearRegression API](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LinearRegression.html) for parameter and attribute details.

```python
import numpy as np
import sklearn
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_squared_error

X_train = np.asarray(X_train, dtype=float)
X_valid = np.asarray(X_valid, dtype=float)
y_train = np.asarray(y_train, dtype=float)
y_valid = np.asarray(y_valid, dtype=float)

# Reject malformed prepared inputs rather than silently reshaping/reordering.
for X, y, ids in ((X_train, y_train, train_ids),
                  (X_valid, y_valid, valid_ids)):
    if (X.ndim != 2 or y.ndim != 1 or X.shape[0] != len(y)
            or len(ids) != len(y) or len(y) < 2
            or X.shape[1] != len(feature_names) or len(feature_names) == 0):
        raise ValueError("Check array shapes, feature names and sample IDs")
    if not (np.isfinite(X).all() and np.isfinite(y).all()):
        raise ValueError("Descriptors and targets must be finite")

model = LinearRegression(
    fit_intercept=True, copy_X=True, tol=1e-6, positive=False
).fit(X_train, y_train)

pred_train = model.predict(X_train)
pred_valid = model.predict(X_valid)

def evaluate(y, predicted, ids):
    return {
        "n": len(y),
        "r2": float(r2_score(y, predicted, force_finite=False)),
        "mse": float(mean_squared_error(y, predicted)),
        "samples": [
            {"id": sample_id, "observed": float(obs),
             "predicted": float(pred), "residual": float(obs - pred)}
            for sample_id, obs, pred in zip(ids, y, predicted)
        ],
    }

report = {
    "sklearn_version": sklearn.__version__,
    "parameters": model.get_params(),
    "target_unit": target_unit,
    "target_sign_convention": target_sign_convention,
    "coefficients": [
        {"feature": name, "coefficient": float(coef)}
        for name, coef in zip(feature_names, model.coef_)
    ],
    "intercept": float(model.intercept_),
    "rank": int(model.rank_),
    "singular_values": model.singular_.tolist(),
    "training": evaluate(y_train, pred_train, train_ids),
    "validation": evaluate(y_valid, pred_valid, valid_ids),
}
```

Return `model` for further prediction and `report` for inspection or export. The example writes no files. Attach the feature units and transformation definitions to the report when handing it off. Subsequent `model.predict(X_new)` requires the same ordered descriptor columns and preparation.

## Interpret and report

- The model predicts `intercept + sum(coefficient[j] * X[j])`. Predictions, intercept and residuals (`observed - predicted`) use the target energy unit; MSE uses its square. A coefficient is target units per unit of its supplied descriptor scale.
- Report training and validation scores separately. R² is unadjusted; 1 is best and negative values mean worse than predicting the mean of the **evaluated partition's targets**. That reference mean is not necessarily the training mean. R² depends on target variance, so pair it with MSE and sample-level errors when comparing partitions.
- `force_finite=False` preserves undefined constant-target R²: `NaN` for perfect predictions or `-inf` for imperfect predictions. Keep that status visible; do not replace it with a successful-looking score. For strict JSON export, encode nonfinite scores as explicit strings or null with a separate status field, since standard JSON has no nonfinite numbers. Metric definitions and edge cases are in the [evaluation guide](https://scikit-learn.org/stable/modules/model_evaluation.html#regression-metrics).
- For this dense, unconstrained fit, inspect `rank_` and `singular_`. A numerical rank below the number of features signals unresolved feature directions; individual coefficients are not uniquely determined by the data at that tolerance. In 1.9, `tol` is passed to dense `scipy.linalg.lstsq` as `cond`, so changing it can change rank and coefficients. Record it; do not interpret it as a prediction-error threshold.
- Good training fit does not establish generalization to simultaneous catalyst/substrate changes. Inspect validation residuals, including which combinations fail. Coefficient signs describe conditional associations under the supplied features and target sign convention; they do not establish causality.
