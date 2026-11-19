---
name: scipy-fit-first-order-substrate-depletion
description: Estimate and compare first-order substrate disappearance rates from prepared concentration-time data using SciPy, with regression uncertainty and residual diagnostics.
---

# Fit first-order disappearance rates with SciPy

Fit the model `ln(C) = b - k*t` separately for each reaction series over a supplied fitting interval. Concentrations must already be calibrated; NMR/HPLC integration and experimental data collection are external preparation.

## Environment and inputs

Use **SciPy 1.18.1** with Python 3.12 and NumPy >=2.0.0,<2.8. Follow the official [installation instructions](https://scipy.org/install/) to prepare a virtual environment, then install the selected release:

```sh
python -m pip install "scipy==1.18.1"
```

NumPy is a SciPy dependency. No credentials or specialized hardware are required.

| Input | Contract |
| --- | --- |
| Series name | Distinguishes reaction conditions or substrate enantiomers. |
| `time_h` | One-dimensional finite numeric array, in hours. |
| `concentration` | Matching array of strictly positive substrate concentrations, in a consistent unit such as mol/L. Do not substitute product yield or enantiomeric excess. |
| Fitting interval | Supplied start and end times, inclusive. Each selected series needs at least three observations and two distinct times. |

Use the same concentration unit and comparable experimental conditions when comparing series. Keep the interval explicit; do not select points simply to maximize R-squared. Taking logarithms of numerical concentrations uses their stated unit as the reference scale: changing that unit shifts the intercept but leaves the slope unchanged.

## Representative usage

Replace the illustrative arrays and interval below with prepared measurements and the chosen fitting interval. The example uses unweighted ordinary least squares in log-concentration space; it does not apply measurement-error weights.

```python
import numpy as np
from scipy import stats

# Illustrative inputs, not published measurements; concentrations in mol/L.
series = {
    "condition-a": ([0, 1, 2, 3, 4], [0.200, 0.186, 0.174, 0.159, 0.149]),
    "condition-b": ([0, 1, 2, 3, 4], [0.200, 0.197, 0.195, 0.191, 0.189]),
}
start_h, end_h = 0.0, 4.0

fit_objects, diagnostics, summary = {}, {}, []
for name, (time_h, concentration) in series.items():
    t = np.asarray(time_h, dtype=float)
    c = np.asarray(concentration, dtype=float)
    if t.ndim != 1 or c.ndim != 1 or t.shape != c.shape:
        raise ValueError(f"{name}: expected matching one-dimensional arrays")
    if not np.isfinite(t).all() or not np.isfinite(c).all() or np.any(c <= 0):
        raise ValueError(f"{name}: times must be finite; concentrations finite and positive")
    selected = (t >= start_h) & (t <= end_h)
    t, c = t[selected], c[selected]
    if t.size < 3 or np.unique(t).size < 2:
        raise ValueError(f"{name}: insufficient observations or distinct times")
    order = np.argsort(t)
    t, c = t[order], c[order]
    y = np.log(c)
    if np.ptp(y) == 0:
        raise ValueError(f"{name}: constant concentrations; no resolved disappearance trend")

    res = stats.linregress(t, y)
    if not np.isfinite([
        res.slope, res.intercept, res.stderr, res.intercept_stderr, res.rvalue
    ]).all():
        raise ValueError(f"{name}: nonfinite regression result")

    fitted_log_c = res.intercept + res.slope * t
    fit_objects[name] = res
    diagnostics[name] = {
        "time_h": t,
        "observed_log_c": y,
        "fitted_log_c": fitted_log_c,
        "residual_log_c": y - fitted_log_c,
    }
    summary.append({
        "series": name, "n": int(t.size),
        "start_h": start_h, "end_h": end_h,
        "k_h_inv": float(-res.slope),
        "k_stderr_h_inv": float(res.stderr),
        "intercept": float(res.intercept),
        "intercept_stderr": float(res.intercept_stderr),
        "r_squared": float(res.rvalue**2),
    })

for row in summary:
    print(row)
# Inspect paired time/residual arrays, or plot them in your plotting environment:
print(diagnostics["condition-a"]["time_h"])
print(diagnostics["condition-a"]["residual_log_c"])
```

Outputs remain in memory: `summary` is a per-series table of records, `fit_objects[name]` retains the full SciPy result, and `diagnostics[name]` retains the selected observations, predictions and residuals. Inputs are not mutated. Preserve the concentration unit with any exported table. The official [linregress reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html) documents result attributes and confidence-interval examples.

## Interpret the results

- **Rate and uncertainty:** `k = -slope` has units h^-1. Negating the slope leaves its standard error unchanged. A standard error is not a confidence interval; SciPy's reported slope and intercept standard errors assume residual normality.
- **Fit quality:** `rvalue**2` is ordinary R-squared, not adjusted R-squared. Inspect residuals against time for curvature or other systematic patterns before interpreting the fitted rate. A high R-squared alone does not establish reaction order or mechanism.
- **Comparisons:** Larger positive `k` means faster fitted disappearance over the selected interval. Retain uncertainty and experimental conditions when comparing estimates; numerical ordering alone does not establish a meaningful difference.
- **Failure or weak signal:** Zero/negative concentrations cannot be logged. Constant concentrations give no resolved trend, and missing or degenerate data cannot yield a usable uncertainty estimate. A nonpositive `k` or uncertainty large relative to `k` does not support a clear disappearance rate. Do not replace an invalid or unresolved fit with a reported zero rate.
