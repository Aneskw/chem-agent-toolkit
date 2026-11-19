---
name: scipy-check-depletion-and-catalyst-rate-linearity
description: Use SciPy to assess first-order reactant depletion from quantified concentration-time data and proportional initial-rate dependence on catalyst loading.
---

# Reaction-order diagnostics with SciPy

Fit the supplied kinetic measurements and return coefficients, uncertainty estimates and residuals. Measurement acquisition, NMR integration/calibration and extraction of initial rates happen before this workflow. These regressions assess particular kinetic relationships; they do not establish a complete rate law or reaction mechanism by themselves.

## Environment and input contract

Use **SciPy 1.18.1** with Python >=3.12 and NumPy >=2.0,<2.8. Follow the [official installation guide](https://scipy.org/install/) to create an environment, then install the pinned package:

```bash
python -m pip install "scipy==1.18.1"
```

The examples use NumPy arrays and [`scipy.stats.linregress`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html). No plotting dependency is required.

Supply either table below as a comma-separated file with one header row and exactly two numeric columns. The filenames and units are example conventions; adapt them together with the output labels.

| Input | Columns | Preparation |
| --- | --- | --- |
| `depletion.csv` | `time_h,concentration_mM` | One reactant and one experimental condition per fit; select and document a chemically justified time interval before fitting. Concentrations must be positive. |
| `catalyst_rates.csv` | `catalyst_mM,initial_rate_mM_per_h` | Independently determined initial rates across catalyst loadings; hold other reaction conditions fixed. Specify whether concentration counts catalyst molecules/dimers or metal centers. |

Keep row provenance, selected interval and units with the report. Do not combine separate reactants into one regression. Zeros and measurements below quantification limits need a measurement-specific decision before logarithms; do not replace them with arbitrary small numbers.

## Reactant depletion

For a first-order depletion model, `ln(c/c_ref) = intercept - k_app*t`. Here `c_ref = 1 mM`, so the logarithm uses the numeric concentration in the declared unit. Changing that unit changes the intercept but not the fitted time slope. An apparent constant has inverse-time units; identifying an intrinsic rate constant requires the appropriate experimental controls.

The following normal path loads the externally supplied, preselected interval, checks the arrays, and retains the fit and residuals in memory. It requires at least three observations to report regression uncertainty and distinct time values. These checks are computational prerequisites, not a criterion for scientific adequacy.

```python
import numpy as np
from scipy.stats import linregress


def load_xy(path):
    xy = np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)
    if xy.shape[1] != 2 or xy.shape[0] < 3:
        raise ValueError("Supply two numeric columns and at least three rows")
    if not np.isfinite(xy).all():
        raise ValueError("Resolve nonfinite measurements before fitting")
    x, y = xy[:, 0], xy[:, 1]
    if np.ptp(x) == 0:
        raise ValueError("Regression requires distinct x values")
    return x, y


time_h, concentration_mM = load_xy("depletion.csv")
if np.any(concentration_mM <= 0):
    raise ValueError("Log-concentration fitting requires positive concentrations")

ln_c = np.log(concentration_mM / 1.0)  # reference concentration: 1 mM
fit = linregress(time_h, ln_c, nan_policy="raise")
fitted_ln_c = fit.intercept + fit.slope * time_h
residual_ln_c = ln_c - fitted_ln_c
summary = {
    "k_app_per_h": -fit.slope,
    "k_app_stderr_per_h": fit.stderr,
    "intercept_ln_c": fit.intercept,
    "intercept_stderr": fit.intercept_stderr,
    "r_squared": fit.rvalue**2,
    "slope_zero_pvalue": fit.pvalue,
    "n_observations": len(time_h),
}
print(summary)
# Diagnostic columns: time_h, observed ln(c/c_ref), fitted value, residual
print(np.column_stack((time_h, ln_c, fitted_ln_c, residual_ln_c)))
```

This call performs unweighted least squares in log-concentration space. Inspect residuals against time for curvature and the original concentration trace for whether the selected interval is appropriate. Repeat separately for another reactant or condition.

A negative slope gives positive `k_app`; a nonnegative slope provides no evidence of depletion under this model. `stderr` is one standard error, not a confidence-interval half-width. SciPy's standard errors assume residual normality. A high R-squared or a small slope-zero p-value alone does not establish first-order kinetics: that p-value tests whether the fitted slope is zero.

## Catalyst-loading dependence

Use this branch when initial rates are already supplied. Run it with the imports and `load_xy` function above:

```python
catalyst_mM, initial_rate = load_xy("catalyst_rates.csv")
if np.any(catalyst_mM < 0):
    raise ValueError("Catalyst concentrations cannot be negative")

rate_fit = linregress(catalyst_mM, initial_rate, nan_policy="raise")
fitted_rate = rate_fit.intercept + rate_fit.slope * catalyst_mM
rate_residual = initial_rate - fitted_rate
rate_summary = {
    "rate_vs_catalyst_slope_per_h": rate_fit.slope,
    "slope_stderr_per_h": rate_fit.stderr,
    "intercept_mM_per_h": rate_fit.intercept,
    "intercept_stderr_mM_per_h": rate_fit.intercept_stderr,
    "r_squared": rate_fit.rvalue**2,
    "slope_zero_pvalue": rate_fit.pvalue,
    "n_observations": len(catalyst_mM),
}
print(rate_summary)
# Diagnostic columns: catalyst_mM, observed rate, fitted rate, residual
print(np.column_stack((catalyst_mM, initial_rate, fitted_rate, rate_residual)))
```

`linregress` estimates an intercept; it does not force the line through zero. Proportional initial-rate dependence on catalyst loading is consistent with first-order catalyst dependence over the measured range when the intercept is compatible with zero and residuals support a straight-line fit. Assess compatibility using the uncertainty and experimental context; do not substitute a universal R-squared cutoff. The returned slope is the rate-versus-loading coefficient, not a fitted reaction-order exponent or the complete multireactant rate constant.

## Report and failure handling

Return the summary dictionary, observed/fitted/residual table, units, fitting interval or loading range, and any excluded observations with their reasons. Fits leave the input files unchanged; the examples print results and keep arrays in memory. Save them only to a caller-chosen output path.

Malformed CSV files, nonfinite entries, nonpositive concentrations for the log transform, or identical x values must be resolved before fitting. Missing data are not silently omitted: `nan_policy="raise"` makes NaNs an error. Constant response data or nonfinite diagnostic values do not constitute a successful kinetic inference; report the uninformative fit rather than treating it as evidence of an order. Too few usable observations means no supported fit, not a zero rate constant.
