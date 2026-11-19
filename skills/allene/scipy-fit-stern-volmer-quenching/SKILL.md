---
name: scipy-fit-stern-volmer-quenching
description: Fit prepared luminescence-quenching measurements with SciPy to estimate Stern–Volmer constants, inspect linear-fit diagnostics, and calculate conditional bimolecular quenching rates when an appropriate unquenched lifetime is available.
---

# Stern–Volmer quenching regression with SciPy

Use ordinary, unweighted linear regression of `I0/I` against quencher concentration to obtain an apparent Stern–Volmer constant. Start with prepared measurements; instrument acquisition, spectral corrections and lifetime-decay fitting are external inputs to this workflow.

## Setup

Use **SciPy 1.18.1**, Python **3.12 or newer**, and standard NumPy CPU arrays (NumPy **>=2.0,<2.8**). Obtain Python from [python.org](https://www.python.org/downloads/). In an activated virtual environment, follow the official [SciPy installation guide](https://scipy.org/install/#installing-with-pip), pinning this release:

```sh
python -m pip install "scipy==1.18.1"
```

The [linregress reference](https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.linregress.html) describes the result attributes and NaN policy used below; retain attribute access to obtain `intercept_stderr`.

## Prepare the measurements

| Input | Contract |
|---|---|
| `Q` | One-dimensional finite concentrations, **mol/L**, matched row-for-row to `I`; nonnegative with at least two distinct concentrations. Convert mM by multiplying by `1e-3`. |
| `I` | Positive, finite intensities, all using the same prepared emission observable, wavelength/band and measurement conditions. |
| `I0` | Positive, finite scalar intensity measured without quencher, on the same scale as `I`. |
| `tau0_s` | Optional independently measured **unquenched excited-state lifetime in seconds**, matched to the emitting species, solvent and temperature of the quenching measurements. Convert ns by `1e-9`, microseconds by `1e-6`. |

Use at least three paired observations for regression uncertainty; the template enforces this. Include a measured zero-concentration point when available. Preserve paired rows and do not silently omit missing values. Supply dilution/spectral corrections before fitting if required by the measurement protocol; the regression does not perform them.

## Fit and retrieve results

The model is `ratio = intercept + KSV * Q`, where `ratio = I0/I`. `linregress` estimates both slope and intercept; it does not constrain the intercept to the ideal Stern–Volmer value of 1.

```python
import numpy as np
from scipy.stats import linregress


def fit_quenching(Q, I, I0, *, tau0_s=None, dynamic_model=False):
    Q = np.asarray(Q, dtype=float)
    I = np.asarray(I, dtype=float)
    I0 = float(I0)
    if Q.ndim != 1 or I.ndim != 1 or Q.shape != I.shape or Q.size < 3:
        raise ValueError("Supply matched 1-D Q and I with at least 3 observations")
    if not (np.isfinite(Q).all() and np.isfinite(I).all()
            and np.isfinite(I0)):
        raise ValueError("Concentrations and intensities must be finite")
    if (Q < 0).any() or np.unique(Q).size < 2:
        raise ValueError("Q must be nonnegative and span distinct concentrations")
    if I0 <= 0 or (I <= 0).any():
        raise ValueError("I0 and every I must be positive")
    if tau0_s is not None:
        tau0_s = float(tau0_s)
        if not np.isfinite(tau0_s) or tau0_s <= 0:
            raise ValueError("tau0_s must be finite and positive")
    if dynamic_model and tau0_s is None:
        raise ValueError("Dynamic rate conversion requires tau0_s")

    ratio = I0 / I
    if not np.isfinite(ratio).all():
        raise ValueError("Normalization produced nonfinite ratios")
    fit = linregress(Q, ratio, nan_policy="raise")
    fitted = fit.intercept + fit.slope * Q
    residuals = ratio - fitted
    report = {
        "KSV_L_mol": fit.slope,
        "KSV_stderr_L_mol": fit.stderr,
        "intercept": fit.intercept,
        "intercept_stderr": fit.intercept_stderr,
        "rvalue": fit.rvalue,
        "R2": fit.rvalue**2,
        "pvalue": fit.pvalue,
        "kq_L_mol_s": (fit.slope / tau0_s if dynamic_model else None),
    }
    return report, fit, fitted, residuals, ratio


# Illustrative inputs only: replace with your prepared measurements.
Q = np.array([0, 1, 2, 3, 4], dtype=float) * 1e-3  # mol/L
I = np.array([1000, 830, 710, 630, 550], dtype=float)
I0 = 1000.0
report, fit, fitted, residuals, ratio = fit_quenching(Q, I, I0)
print(report)
# Columns remain in input order: Q, observed ratio, fitted ratio, residual.
print(np.column_stack((Q, ratio, fitted, residuals)))

# Optional, only after independent support for a dynamic-quenching model:
# report, fit, fitted, residuals, ratio = fit_quenching(
#     Q, I, I0, tau0_s=measured_tau0_seconds, dynamic_model=True)
```

The returned arrays and regression object remain in memory; no input is modified and no files are written. For a plotted line, sort `Q` and `fitted` with the same index. For repeated quencher comparisons, fit each matched series separately and retain its concentration range, measurement conditions and reference intensity with the report.

## Interpret the fit

- `KSV_L_mol` is the slope in **L/mol**; the fitted line and residuals are dimensionless. Inspect residuals against concentration for curvature or other structure, and assess whether the fitted intercept is consistent with 1 given measurement uncertainty. Do not force the intercept or discard points just to improve agreement.
- `stderr` and `intercept_stderr` are regression standard errors under the documented residual-normality assumption. `R2` describes fit agreement; `pvalue` tests a zero slope with the default two-sided alternative. Neither is evidence of a unique quenching mechanism. Constant ratios can produce undefined correlation and uncertainty statistics; inspect NaNs rather than reporting a successful kinetic inference.
- Under a suitable **dynamic-quenching** model, `KSV = kq * tau0`, so `kq = KSV/tau0` in **L mol^-1 s^-1**. This relationship is defined in the [IUPAC Stern–Volmer entry](https://goldbook.iupac.org/terms/view/S06004/json). Leave `dynamic_model=False` when that interpretation or the lifetime match is unsupported; `kq_L_mol_s` is then `None`. A negative slope is not a physical positive quenching-rate estimate.
- Linear intensity quenching alone does not establish dynamic quenching or distinguish energy transfer from other pathways. The unweighted fit does not model unequal or correlated errors from shared `I0`; its slope standard error excludes lifetime and reference-intensity uncertainty. Do not label it as the total uncertainty of `kq`.
## Already normalized measurements

When `I0/I` is supplied directly, use the prepared dimensionless ratios instead of normalizing them again. With matched one-dimensional arrays `Q` (mol/L) and `ratio`, require at least three finite pairs, nonnegative nonconstant concentrations and positive ratios, then run:

```python
fit = linregress(Q, ratio, nan_policy="raise")
fitted = fit.intercept + fit.slope * Q
residuals = ratio - fitted
print({"KSV_L_mol": fit.slope, "intercept": fit.intercept,
       "KSV_stderr_L_mol": fit.stderr,
       "intercept_stderr": fit.intercept_stderr,
       "R2": fit.rvalue**2, "pvalue": fit.pvalue})
print(np.column_stack((Q, ratio, fitted, residuals)))
```

The imports are the same as above. Apply the same residual, intercept, unit and mechanistic interpretation checks. Fit each quencher's matched series separately; retain its reference intensity or normalization provenance with the results.

For mixture or condition comparisons, record exactly which component or total concentration `Q` denotes. An apparent mixture slope is not automatically the constant of an individual quencher. Compare conditions with their composition and concentration definitions retained.
