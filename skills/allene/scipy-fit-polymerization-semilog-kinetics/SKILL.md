---
name: scipy-fit-polymerization-semilog-kinetics
description: Estimate apparent polymerization rate constants from measured conversion-time or residual-monomer data using SciPy semilog regression, with unit handling and fit diagnostics.
---

# Apparent polymerization rates from semilog regression

Fit `-ln([M]/[M]0) = intercept + k_app * time` with SciPy. Start with numerical measurements from one reaction under consistent conditions. Measurement acquisition, spectral integration, SEC processing, and figure digitization must already be complete.

## Environment and inputs

Use **SciPy 1.18.1**, **Python 3.12**, and a compatible NumPy version (`>=2.0.0,<2.8`). Follow the [official SciPy installation instructions](https://scipy.org/install/) to create an environment, then install the pinned SciPy release:

```sh
python -m pip install "scipy==1.18.1"
```

Prepare a CSV named `kinetics.csv` in the working directory:

| Column | Meaning |
| --- | --- |
| `time_s` | Elapsed reaction time in seconds; convert minutes by multiplying by 60 or hours by 3600. |
| `conversion` | Monomer conversion as a fraction, `0 <= X < 1`; divide percentages by 100. |

Each row is a paired measurement. Use at least three finite pairs and at least two distinct times to retain residual degrees of freedom. Choose the analysis interval explicitly and retain that choice with the results; do not select points merely to improve R-squared. Do not silently discard missing values or clip complete conversion below 1: the logarithm is undefined at `X = 1`.

For residual-concentration inputs, supply initial concentration `M0 > 0` and measured concentrations `M` in the same units, with `0 < M <= M0`. Convert to `X = 1 - M/M0` before using the CSV path, or calculate `y = -np.log(M/M0)` directly. This assumes concentration ratios represent the remaining monomer fraction; changing reaction volume requires appropriate preparation outside this fit.

Fit independent reaction replicates separately and preserve their identifiers, conditions and selected intervals. Do not pool distinct replicates into one trace merely to obtain a single slope; compare the per-replicate estimates afterward.

## Fit and retain diagnostics

The following template reads the measured CSV and writes `semilog-fit.json` and `semilog-points.csv` in the working directory, replacing files with those names. It uses ordinary, unweighted least squares with a fitted intercept. SciPy's [linregress interface](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html) documents the result attributes and NaN handling.

```python
import csv
import json
import numpy as np
from scipy.stats import linregress

with open("kinetics.csv", newline="", encoding="utf-8-sig") as handle:
    rows = list(csv.DictReader(handle))
time_s = np.array([float(row["time_s"]) for row in rows], dtype=float)
X = np.array([float(row["conversion"]) for row in rows], dtype=float)

if len(time_s) < 3:
    raise ValueError("Need at least three paired measurements for this fit.")
if not (np.isfinite(time_s).all() and np.isfinite(X).all()):
    raise ValueError("Resolve nonfinite measurements before fitting.")
if np.ptp(time_s) == 0:
    raise ValueError("Elapsed times must not all be identical.")
if np.any((X < 0) | (X >= 1)):
    raise ValueError("Conversion must be a fraction in [0, 1).")

y = -np.log1p(-X)
result = linregress(time_s, y, nan_policy="raise")
fitted = result.intercept + result.slope * time_s
residual = y - fitted

summary = {
    "n": len(time_s),
    "time_unit": "s",
    "intercept_fitted": True,
    "k_app_s_inv": float(result.slope),
    "k_app_stderr_s_inv": float(result.stderr),
    "intercept": float(result.intercept),
    "intercept_stderr": float(result.intercept_stderr),
    "r_squared": float(result.rvalue**2),
}
# Reject undefined statistics rather than emitting nonstandard JSON NaNs.
with open("semilog-fit.json", "w", encoding="utf-8") as handle:
    handle.write(json.dumps(summary, indent=2, allow_nan=False) + "\n")
with open("semilog-points.csv", "w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle)
    writer.writerow(["time_s", "conversion", "minus_ln_remaining",
                     "fitted", "residual"])
    writer.writerows(zip(time_s, X, y, fitted, residual))
print(summary)
```

The transformation `-np.log1p(-X)` evaluates `-ln(1-X)`. Preserve the measured input file and record the conditions and included interval beside the outputs. Retain the intercept: `linregress` does not constrain the line through zero. A required zero-intercept analysis needs a different fitting interface.

## Read the result

- **`k_app_s_inv`** is the slope, in s^-1 because time was supplied in seconds. It is an apparent rate for the analyzed interval.
- **Standard errors** describe the fitted slope and intercept under the regression's residual-normality assumption in transformed space. They do not propagate measurement uncertainty in conversion or time. Log transformation magnifies conversion errors near complete conversion.
- **R-squared and residuals** describe agreement with a straight line. Inspect measured and fitted semilog values against time and residuals against time; curvature or systematic departures limit a single-rate interpretation. Do not impose an unsupported universal R-squared cutoff.
- **Constant conversion, a negative slope, or nonfinite statistics** require inspecting the measurements and chosen interval. Constant conversion resolves no kinetic increase; a negative slope contradicts increasing conversion. Do not report undefined statistics as a successful estimate. Malformed CSV values, invalid conversions, or unresolved NaNs stop the template with an exception.

A straight semilog relationship supports an apparent kinetic description over the supplied interval. It does not alone establish controlled or living polymerization, or identify a mechanism.
