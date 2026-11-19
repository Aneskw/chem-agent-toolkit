---
name: scipy-fit-hammett-rate-correlations
description: Estimate a Hammett reaction constant and regression uncertainty with SciPy from prepared substituent constants and comparable reaction rate constants. Use after rate extraction, when checking a linear substituent effect.
---

# Hammett regression from prepared rates

Fit the free-intercept relation `log10(k_X/k_H) = intercept + rho * sigma`. This workflow starts after experimental calibration and rate extraction. It does not infer a kinetic model from concentration traces.

## Environment and inputs

Use Python 3.12 and SciPy 1.18.1 with NumPy. Follow the official [SciPy installation guide](https://scipy.org/install/) to prepare a virtual environment, then install the pinned package:

```sh
python -m pip install "scipy==1.18.1"
```

| Input | Contract |
|---|---|
| `labels` | Substituent identifiers in the same order as both arrays. |
| `sigma` | One-dimensional, finite, dimensionless substituent constants from a consistent scale and substitution position. |
| `k` | Matching positive, finite rate constants from comparable conditions and the same kinetic definition. |
| `k_H` | Positive, finite unsubstituted reference rate, with the same units as `k`. |

Use at least three pairs for the uncertainty calculation below, with variation in `sigma`. Preserve the association between each substituent and its rate; never sort the arrays independently. Supply the appropriate substituent constants rather than guessing them. Rates may carry units such as inverse seconds, but their ratio must be dimensionless.

## Fit and inspect

Replace this illustrative input block with prepared measurements. These numbers demonstrate the interface; they are not measured data or published substituent constants.

```python
import numpy as np
from scipy.stats import linregress, t

labels = ["X1", "H", "X2", "X3"]
sigma = np.array([-0.2, 0.0, 0.2, 0.4], dtype=float)
k = np.array([1.6, 1.0, 0.65, 0.4], dtype=float)
k_H = 1.0  # same rate units as every entry in k

if (sigma.ndim != 1 or k.shape != sigma.shape
        or sigma.size < 3 or len(labels) != sigma.size):
    raise ValueError("Supply at least three aligned one-dimensional pairs.")
if (not np.all(np.isfinite(sigma)) or not np.all(np.isfinite(k))
        or not np.isfinite(k_H) or np.any(k <= 0) or k_H <= 0
        or np.ptp(sigma) == 0):
    raise ValueError("Require finite values, positive rates, and varying sigma.")

y = np.log10(k / k_H)
if not np.all(np.isfinite(y)):
    raise ValueError("Rate-ratio transformation produced nonfinite values.")
result = linregress(sigma, y)
fitted = result.intercept + result.slope * sigma
residual = y - fitted
rho_margin = abs(t.ppf(0.025, sigma.size - 2)) * result.stderr
```

Access the result through attributes so the intercept uncertainty remains available. Continue in the same Python session:

```python
summary = {
    "rho": result.slope,
    "intercept": result.intercept,
    "r_squared": result.rvalue ** 2,
    "rho_stderr": result.stderr,
    "intercept_stderr": result.intercept_stderr,
    "rho_ci95": (result.slope - rho_margin, result.slope + rho_margin),
}
rows = [
    {"substituent": label, "sigma": float(s), "log10_rate_ratio": float(obs),
     "fitted": float(pred), "residual": float(err)}
    for label, s, obs, pred, err in zip(labels, sigma, y, fitted, residual)
]
print(summary)
for row in rows:
    print(row)
```

The outputs are an in-memory summary and observed/fitted table, also printed to standard output. No files are written and the supplied arrays are not modified. If persistence is requested, serialize these objects to the requested path.

## Interpret the result

- `rho` is `result.slope`. `result.rvalue` is a Pearson correlation coefficient, not the Hammett reaction constant. Both fitted coefficients are dimensionless.
- Keep the fitted intercept: `linregress` estimates it rather than forcing the line through zero. An unsubstituted reference has zero log-rate ratio by construction; that alone does not constrain the entire regression through the origin.
- Report the slope with its standard error or the calculated two-sided 95% interval. These regression uncertainties assume normally distributed residuals; the fit does not propagate supplied rate errors or shared-reference uncertainty. It is ordinary unweighted least squares, not an errors-in-variables analysis.
- Inspect residuals versus `sigma` and substituent identity. Curvature or a systematic subgroup pattern limits a single-slope interpretation; a high R-squared alone does not establish a mechanism.
- A negative slope means rates decrease with increasing `sigma`; a positive slope means the reverse. Mechanistic interpretation requires the chosen substituent scale and independent experimental evidence.

Empty inputs and constant `sigma` do not yield an interpretable fit. Treat exceptions or nonfinite coefficients/uncertainties as unresolved analysis, not a null substituent effect. A zero slope from valid data is a possible result; a NaN correlation diagnostic is not evidence of a mechanism.

For interface details, consult the [version-tagged linregress documentation and implementation](https://github.com/scipy/scipy/blob/v1.18.1/scipy/stats/_stats_py.py).
