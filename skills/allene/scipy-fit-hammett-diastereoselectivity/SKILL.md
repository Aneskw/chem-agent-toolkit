---
name: scipy-fit-hammett-diastereoselectivity
description: Fit and interpret a Hammett correlation with SciPy when matched para-substituent constants and prepared logarithmic diastereoselectivity values are available.
---

# Hammett selectivity regression with SciPy

Fit an unweighted straight line to supplied `sigma_para` and `log_dr` values. This workflow returns coefficients, fit statistics and labeled residuals. Substituent-constant selection, NMR integration and conversion of measurements to quantitative selectivity ratios happen upstream.

## Environment

Use **SciPy 1.18.1** with Python **3.12 or newer** in a virtual environment. Follow the [official installation guide](https://scipy.org/install/); the pinned pip command is:

```sh
python -m pip install "scipy==1.18.1"
```

The package requires NumPy `>=2.0.0,<2.8`, which pip resolves. The [linregress reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html) explains its parameters and result fields.

## Prepare paired inputs

Provide a UTF-8 CSV, `hammett.csv`, with these columns. Each row represents one matched observation; preserve the substituent label throughout fitting.

| Column | Meaning |
| --- | --- |
| `substituent` | Label identifying the measurement and substituent |
| `sigma_para` | Supplied dimensionless para-substituent constant, used as x |
| `log_dr` | Supplied logarithmic selectivity response, used as y |

Record the logarithm base and ratio orientation with the data. Every row must use the same convention, such as `log10(anti/syn)`. Reversing the ratio changes the slope sign; changing the logarithm base changes its scale. Do not mix constant scales or reaction conditions within one correlation without a justified analysis plan.

Use finite numerical values, more than two observations and at least two distinct x values. Values reported only as bounds, such as `>20:1`, are not exact responses: obtain quantitative upstream data or report the unresolved rows rather than treating the bound as a measured value. This workflow does not fit censored data or incorporate measurement-error weights.

## Fit and access results

The example reads the prepared CSV. Set `response_convention` to match its actual preparation; the string below is an illustrative convention. Paths are relative to the working directory unless made absolute.

```python
import csv
import numpy as np
from scipy import stats

input_path = "hammett.csv"  # External prepared data
response_convention = "log10(anti/syn)"  # Match upstream preparation

with open(input_path, newline="", encoding="utf-8-sig") as stream:
    rows = list(csv.DictReader(stream))

labels = [row["substituent"] for row in rows]
x = np.asarray([float(row["sigma_para"]) for row in rows], dtype=float)
y = np.asarray([float(row["log_dr"]) for row in rows], dtype=float)

if x.size <= 2:
    raise ValueError("Need more than two paired observations for fit statistics")
if not (np.isfinite(x).all() and np.isfinite(y).all()):
    raise ValueError("Resolve nonfinite inputs before fitting")
if np.ptp(x) == 0:
    raise ValueError("sigma_para must vary")

result = stats.linregress(x, y, nan_policy="raise")
fitted = result.intercept + result.slope * x
residuals = y - fitted

summary = {
    "n": int(x.size),
    "response_convention": response_convention,
    "slope": float(result.slope),
    "intercept": float(result.intercept),
    "r_squared": float(result.rvalue**2),
    "slope_stderr": float(result.stderr),
    "intercept_stderr": float(result.intercept_stderr),
    "pvalue_two_sided": float(result.pvalue),
}
paired_results = [
    {
        "substituent": label,
        "sigma_para": float(xi),
        "log_dr": float(yi),
        "fitted_log_dr": float(fi),
        "residual": float(ri),
    }
    for label, xi, yi, fi, ri in zip(labels, x, y, fitted, residuals)
]
print(summary)
for row in paired_results:
    print(row)
```

`summary` and `paired_results` remain available in memory and are printed. The call creates no files and does not mutate the source CSV. Missing columns or nonnumeric fields raise errors during loading; correct the upstream data rather than silently dropping observations. `nan_policy="raise"` rejects NaNs, while the explicit finite check also catches infinities.

## Interpret the fit

- **Slope and intercept:** describe the supplied logarithmic response per unit of `sigma_para` and its fitted value at zero. Interpret the sign using the recorded ratio orientation. These are unweighted least-squares estimates.
- **R-squared:** use `result.rvalue**2`, not `result.rvalue`. It describes the linear association in the supplied data; it does not establish a reaction mechanism.
- **Uncertainty:** `stderr` and `intercept_stderr` are standard errors, not confidence intervals. SciPy documents them under an assumption of residual normality. The default two-sided p-value tests a zero slope; it is not a probability that a proposed mechanism is correct.
- **Residuals:** inspect labeled residuals against x and fitted responses for systematic curvature or influential observations before using the line. Fitted responses and residuals remain in the supplied logarithmic units.

Check for nonfinite coefficients or statistics, especially with constant responses or degenerate inputs; these do not constitute a usable statistical result. An empty or insufficient dataset produces no meaningful correlation. Report the data gap rather than a slope. If a figure is requested, plot the observed pairs and the fitted line on the same declared scales, sorting x for the line while retaining original pairing in the reported table.
