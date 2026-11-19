---
name: scipy-fit-concentration-or-pressure-orders
description: Estimate apparent reaction orders from prepared initial-rate concentration or hydrogen-pressure series using SciPy log-log regression, with fit statistics and recorded units.
---

# Reaction orders from initial-rate series

Use one series per varied factor, with other reaction conditions held fixed. Start with calibrated, comparable initial rates and their corresponding concentrations or pressures. Rate extraction, calibration and selection of time windows are supplied preparation. In systems with induction periods, record how the supplied rates were selected so that activation effects are not mixed with concentration dependence.

## Environment

Use Python 3.15 and SciPy 1.18.1. Obtain Python from [python.org](https://www.python.org/downloads/). In an activated virtual environment, install the pinned package:

```console
python -m pip install "scipy==1.18.1"
```

The [official installation guide](https://scipy.org/install/) covers environment setup. The workflow uses Python's standard library for input and output; it needs no credentials or external dataset.

## Prepare one series

Supply a UTF-8 CSV named `initial-rates.csv` in the working directory:

| Column | Meaning |
| --- | --- |
| `factor` | Positive concentration or hydrogen pressure, in one consistent unit |
| `initial_rate` | Corresponding positive initial product-formation rate, in one consistent unit |

Each row is one paired observation. Keep factors and rates aligned; do not independently sort either column or pool different factors or conditions. Record the factor name, both units and the preparation/time-window provenance separately. The example requires at least three observations with varying factor values so that the fit has residual degrees of freedom.

Illustrative input layout only; replace these values with prepared measurements:

```csv
factor,initial_rate
0.025,0.00011
0.050,0.00020
0.100,0.00039
0.200,0.00076
```

## Fit and save the result

Run this Python example from the directory containing the supplied CSV. Edit the metadata to describe that series. For a pressure series, change the factor name and unit to the measured hydrogen pressure and its unit; the fitting procedure is the same.

```python
import csv
import json
from math import isfinite, log
from pathlib import Path
from scipy.stats import linregress

factor_name = "reagent concentration"
factor_unit = "mol/L"
rate_unit = "mol/L/s"

with Path("initial-rates.csv").open(encoding="utf-8", newline="") as stream:
    rows = list(csv.DictReader(stream))
factor = [float(row["factor"]) for row in rows]
rate = [float(row["initial_rate"]) for row in rows]

if len(factor) < 3:
    raise ValueError("Supply at least three paired observations.")
if not all(isfinite(v) and v > 0 for v in factor + rate):
    raise ValueError("Factors and rates must be positive and finite.")
if len(set(factor)) < 2:
    raise ValueError("The factor must vary within the series.")

x = [log(v) for v in factor]
y = [log(v) for v in rate]
fit = linregress(x, y, nan_policy="raise")
statistics = {
    "order": float(fit.slope),
    "intercept": float(fit.intercept),
    "order_stderr": float(fit.stderr),
    "r_squared": float(fit.rvalue ** 2),
    "p_slope_zero": float(fit.pvalue),
}
if not all(isfinite(v) for v in statistics.values()):
    raise ValueError("Non-finite regression statistics; inspect the series.")

report = {
    "factor": factor_name,
    "factor_unit": factor_unit,
    "rate_unit": rate_unit,
    "factor_range": [min(factor), max(factor)],
    "n": len(factor),
    "log_base": "natural",
    **statistics,
}
Path("reaction-order.json").write_text(
    json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
)
print(json.dumps(report, indent=2, allow_nan=False))
```

This leaves the input intact and writes `reaction-order.json` in the working directory, replacing an existing file at that path. Change the output filename for each additional series. Missing columns, malformed numbers and invalid inputs raise errors; do not silently drop those observations or replace zero rates before taking logarithms.

## Interpret the fit

The fitted relationship is `ln(rate) = intercept + order * ln(factor)`, using numerical values in the recorded units. `order` is dimensionless and describes the apparent dependence over the supplied factor range. Changing units consistently shifts the intercept, not the order. The intercept incorporates the fixed conditions and is not automatically the full reaction's rate constant.

`order_stderr` is the standard error of the slope under the regression's residual-normality assumption. `r_squared` describes linear fit quality in log space. Inspect the log-log data for curvature and influential observations before summarizing the series with a single order; no universal acceptance cutoff is supplied.

`p_slope_zero` tests a zero slope using SciPy's default two-sided alternative. It does not test whether the order equals one. An order near one describes approximately first-order dependence under these conditions; it does not alone establish an elementary reaction or a unique mechanism. Empty or invalid series and non-finite statistics provide no usable estimate in this workflow.

For return-field definitions and statistical assumptions, consult the [official linregress reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html).
