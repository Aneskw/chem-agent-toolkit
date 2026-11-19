---
name: scipy-fit-grouped-initial-rate-orders
description: Estimate apparent reaction orders from prepared concentration and initial-rate measurements using SciPy logarithmic regression, with slope uncertainty and fit diagnostics.
---

# Fit apparent reaction orders from initial rates

Use one concentration series per varied component, measured under otherwise fixed conditions. This workflow starts with quantified initial rates; extracting rates from time courses or instrument signals is an external preparation step.

## Environment and input

Use Python 3.12 or newer with [SciPy 1.18.1](https://pypi.org/project/scipy/1.18.1/). Its NumPy requirement is `>=2.0,<2.8`. Official setup guidance is at [SciPy installation](https://scipy.org/install/); in the intended Python environment:

```shell
python -m pip install scipy==1.18.1
```

Prepare `rates.csv` in the working directory:

| Column | Meaning |
| --- | --- |
| `component` | Identifier for one independently varied concentration series |
| `concentration` | Positive finite concentration; one consistent unit within the series |
| `initial_rate` | Positive finite initial rate; one consistent unit within the series |

Each series needs at least three observations and more than one distinct concentration. Keep replicates as separate observations. Record concentration/rate units and the fixed experimental conditions alongside the data. Separate series with different conditions even if they vary the same component. Zero, negative or missing rates cannot enter this logarithmic fit; investigate them rather than replacing them with small positive numbers.

Illustrative input layout, not published measurements:

```csv
component,concentration,initial_rate
substrate,0.020,0.0011
substrate,0.040,0.0019
substrate,0.060,0.0032
substrate,0.080,0.0039
```

## Regression and output

Regress `y=-ln(v/v_ref)` on `x=-ln(c/c_ref)` with an intercept. For a local power-law dependence `v proportional to c**n`, the slope is the apparent order `n`; negating both logarithms preserves its sign. Fixed positive reference values make the logarithms dimensionless. The example uses each series' first observation as its references and records them in the output. Changing reference values changes the intercept, not the slope.

Run this Python example with the prepared CSV. It uses ordinary, unweighted least squares through [`scipy.stats.linregress`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html), whose default alternative is two-sided.

```python
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import linregress, t

groups = defaultdict(list)
with Path("rates.csv").open(newline="", encoding="utf-8-sig") as stream:
    for row in csv.DictReader(stream):
        groups[row["component"]].append(
            (float(row["concentration"]), float(row["initial_rate"]))
        )
if not groups:
    raise ValueError("rates.csv has no measurements")

summary, points = [], []
for component, rows in groups.items():
    data = np.asarray(rows, dtype=np.float64)
    c, v = data[:, 0], data[:, 1]
    if len(c) < 3 or not np.all(np.isfinite(data)) or np.any(data <= 0):
        raise ValueError(f"{component}: need >=3 finite, positive pairs")
    if np.ptp(c) == 0:
        raise ValueError(f"{component}: concentrations are all identical")

    c_ref, v_ref = c[0], v[0]
    x, y = -np.log(c / c_ref), -np.log(v / v_ref)
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError(f"{component}: nonfinite logarithms")
    fit = linregress(x, y, nan_policy="raise")
    y_fit = fit.intercept + fit.slope * x
    residual = y - y_fit
    half_width = t.ppf(0.975, len(x) - 2) * fit.stderr

    # An exactly constant response has no informative R-squared or
    # residual-based uncertainty. Leave these CSV fields empty.
    varying_rate = np.ptp(y) > 0
    summary.append({
        "component": component, "n_points": len(x),
        "concentration_ref": c_ref, "rate_ref": v_ref,
        "order": fit.slope, "intercept": fit.intercept,
        "order_stderr": fit.stderr if varying_rate else None,
        "order_ci95_low": fit.slope - half_width if varying_rate else None,
        "order_ci95_high": fit.slope + half_width if varying_rate else None,
        "r_squared": fit.rvalue**2 if varying_rate else None,
        "status": "fit" if varying_rate else "constant-rate",
    })
    for ci, vi, xi, yi, fi, ri in zip(c, v, x, y, y_fit, residual):
        points.append({
            "component": component, "concentration": ci, "initial_rate": vi,
            "x": xi, "y": yi, "y_fit": fi, "residual": ri,
        })

for filename, records in [
    ("reaction-orders.csv", summary), ("reaction-order-points.csv", points)
]:
    with Path(filename).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
```

## Read the results

The example leaves `rates.csv` unchanged and overwrites two files in the working directory:

- `reaction-orders.csv`: one row per series, with dimensionless fitted order, slope standard error, a two-sided 95% slope interval, intercept, R-squared and the reference values in the input units.
- `reaction-order-points.csv`: measured values, transformed points, fitted log responses and residuals (`y-y_fit`) for inspection. Sort by `x` before drawing a connected fitted line.

Plot `y` against `x` and residuals against `x` for each component before using the estimate. Curvature or changing residual spread can undermine a single unweighted log-linear fit. The interval uses Student-t with `N-2` degrees of freedom and SciPy's residual-based slope standard error; its usual regression assumptions apply to errors in the transformed response. This fit does not propagate concentration uncertainty or account for unequal measurement errors. Logging also changes the error model relative to fitting rates directly.

Report the fitted slope and interval as an apparent order over the measured concentration range. An interval containing one is compatible with first-order dependence under this model; it does not establish a unique mechanism. R-squared describes the log-space fit, not mechanistic validity. The `linregress` p-value tests zero slope, not first-order dependence, so it is not used here.

A `constant-rate` row retains the fitted slope but leaves R-squared and residual-based uncertainty blank: identical reported rates do not establish exact zero order or zero uncertainty. A `fit` status only marks a completed regression. Treat any nonfinite statistic as unresolved. Invalid input raises an error before either output file is written; existing output files may therefore be from a previous run. An empty input is an error, not evidence of no concentration dependence.
