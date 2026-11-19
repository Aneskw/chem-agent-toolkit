---
name: scipy-fit-eyring-temperature-dependence
description: Fit an Eyring relationship with SciPy from measured temperatures and comparable positive rate constants; obtain activation enthalpy, regression uncertainty and residuals. Use after rate constants have been determined for one experimental regime.
---

# Analyse temperature-dependent rates with an Eyring fit

## Prepare the environment and inputs

Use Python 3.12 or later with **SciPy 1.18.1**. Follow the official [SciPy setup instructions](https://scipy.org/install/); in an activated Python environment install the pinned release:

```sh
python -m pip install "scipy==1.18.1"
```

NumPy is a SciPy dependency. The workflow starts with independently determined rate constants; it does not fit kinetic traces or establish a reaction mechanism.

Supply a numeric, comma-separated `rates.csv` in the working directory with exactly these header names:

| Column | Required meaning |
| --- | --- |
| `T_K` | Absolute temperature in kelvin; convert Celsius with `T_K = T_C + 273.15`. |
| `kobs_s_inv` | Positive observed rate constant in s⁻¹. Divide min⁻¹ values by 60 before use. |

Each row pairs one temperature with its measured rate constant. Keep catalyst/substrate conditions, medium and the definition of `kobs` comparable across rows. Use at least three observations and at least two distinct temperatures for regression with residual degrees of freedom. Independently measured replicates may share a temperature. Missing, infinite and nonpositive values require correction at the input; do not silently discard them.

## Fit and retain results

Run this template in the directory containing the real input file. It uses unweighted least squares on `x = 1/T` and `y = ln(kobs/T)` with natural logarithms. Numerical logarithms use the stated kelvin and second units.

```python
import json
from pathlib import Path
import numpy as np
from scipy.stats import linregress

# External input: measured rates.csv, with T_K,kobs_s_inv header.
data = np.genfromtxt("rates.csv", delimiter=",", names=True, ndmin=1)
T = np.asarray(data["T_K"], dtype=float)
k = np.asarray(data["kobs_s_inv"], dtype=float)
if T.size < 3:
    raise ValueError("Need at least three paired observations")
if not (np.all(np.isfinite(T)) and np.all(np.isfinite(k))):
    raise ValueError("Resolve missing or nonfinite measurements")
if np.any(T <= 0) or np.any(k <= 0):
    raise ValueError("Temperatures and rate constants must be positive")
if np.unique(T).size < 2:
    raise ValueError("Need more than one temperature")

x = 1.0 / T
y = np.log(k) - np.log(T)  # ln(k/T), avoiding intermediate ratio underflow
fit = linregress(x, y)
y_fit = fit.intercept + fit.slope * x
residual = y - y_fit
R = 8.314462618  # J mol^-1 K^-1
summary = {
    "n": int(T.size),
    "slope_K": float(fit.slope),
    "intercept": float(fit.intercept),
    "slope_stderr_K": float(fit.stderr),
    "intercept_stderr": float(fit.intercept_stderr),
    "rvalue": float(fit.rvalue),
    "r_squared": float(fit.rvalue**2),
    "deltaH_kJ_mol": float(-R * fit.slope / 1000),
    "deltaH_stderr_kJ_mol": float(R * fit.stderr / 1000),
}
if not all(np.isfinite(v) for v in summary.values()):
    raise ValueError("Nonfinite regression result; inspect input and variation")
print(json.dumps(summary, indent=2))
Path("eyring-summary.json").write_text(
    json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
)
np.savetxt(
    "eyring-fit.csv",
    np.column_stack((T, k, x, y, y_fit, residual)),
    delimiter=",", comments="",
    header="T_K,kobs_s_inv,invT_K_inv,ln_kobs_over_T,ln_fit,residual",
)
```

The two output files are overwritten if they already exist. The input remains unchanged, and output rows retain its order. For an Eyring plot, place `invT_K_inv` on the horizontal axis and `ln_kobs_over_T` on the vertical axis; overlay `ln_fit` after sorting by the horizontal coordinate. Inspect residuals against temperature or `1/T` for curvature and outliers. The CSV supplies these plot coordinates without requiring a plotting library.

## Interpret the fit

- **Enthalpy:** `ΔH‡ = −R × slope`. The reported value is in kJ mol⁻¹ and is an apparent activation enthalpy when fitted to an observed composite rate constant. Do not label it Arrhenius activation energy.
- **Uncertainty:** `stderr` and `intercept_stderr` are coefficient standard errors under residual normality, not confidence interval widths. The enthalpy standard error scales the slope error by `R`. These errors do not include temperature uncertainty or uncertainty from the upstream determination of rate constants. Retain the result object: five-value tuple unpacking loses `intercept_stderr`.
- **Fit quality:** `rvalue**2` is the coefficient of determination. A high value alone does not validate a mechanism. Systematic residual structure calls the single straight-line description into question. `linregress` has no measurement-weight argument; if unequal transformed-rate uncertainties require weighting, hand off to a suitable weighted fit instead of treating these errors as weighted estimates.
- **Entropy:** retain the intercept unless the rate law and standard-state conventions justify its conversion. For the conventional first-order Eyring equation with unit transmission coefficient, using k in s⁻¹ and T in K, `ΔS‡ = R × [intercept − ln(k_B/h)]`, with `k_B/h` expressed in K⁻¹ s⁻¹. A pseudo-first-order `kobs` can include concentration-dependent factors, so its intercept need not yield an intrinsic activation entropy. Second-order constants need a reference-concentration treatment and do not belong directly in this s⁻¹ input contract. Multiplying all rate numbers by a constant `a` shifts the intercept by `ln(a)` and inferred entropy by `R ln(a)`, leaving the slope unchanged.

Use the [SciPy linregress interface reference](https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.linregress.html) for coefficient meanings and confidence-interval examples. The [Eyring equation and reference-concentration convention](https://www.cup.uni-muenchen.de/ch/compchem/vib/eyring1.html), equations (2)–(3), explain the activation-parameter mapping.
