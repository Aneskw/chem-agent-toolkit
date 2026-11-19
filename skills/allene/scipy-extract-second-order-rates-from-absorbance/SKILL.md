---
name: scipy-extract-second-order-rates-from-absorbance
description: Extract second-order rate constants from concentration-series absorbance decay traces with SciPy, using exponential fits followed by regression of observed rates against excess-reactant concentration.
---

# From absorbance decays to second-order rate constants

Fit each trace to `A(t) = A0 * exp(-kobs * t) + C`, then fit `kobs = k2 * concentration + intercept`. Start with prepared absorbance data from comparable experiments under pseudo-first-order conditions. Spectroscopy acquisition and chemical preparation are external inputs.

## Environment and input preparation

Use Python >=3.12 with [SciPy 1.18.1](https://pypi.org/project/scipy/1.18.1/) and NumPy. The package can be obtained with `python -m pip install scipy==1.18.1`; this also resolves its NumPy dependency.

Use traces with one reaction partner in at least tenfold excess. The published workflow uses four different excess-reactant concentrations. Keep solvent, temperature, monitored species and other reaction conditions comparable across the series. Supply concentrations after mixing, in mol/L: convert mM to M before regression.

For the residual-based regression uncertainty below, supply at least three independent trace measurements spanning at least two concentrations. Three or more concentration levels also allow checking curvature; replicates at only two levels cannot test that shape. A slope from just two traces is descriptive and has no residual degrees of freedom for a standard-error estimate.

Prepare `traces`, a list of records with these keys. Time and absorbance may have different lengths between records, but must match within each record.

| Key | Meaning |
| --- | --- |
| `concentration_M` | Positive excess-reactant concentration, mol/L; use distinct values across the series. |
| `time_s` | Finite 1-D array in seconds, increasing from zero at the first retained observation; more than three observations. |
| `absorbance` | Matching finite 1-D absorbance array. |
| `p0` | Three initial guesses in order `[A0, kobs, C]`: amplitude, rate in s^-1, baseline. |

Estimate the baseline from a justified late-time plateau when available, amplitude from the initial signal minus that baseline, and rate from the observed timescale. These are starting guesses, not fixed parameters. A trace that does not resolve decay and baseline can leave rate and baseline poorly determined.

## Fit traces and regress rates

The template below takes the supplied `traces` records. It uses unweighted, unconstrained fits with explicit initial guesses; weighting and initialization are analysis choices. Preserve the fitted baseline instead of silently treating it as zero.

```python
import warnings
import numpy as np
from scipy.optimize import curve_fit, OptimizeWarning
from scipy.stats import linregress


def decay(t, A0, kobs, C):
    return A0 * np.exp(-kobs * t) + C


def fit_trace(record):
    t = np.asarray(record['time_s'], dtype=np.float64)
    a = np.asarray(record['absorbance'], dtype=np.float64)
    p0 = np.asarray(record['p0'], dtype=np.float64)
    if (t.ndim != 1 or a.shape != t.shape or t.size <= 3
            or not np.all(np.isfinite(t))
            or not np.all(np.isfinite(a))):
        raise ValueError('Need matching finite 1-D time/absorbance arrays, length >3')
    if t[0] != 0 or not np.all(np.diff(t) > 0):
        raise ValueError('Supply increasing time in seconds, relative to first point')
    if p0.shape != (3,) or not np.all(np.isfinite(p0)):
        raise ValueError('p0 must be [amplitude, rate_per_second, baseline]')

    with warnings.catch_warnings():
        warnings.simplefilter('error', OptimizeWarning)
        popt, pcov = curve_fit(
            decay, t, a, p0=p0, method='lm',
            sigma=None, absolute_sigma=False, check_finite=True,
        )
    if (not np.all(np.isfinite(popt)) or popt[1] <= 0
            or not np.all(np.isfinite(pcov))
            or np.any(np.diag(pcov) < 0)):
        raise ValueError('Rate or covariance needs investigation')
    fitted = decay(t, *popt)
    return {
        'parameters': popt,             # A0, kobs, C
        'covariance': pcov,
        'kobs_s_inv': popt[1],
        'kobs_se_s_inv': np.sqrt(pcov[1, 1]),
        'covariance_condition': np.linalg.cond(pcov),
        'fitted_absorbance': fitted,
        'residuals': a - fitted,
    }


# External handoff: traces is the prepared list described above.
concentration = np.asarray(
    [row['concentration_M'] for row in traces], dtype=np.float64
)
if (concentration.ndim != 1 or concentration.size < 3
        or not np.all(np.isfinite(concentration))
        or np.any(concentration <= 0)
        or np.unique(concentration).size < 2):
    raise ValueError('Need >=3 traces at positive finite, varying concentrations')
fits = [fit_trace(row) for row in traces]
kobs = np.asarray([fit['kobs_s_inv'] for fit in fits], dtype=np.float64)
regression = linregress(concentration, kobs)
if not np.all(np.isfinite([
    regression.slope, regression.intercept, regression.stderr,
    regression.intercept_stderr, regression.rvalue,
])):
    raise ValueError('Concentration regression has unresolved statistics')
summary = {
    'k2_M_inv_s_inv': regression.slope,
    'k2_regression_se_M_inv_s_inv': regression.stderr,
    'intercept_s_inv': regression.intercept,
    'intercept_se_s_inv': regression.intercept_stderr,
    'r_squared': regression.rvalue ** 2,
}
rate_residuals = kobs - (
    regression.slope * concentration + regression.intercept
)
print(summary)
```

## Inspect and deliver the result

Treat `summary` as provisional until checking both stages:

- For each record, inspect `fits[i]['residuals']` against its time array and compare `fitted_absorbance` with the measured trace. Systematic residual structure calls the single-exponential description into question. Inspect `covariance`, `covariance_condition` and `kobs_se_s_inv`; large condition numbers can indicate unreliable parameter estimates even when the optimizer returns successfully.
- Inspect `kobs` versus `concentration` and `rate_residuals`. Keep the fitted intercept visible; this template does not force a line through zero. A linear concentration dependence is consistent with this kinetic model, but numerical fit quality alone does not establish a chemical mechanism.

`k2_M_inv_s_inv` is the second-order rate constant estimate because it divides a rate in s^-1 by a concentration in mol/L. Report the conditions, concentrations, per-trace `kobs` and its approximate standard error, slope, slope standard error, intercept and R-squared. A negative slope or patterned residuals needs investigation before reporting a meaningful second-order rate constant.

The per-trace covariance is a local linear approximation. With `sigma=None` and `absolute_sigma=False`, SciPy scales it using residual variance. The second-stage `linregress` is unweighted: its `stderr` assumes residual normality and does not propagate per-trace covariance or concentration uncertainty. Do not label it a complete experimental uncertainty budget.

A `RuntimeError` from minimization, an `OptimizeWarning` promoted to an exception, or a validation failure stops this template. Identify the affected trace and resolve its preparation/model/initialization problem before refitting; do not silently drop it from the concentration series. No successful rate estimate is available from such a failure. Finite covariance alone is not an acceptance criterion.

Consult the official [curve_fit interface](https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.optimize.curve_fit.html) for weighting, bounds or parameter scaling when the unweighted example is unsuitable, and [linregress](https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.linregress.html) for regression result definitions. The method and concentration-series design are described in [An et al., Kinetics and Fig. 2, p. 18114](https://doi.org/10.1039/D4SC04852K).

For phosphine-addition data, the [source method](https://doi.org/10.1039/D1CC06786A) used excess Bu3P and intermediate trapping to suppress competing behavior. Establish the pseudo-first-order and single-decay assumptions for the supplied chemistry before interpreting the concentration-series slope as an addition constant; the numerical regression alone does not establish those assumptions.
