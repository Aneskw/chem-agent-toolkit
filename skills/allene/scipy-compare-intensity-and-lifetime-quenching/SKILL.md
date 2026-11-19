---
name: scipy-compare-intensity-and-lifetime-quenching
description: Fit Stern–Volmer intensity ratios and optional independently fitted lifetime ratios with SciPy, inspect regression diagnostics, and compare quenching trends from prepared measurements.
---

# Fit and compare Stern–Volmer relationships

Use this workflow with concentration-dependent fluorescence measurements that are already comparable across samples. It performs unweighted linear regression with a free intercept. Measurement acquisition, spectral correction and fitting lifetimes from raw decay traces are external preparation.

## Environment and inputs

Use Python >=3.12 and [SciPy 1.18.1](https://pypi.org/project/scipy/1.18.1/). Follow the official [installation guide](https://scipy.org/install/) to create and activate a virtual environment, then install the pinned package:

```sh
python -m pip install scipy==1.18.1
```

Installing SciPy also installs its compatible NumPy dependency.

| Input | Contract |
| --- | --- |
| Quencher concentration | One-dimensional array, one value per measurement; convert its declared units to mol/L before fitting. |
| Intensity and I0 | Positive, finite measured intensities and an unquenched reference in the same units, using the same spectral readout and preparation. |
| Optional lifetime and tau0 | Positive, finite, independently fitted lifetimes and an unquenched lifetime in the same time units. Pair each lifetime with its corresponding concentration. |
| Series selection | Use the intended concentration range; retain the selection and any exclusions in the report. Do not select points solely to improve R-squared. |

Check matching lengths, finite values and variation in concentration. More than two observations are needed to estimate residual error. Do not infer missing intensities or lifetimes from a plotted regression line.

## Representative analysis

The following values are illustrative inputs, not published measurements or execution results. Replace them and the references with prepared measurements. The zero-concentration point is included in this example.

```python
import numpy as np
from scipy.stats import linregress

q_uM = np.array([0, 50, 100, 150, 200], dtype=float)
q_M = q_uM * 1e-6  # micromol/L -> mol/L
intensity = np.array([1000, 900, 805, 730, 660], dtype=float)
I0 = 1000.0

ratio_I = I0 / intensity
fit_I = linregress(q_M, ratio_I)
predicted_I = fit_I.intercept + fit_I.slope * q_M
residual_I = ratio_I - predicted_I

report = {
    "intensity": {
        "slope_L_per_mol": fit_I.slope,
        "intercept": fit_I.intercept,
        "r_squared": fit_I.rvalue**2,
        "slope_stderr_L_per_mol": fit_I.stderr,
        "intercept_stderr": fit_I.intercept_stderr,
    }
}
# Columns: concentration_M, observed_ratio, fitted_ratio, residual
diagnostics = {
    "intensity": np.column_stack((q_M, ratio_I, predicted_I, residual_I))
}
```

For the optional lifetime comparison, supply independently fitted lifetimes. Use the same concentration array only when it describes those measurements:

```python
tau_ns = np.array([3.20, 3.18, 3.21, 3.17, 3.19], dtype=float)
tau0_ns = 3.20
ratio_tau = tau0_ns / tau_ns
fit_tau = linregress(q_M, ratio_tau)
predicted_tau = fit_tau.intercept + fit_tau.slope * q_M

report["lifetime"] = {
    "slope_L_per_mol": fit_tau.slope,
    "intercept": fit_tau.intercept,
    "r_squared": fit_tau.rvalue**2,
    "slope_stderr_L_per_mol": fit_tau.stderr,
    "intercept_stderr": fit_tau.intercept_stderr,
}
diagnostics["lifetime"] = np.column_stack(
    (q_M, ratio_tau, predicted_tau, ratio_tau - predicted_tau)
)

# Only for matched measurements at the same q_M values and conditions:
diagnostics["paired_comparison"] = np.column_stack(
    (q_M, ratio_I, ratio_tau, ratio_I - ratio_tau, ratio_I / ratio_tau)
)
# Columns: concentration_M, I0_over_I, tau0_over_tau,
#          ratio_difference, intensity_over_lifetime_ratio
```

These operations leave the supplied measurements unchanged. Results reside in `report` and `diagnostics`; no files are written. Return both with the input units, reference values and fitted concentration range. Inspect the observed ratios, fitted ratios and residuals against concentration when judging the linear model.

## Read the result

- The slope is the fitted Stern–Volmer coefficient in L/mol for concentrations in mol/L. Ratios and intercepts are dimensionless. Fitting directly in micromol/L instead would change the numerical slope by a factor of one million.
- `linregress` estimates the intercept; normalization does not constrain it to one. Inspect departures from one alongside reference preparation and residuals.
- `rvalue**2` describes the linear fit. Curved residual patterns indicate that one linear slope does not describe the chosen range adequately. Do not silently replace the model or remove points.
- `stderr` and `intercept_stderr` are regression standard errors under residual-normality assumptions. This calculation does not propagate measurement or shared-reference uncertainty.
- Compare intensity and lifetime trends when both are available. A linear intensity plot or high R-squared alone does not establish a quenching mechanism. Keep the fitted relationship distinct from mechanistic conclusions.
- Missing/NaN inputs propagate to NaN results under the default policy. Reject or explicitly resolve missing observations before fitting; identical concentrations cannot define a slope. A near-zero slope can be a meaningful lack of concentration dependence and must not be treated as a failed fit.

## Compare intensity and lifetime evidence

Match the same emitting species, conditions and concentration range before comparing the two observables. The paired table above requires identical measured concentration rows; otherwise retain separate fits or explicitly align matching concentrations. Compare the measured ratios and their differences as well as slopes and residuals. The ratio difference and ratio-of-ratios are dimensionless diagnostics, without a universal acceptance threshold.

| Pattern, assessed against measurement uncertainty | Conditional interpretation |
| --- | --- |
| `I0/I` and `tau0/tau` agree and follow the same increasing line | Consistent with the simple dynamic-quenching model: both equal `1 + kq*tau0*[Q]`. Check the intercepts against 1 and retain their uncertainty. |
| Intensity decreases but the emitting population's lifetime remains approximately unchanged | Compatible with a nonemissive ground-state complex removing part of the fluorescent population (static quenching), subject to optical and sample-preparation checks. |
| Different concentration dependence or curved residuals | Examine mixed quenching, heterogeneous emitters or measurement artifacts before interpreting one apparent slope as a single process. |

The dynamic relation is defined by [IUPAC](https://goldbook.iupac.org/terms/view/S06004); the [instrument manufacturer's Stern-Volmer guide](https://www.edinst.com/resource/what-is-a-stern-volmer-plot/) explains the lifetime distinction for static quenching. Before assigning a discrepancy to chemistry, check dilution, inner-filter absorption/reabsorption, photobleaching and consistent excitation/detection. Keep the lifetime definition explicit for multiexponential decays. These comparisons do not distinguish electron transfer from energy transfer or establish a unique mechanism.

The simple regressions do not include shared-reference uncertainty or correlation between ratios. Their standard errors alone are insufficient for a formal test of equality between the two trends; use an independently justified error model if that inference is required.

For return-field and missing-data details, consult the [SciPy linregress reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html).
