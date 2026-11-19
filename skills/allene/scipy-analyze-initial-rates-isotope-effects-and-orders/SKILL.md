---
name: scipy-analyze-initial-rates-isotope-effects-and-orders
description: Use SciPy to fit calibrated early-time substrate depletion, compare matched H/D initial rates, and estimate apparent orders from controlled concentration series.
---

# Initial rates, isotope effects and apparent reaction orders

## Prepare the environment and data

Use Python >=3.12 with [SciPy 1.18.1](https://pypi.org/project/scipy/1.18.1/) and NumPy >=2.0,<2.8. Obtain a compatible Python from [python.org](https://www.python.org/downloads/) and follow the [official SciPy installation guide](https://scipy.org/install/); in that environment, install the pinned release with `python -m pip install "scipy==1.18.1"`.

Start with calibrated numerical time courses and supplied early-time windows. NMR acquisition, spectral processing and integration are external preparation. Carry these fields with each run:

| Input | Meaning |
|---|---|
| Run ID, replicate ID, H/D label, matched pair ID | Preserve independent runs and explicit pairing. Match temperature, solvent, starting concentrations and other conditions apart from isotope substitution. |
| Time and substrate concentration | Equal-length finite 1-D arrays; use one time unit and one concentration unit throughout. Retain at least three observations with distinct times for a slope error and residual assessment. |
| Window and calibration | Record selected time bounds, calibration and any excluded points. Apply the same mask to time, concentration and uncertainties. |
| Optional concentration SDs | Positive finite array in concentration units, one SD per observation; these are measurement errors, not replicate scatter. |
| Order series | Identity and initial concentration of the varied component, plus the fixed conditions. Use a separate controlled series for each component. |

If input is percent **remaining**, convert with `concentration = initial_concentration * percent_remaining / 100`. For percent **consumed**, use `initial_concentration * (1 - percent_consumed / 100)`. Percentage-point slopes alone cannot compare rates when initial substrate concentrations differ. A fractional remaining trace uses no factor of 100.

## Fit each selected interval

The model is `concentration = intercept + slope * time`; the positive substrate-consumption rate is `-slope`. Do not force the intercept to the nominal starting concentration or replace a rising trace's slope with its absolute value.

This template returns results in memory and leaves input arrays unchanged. Unweighted fitting uses [linregress](https://github.com/scipy/scipy/blob/v1.18.1/scipy/stats/_stats_py.py). The optional weighted branch uses the [version-pinned curve_fit interface](https://github.com/scipy/scipy/blob/v1.18.1/scipy/optimize/_minpack_py.py).

```python
import numpy as np
from scipy.stats import linregress
from scipy.optimize import curve_fit

def fit_rate(time, concentration, sigma=None, *, absolute_sigma=True):
    t = np.asarray(time, dtype=np.float64)
    c = np.asarray(concentration, dtype=np.float64)
    if (t.ndim != 1 or c.shape != t.shape or t.size < 3
            or not np.all(np.isfinite(t)) or not np.all(np.isfinite(c))
            or np.unique(t).size < 3):
        raise ValueError("Need >=3 finite paired observations at distinct times")
    fit = linregress(t, c)
    slope, intercept, slope_se = fit.slope, fit.intercept, fit.stderr
    covariance = None
    if sigma is not None:
        s = np.asarray(sigma, dtype=np.float64)
        if s.shape != c.shape or not np.all(np.isfinite(s)) or np.any(s <= 0):
            raise ValueError("sigma must contain one positive finite SD per point")
        def line(x, m, b):
            return m * x + b
        params, covariance = curve_fit(
            line, t, c, p0=[slope, intercept], sigma=s,
            absolute_sigma=absolute_sigma
        )
        slope, intercept = params
        slope_se = np.sqrt(covariance[0, 0])
    predicted = intercept + slope * t
    return dict(
        rate=-slope, slope=slope, rate_se=slope_se, intercept=intercept,
        ols_r2=fit.rvalue**2, covariance=covariance,
        time=t.copy(), predicted=predicted, residual=c - predicted,
        n=t.size, window=(float(t.min()), float(t.max())),
        weighted=sigma is not None,
        absolute_sigma=absolute_sigma if sigma is not None else None
    )
```

Without `sigma`, `rate_se` is the regression slope standard error, assuming residual normality. With `sigma`, the objective is `sum((residual / SD)**2)`. Choose `absolute_sigma=True` for calibrated absolute SDs; choose `False` explicitly for relative SDs, which rescales parameter covariance by fitted reduced chi-square. The function's default `True` is a template choice; SciPy's default is `False`. The returned covariance orders parameters as slope, intercept. This branch models errors in concentration; it does not account for uncertain times.

## Representative analysis

These arrays are illustrative inputs, not published measurements or execution results. They are already restricted to their chosen early interval, with time in minutes and substrate concentration in mol/L. Replace them with supplied calibrated runs. H1/D1 and H2/D2 are independent matched replicate pairs at the same baseline conditions. H3 and H4 belong to the same controlled catalyst series as H1/H2; only catalyst concentration changes.

```python
time_min = [0, 1, 2, 3]
runs = {
    # id: (isotope, pair ID, catalyst concentration in mol/L, substrate trace)
    "H1": ("H", "p1", 0.001, [0.1000, 0.0988, 0.0975, 0.0964]),
    "D1": ("D", "p1", 0.001, [0.1000, 0.0992, 0.0985, 0.0976]),
    "H2": ("H", "p2", 0.001, [0.1000, 0.0987, 0.0976, 0.0963]),
    "D2": ("D", "p2", 0.001, [0.1000, 0.0991, 0.0984, 0.0975]),
    "H3": ("H", None, 0.002, [0.1000, 0.0982, 0.0966, 0.0948]),
    "H4": ("H", None, 0.004, [0.1000, 0.0975, 0.0952, 0.0927]),
}
rates = {rid: fit_rate(time_min, row[3]) for rid, row in runs.items()}
for rid, result in rates.items():
    print(rid, result["rate"], result["rate_se"], result["ols_r2"])
    # Inspect result["residual"] against result["time"] before using this rate.

pairs = {"p1": ("H1", "D1"), "p2": ("H2", "D2")}
ratios = {}
for pid, (hid, did) in pairs.items():
    h, d = rates[hid]["rate"], rates[did]["rate"]
    if not (np.isfinite(h) and np.isfinite(d) and h > 0 and d > 0):
        raise ValueError(f"{pid}: no valid positive H/D rate ratio")
    ratios[pid] = h / d
values = np.array(list(ratios.values()))
kie_summary = dict(n=values.size, mean=float(values.mean()),
                   sd=float(values.std(ddof=1)))
print("H/D ratios:", ratios, "replicate summary:", kie_summary)

# Example aggregation: equal-weight mean rate at each catalyst level.
# Keep the individual fits and replicate counts alongside these means.
levels = [[0.001, ["H1", "H2"]], [0.002, ["H3"]], [0.004, ["H4"]]]
x = np.array([level for level, ids in levels], dtype=np.float64)
v = np.array([np.mean([rates[rid]["rate"] for rid in ids])
              for level, ids in levels])
if np.any(v <= 0) or not np.all(np.isfinite(v)):
    raise ValueError("Log-order fit requires finite positive rates")
log_x, log_v = np.log(x), np.log(v)
order_fit = linregress(log_x, log_v)
order_result = dict(
    component="catalyst", apparent_order=order_fit.slope,
    order_se=order_fit.stderr, intercept=order_fit.intercept,
    r2=order_fit.rvalue**2,
    residual=log_v - (order_fit.intercept + order_fit.slope * log_x),
    concentrations=x, mean_rates=v, counts=[len(ids) for _, ids in levels]
)
print(order_result)
```

For supplied observation SDs, call `fit_rate(time, concentration, sigma=sigma_c, absolute_sigma=True)` with arrays selected by the same window. Do not silently substitute weighted rates for some runs and unweighted rates for others; record the fitting choice.

The replicate summary is the arithmetic mean and sample SD of **paired ratios**, not a ratio of pooled means. With one pair report its ratio and mark replicate SD unavailable. Fit errors on individual rates and between-replicate SD measure different uncertainties. A near-zero denominator makes a ratio unstable even if it is positive; retain its slope uncertainty.

For each apparent order, regress log(rate) against log(initial concentration) while other conditions stay fixed. The example uses unweighted regression on concentration-level mean rates; report that aggregation and weighting choice. Use consistent units and the same logarithm base for both axes. The slope is the apparent order over the measured range, including its sign. The intercept depends on units and fixed concentrations and is not automatically a transferable rate constant.

## Inspect and deliver results

Inspect the original early trace and residuals for curvature, drift and isolated influential points. High R² alone does not establish an initial linear regime. Keep the supplied window visible; if it is unsuitable, obtain or document a revised selection rather than automatically optimizing R². For weighted fits, also inspect residual/SD. `ols_r2` always refers to the preliminary unweighted fit; it is not weighted goodness of fit.

Return a per-run rate table with units (mol/L/min in the example), slope error, intercept, window, point count, fitting choice and residual arrays or plots; a pair-ID ratio table and replicate mean/SD/count; and each component's apparent order, standard error, log-fit R², residuals, concentration range and aggregation. Rates quantify substrate disappearance; equating that with formation of one product requires the relevant stoichiometry and selectivity.

Nonfinite fits, nonpositive consumption rates and zero/negative log inputs require resolution before ratio/order interpretation. Do not silently discard them. `curve_fit` can raise `ValueError` for invalid inputs and `RuntimeError` for failed minimization; `OptimizeWarning` or nonfinite covariance means parameter uncertainty is unresolved. No fitted number alone establishes a rate-limiting step.
