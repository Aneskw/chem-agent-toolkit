---
name: scipy-check-catalyst-product-ee-linearity
description: Analyze paired catalyst and product enantiomeric excess measurements with SciPy to assess linearity in a nonlinear-effect experiment, returning a freely fitted line, uncertainty and residuals.
---

# Catalyst–product ee linearity with SciPy

Fit product ee against catalyst ee using ordinary linear least squares. Start with experimentally measured pairs from one set of reaction conditions. This workflow analyzes those measurements; it does not prepare mixtures, measure ee, or uniquely identify catalyst aggregation.

## Prepare the environment and measurements

Use **SciPy 1.18.1** with **Python 3.12 or later**. Follow the official [SciPy installation guide](https://scipy.org/install/) to obtain Python and create an activated virtual environment, then install the pinned release:

```sh
python -m pip install "scipy==1.18.1"
```

NumPy is a SciPy dependency and is used below. The [release package](https://pypi.org/project/scipy/1.18.1/) supplies platform distributions.

Prepare two equal-length, one-dimensional numeric arrays:

| Input | Meaning |
| --- | --- |
| `ee_catalyst` | Catalyst ee in percent: `20.0` means 20%, not 0.20 |
| `ee_product` | Corresponding measured product ee in percent, in the same row order |

Use a consistent stereochemical sign convention for each species across the series and record which enantiomer is positive. Do not replace signed measurements with absolute values. Keep a measured racemic-catalyst point with its measured product ee; do not insert a synthetic `(0, 0)` point or force a measured product value to zero. Fit the intercept freely. Use at least three finite pairs with variation in catalyst ee to obtain a line with residual degrees of freedom. Resolve missing values at the paired-row level before fitting.

## Fit and return results

Replace the two arrays with the user's measurements. The values here are the six measured pairs in [the study's supporting information](https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-025-57381-w/MediaObjects/41467_2025_57381_MOESM1_ESM.pdf), section 9.3.3, Table S6 (S154), with catalyst ee assigned to `x` and product ee to `y`.

Run this in the prepared Python environment:

```python
import json
import numpy as np
from scipy.stats import linregress

ee_catalyst = np.asarray([0, 19.34, 38.62, 59.62, 78.70, 99.99], dtype=float)
ee_product = np.asarray([0, 17.78, 36.18, 56.10, 73.90, 93.78], dtype=float)

if (ee_catalyst.ndim != 1 or ee_product.ndim != 1
        or ee_catalyst.shape != ee_product.shape or ee_catalyst.size < 3):
    raise ValueError("Provide equal-length 1-D arrays with at least three pairs.")
if not (np.isfinite(ee_catalyst).all() and np.isfinite(ee_product).all()):
    raise ValueError("Resolve nonfinite measurements as paired rows before fitting.")
if (np.any(np.abs(ee_catalyst) > 100) or np.any(np.abs(ee_product) > 100)):
    raise ValueError("ee must be expressed in percent within [-100, 100].")
if np.unique(ee_catalyst).size < 2:
    raise ValueError("Catalyst ee must vary.")

fit = linregress(ee_catalyst, ee_product)
predicted = fit.intercept + fit.slope * ee_catalyst
residual = ee_product - predicted

paired_data = [
    {"ee_catalyst_percent": float(x), "ee_product_percent": float(y),
     "predicted_product_ee_percent": float(yhat), "residual_pp": float(err)}
    for x, y, yhat, err in zip(ee_catalyst, ee_product, predicted, residual)
]
summary = {
    "n_pairs": int(ee_catalyst.size),
    "slope": float(fit.slope),
    "intercept_pp": float(fit.intercept),
    "r_squared": float(fit.rvalue**2),
    "slope_stderr": float(fit.stderr),
    "intercept_stderr_pp": float(fit.intercept_stderr),
    "pvalue_zero_slope_two_sided": float(fit.pvalue),
}
print(json.dumps({"paired_data": paired_data, "regression": summary},
                 indent=2, allow_nan=False))
```

`paired_data` and `summary` remain available in memory; the printed JSON is the returned table and regression summary. Inputs are retained without normalization or reordering. Fitted values are model predictions at the measured catalyst ee values, not additional measurements. The [versioned implementation and API documentation](https://github.com/scipy/scipy/blob/v1.18.1/scipy/stats/_stats_py.py#L10793) define the regression and result attributes. Keep the result object: five-value tuple unpacking omits `intercept_stderr`.

## Interpret and inspect

| Result | Meaning |
| --- | --- |
| `slope`, `slope_stderr` | Product-ee change per catalyst-ee change and its standard error; dimensionless when both use percent |
| `intercept_pp`, `intercept_stderr_pp` | Freely estimated product ee at zero catalyst ee and its standard error, in percentage points |
| `r_squared` | `fit.rvalue**2`, the coefficient of determination |
| `residual_pp` | Measured minus predicted product ee, in percentage points |
| `pvalue_zero_slope_two_sided` | Default two-sided test of a zero slope; **not a test for absence of nonlinear effects** |

Inspect residuals against catalyst ee in increasing catalyst-ee order, alongside R² and the experimental measurement uncertainty. Systematic curvature warrants further investigation; a high R² alone does not establish absence of curvature. Report apparent linearity only over the sampled ee range and reaction conditions. Standard errors use the regression's residual-normality assumption and do not propagate independently measured catalyst-ee errors. This call accepts no measurement-error weights.

Do not infer a unique active-species stoichiometry or absence of aggregation from linearity alone. Return the measured pairs, fitted line, uncertainties and residuals so that mechanistic conclusions remain separate from the regression.

Treat nonfinite fit results or serialization failures as an unsuccessful analysis requiring input/degeneracy inspection. Do not turn missing or invalid statistics into zeros or report them as evidence of linearity.
