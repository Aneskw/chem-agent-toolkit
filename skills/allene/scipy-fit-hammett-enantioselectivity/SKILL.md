---
name: scipy-fit-hammett-enantioselectivity
description: Fit para-substituent Hammett constants against log10(S/R) with SciPy, starting from matched enantiomer ratios or signed product ee, and report slope, uncertainty and residuals.
---

# Fit a Hammett relationship for enantioselectivity

Use an unweighted linear fit with a freely estimated intercept. Supply measured selectivities and externally chosen, matched para-substituent constants; chromatography integration and selection of constants are upstream tasks.

## Environment and inputs

Use Python 3.12 or newer and **SciPy 1.18.1** with NumPy. Follow the [official SciPy setup instructions](https://scipy.org/install/) to prepare a virtual environment, then install the pinned release:

```sh
python -m pip install "scipy==1.18.1"
```

| Input | Convention |
| --- | --- |
| `sigma_p` | Finite, dimensionless, one-dimensional array; one constant per measurement. |
| Signed ee | Percent, defined as `100*(S-R)/(S+R)`; S enrichment is positive and R enrichment negative. Unsigned ee requires the major enantiomer assignment before conversion. |
| Alternative selectivity input | A finite positive `S/R` ratio, or an already calculated finite `log10(S/R)`, with matching row order. |

For ee as a fraction `e`, use `S/R = (1+e)/(1-e)`. Zero ee is valid and gives a zero logarithm. Values of ±100% give an infinite or undefined logarithm: keep those measurements in the source data but omit them from this finite-response fit and report the exclusion. Never substitute an arbitrary small denominator. Reject ee outside ±100% as invalid input. Keep the S/R orientation fixed across the series; switching to R/S reverses the logarithm and fitted slope.

## Fit and export

Replace the arrays below with matched measurements from a consistent experimental series. This example uses the six `sigma_p` and tabulated logarithms from [Supplementary Table S7, S158](https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-025-57381-w/MediaObjects/41467_2025_57381_MOESM1_ESM.pdf). Using the tabulated logarithms avoids recalculating them from rounded ee percentages.

```python
import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import linregress

sigma_p = np.array([-0.27, -0.17, 0.00, 0.06, 0.23, 0.54], dtype=float)
log_ratio = np.array([0.9789, 1.1949, 1.2787, 1.5096, 1.5911, 1.8173], dtype=float)

# Alternative to log_ratio above: convert your signed ee percentages.
# ee_percent = np.asarray(your_signed_ee_percent, dtype=float)
# e = ee_percent / 100.0
# After checking finite values and -1 < e < 1:
# log_ratio = np.log10((1.0 + e) / (1.0 - e))
# For supplied S/R ratios, check positivity and use np.log10(S_over_R).

if sigma_p.ndim != 1 or log_ratio.shape != sigma_p.shape:
    raise ValueError("Provide paired one-dimensional arrays of equal length")
if len(sigma_p) < 3:
    raise ValueError("This example needs at least three points for uncertainty estimates")
if not (np.isfinite(sigma_p).all() and np.isfinite(log_ratio).all()):
    raise ValueError("Resolve nonfinite input rows before fitting")
if np.ptp(sigma_p) == 0:
    raise ValueError("Distinct sigma_p values are required to estimate a slope")

fit = linregress(sigma_p, log_ratio)  # default: two-sided zero-slope test
fitted = fit.intercept + fit.slope * sigma_p
residual = log_ratio - fitted
summary = {
    "slope_rho": fit.slope,
    "intercept": fit.intercept,
    "r_squared": fit.rvalue**2,
    "slope_stderr": fit.stderr,
    "intercept_stderr": fit.intercept_stderr,
    "slope_pvalue_two_sided": fit.pvalue,
    "n": len(sigma_p),
}
# Represent undefined statistics as JSON null, not nonstandard NaN literals.
summary = {k: float(v) if math.isfinite(v) else None
           for k, v in summary.items()}
summary["n"] = len(sigma_p)

# These two files are written in the current directory and replace existing files.
Path("fit_summary.json").write_text(
    json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
)
with open("hammett_points.csv", "w", newline="", encoding="utf-8") as stream:
    writer = csv.writer(stream)
    writer.writerow(["sigma_p", "log10_S_over_R", "fitted", "residual"])
    writer.writerows(zip(sigma_p, log_ratio, fitted, residual))
```

The input arrays retain their order and values. `fit_summary.json` holds the coefficients and inference fields; `hammett_points.csv` holds each observed response, fitted response and observed-minus-fitted residual. Record any excluded rows and the original ratio/ee convention alongside the analysis when using your own data.

## Interpret the result

- **Slope (`rho`) and intercept:** Fit `log10(S/R) = intercept + rho*sigma_p`. A positive slope associates increasing `sigma_p` with increasing S/R under the selected conditions. The intercept is the fitted log10(S/R) at zero `sigma_p`; do not force it to zero.
- **Uncertainty:** `slope_stderr` and `intercept_stderr` are standard errors under the residual-normality assumption. `slope_pvalue_two_sided` tests a zero slope; it does not test linearity or establish a reaction mechanism.
- **Fit quality:** `r_squared` is the squared Pearson correlation. Inspect residuals for curvature or individual points dominating the trend before summarizing the relationship with one slope. There is no universal acceptance cutoff here.
- **Undefined results:** Empty/insufficient or nonfinite inputs and constant `sigma_p` cannot support this workflow's inference. A constant response can give a zero slope but undefined correlation/inference fields; the example exports these as `null`. Report the flat response and undefined fields explicitly rather than treating them as a successful mechanistic correlation.

`linregress` performs unweighted least squares and has no measurement-weight argument. Its standard errors do not propagate errors in `sigma_p` or the nonlinear ee-to-log conversion. An analysis requiring those error models needs a separately justified fitting method. See the [SciPy linregress interface](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html) for parameter and result-field details.
