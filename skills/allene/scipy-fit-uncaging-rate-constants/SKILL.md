---
name: scipy-fit-uncaging-rate-constants
description: Fit single-phase uncaging absorbance traces with SciPy and estimate second-order rate constants from matched substrate-concentration series under pseudo-first-order conditions.
---

# Extract uncaging rate constants from absorbance traces

Fit each trace with `A(t) = Ainf - (Ainf - A0) exp(-kobs*t)`, then fit `kobs = intercept + k2*[substrate]` across a matched concentration series. Use this path when the exponential and pseudo-first-order assumptions are supported by the experiment. It does not decompose biphasic curves or acquire spectra.

## Environment and inputs

Use **Python 3.12 or newer and SciPy 1.18.1**, with NumPy arrays. Follow the [official SciPy setup instructions](https://scipy.org/install/) to prepare a virtual environment, then install the chosen release:

```sh
python -m pip install "scipy==1.18.1"
```

NumPy is a SciPy dependency. No instrument software is needed once traces have been exported.

Prepare these external inputs; the filenames and columns below define this example's interchange format:

| Input | Required content |
| --- | --- |
| `series.csv` | Header `concentration_M,trace_csv`; one row per experiment. Concentration is substrate mol/L; trace paths are relative to this manifest. |
| Each trace CSV | Header `time_s,absorbance`; paired finite numeric values, chronological times in seconds and absorbance in AU. |
| Experimental grouping | Same catalyst concentration and definition, temperature, buffer, chloride level and signal calibration across a series. Analyse distinct conditions or kinetic phases separately. |

Convert exported minutes to seconds and micromolar concentrations to mol/L before loading. Apply any justified blank/reference correction consistently. Use at least four observations per three-parameter trace fit and at least three distinct substrate concentrations for regression with residual degrees of freedom. Sample the rise and approach to a plateau sufficiently to distinguish amplitude from rate; a flat or short trace may not identify a rate.

Keep substrate in the experimentally justified pseudo-first-order regime. The concentration axis here is **substrate**, not catalyst concentration. Supply single-phase traces; do not select a segment of a multiphasic curve solely to make an exponential fit succeed.

## Fit traces and the concentration series

Run this Python example from the directory containing `series.csv`, adapting the input and output paths. It writes to `kinetic-results/`, replacing files with the same names. Inputs are read only. Initial estimates are derived from each trace and are starting guesses, not published parameter values. The example uses unweighted fits and retains a free regression intercept.

```python
import csv
import json
from pathlib import Path
import warnings

import numpy as np
from scipy.optimize import curve_fit, OptimizeWarning
from scipy.stats import linregress

manifest = Path("series.csv").resolve()
out = Path("kinetic-results")
out.mkdir(parents=True, exist_ok=True)


def absorbance_model(t, Ainf, A0, kobs):
    return Ainf - (Ainf - A0) * np.exp(-kobs * t)


with manifest.open(newline="", encoding="utf-8-sig") as stream:
    experiments = list(csv.DictReader(stream))

rows = []
for index, experiment in enumerate(experiments):
    concentration = float(experiment["concentration_M"])
    if not np.isfinite(concentration) or concentration <= 0:
        raise ValueError("Substrate concentration must be positive mol/L")
    trace = manifest.parent / experiment["trace_csv"]
    data = np.genfromtxt(trace, delimiter=",", names=True,
                         dtype=np.float64, encoding="utf-8-sig")
    t = np.atleast_1d(data["time_s"])
    A = np.atleast_1d(data["absorbance"])
    if (len(t) < 4 or not np.all(np.isfinite(t))
            or not np.all(np.isfinite(A)) or np.any(np.diff(t) <= 0)):
        raise ValueError(f"Check observations and chronological times: {trace}")
    t = t - t[0]  # A0 refers to the first retained observation
    if np.ptp(A) == 0:
        raise ValueError(f"Flat trace does not identify a rate: {trace}")
    p0 = [A[-1], A[0], 1.0 / t[-1]]
    with warnings.catch_warnings():
        warnings.simplefilter("error", OptimizeWarning)
        popt, pcov = curve_fit(
            absorbance_model, t, A, p0=p0, method="trf",
            bounds=([-np.inf, -np.inf, 0.0], [np.inf, np.inf, np.inf]),
            check_finite=True,
        )
    errors = np.sqrt(np.diag(pcov))
    condition = np.linalg.cond(pcov)
    if not (np.all(np.isfinite(popt)) and np.all(np.isfinite(errors))
            and np.isfinite(condition)):
        raise ValueError(f"Unresolved parameter covariance: {trace}")
    predicted = absorbance_model(t, *popt)
    np.savetxt(
        out / f"trace-{index:03d}-fit.csv",
        np.column_stack((t, A, predicted, A - predicted)),
        delimiter=",", header="elapsed_s,observed_AU,fitted_AU,residual_AU",
        comments="",
    )
    rows.append([str(trace), concentration, *popt, *errors, condition])

concentrations = np.asarray([row[1] for row in rows], dtype=np.float64)
rates = np.asarray([row[4] for row in rows], dtype=np.float64)
if len(np.unique(concentrations)) < 3:
    raise ValueError("Provide at least three distinct substrate concentrations")
if np.ptp(rates) == 0:
    raise ValueError("Constant fitted rates do not support this concentration fit")

with (out / "kobs.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.writer(stream)
    writer.writerow([
        "trace", "concentration_M", "Ainf_AU", "A0_AU", "kobs_s-1",
        "Ainf_SE_AU", "A0_SE_AU", "kobs_SE_s-1", "covariance_condition",
    ])
    writer.writerows(rows)

regression = linregress(concentrations, rates)
fitted_rates = regression.intercept + regression.slope * concentrations
np.savetxt(
    out / "concentration-fit.csv",
    np.column_stack((concentrations, rates, fitted_rates, rates - fitted_rates)),
    delimiter=",", header="concentration_M,kobs_s-1,fitted_kobs_s-1,residual_s-1",
    comments="",
)
result = {
    "k2_L_mol-1_s-1": float(regression.slope),
    "k2_SE_L_mol-1_s-1": float(regression.stderr),
    "intercept_s-1": float(regression.intercept),
    "intercept_SE_s-1": float(regression.intercept_stderr),
    "R_squared": float(regression.rvalue**2),
}
(out / "k2.json").write_text(
    json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
)
print(result)
```

`trace-NNN-fit.csv` preserves measured and fitted absorbance plus residuals, mapped to manifest row order. `kobs.csv` records parameters in the model's order, approximate standard errors and covariance conditioning. `concentration-fit.csv` exposes the second regression's residuals. `k2.json` contains the slope, intercept, their standard errors and R-squared. Inspect both fitting stages before reporting the slope as a second-order rate constant; the file writing alone does not validate that interpretation. If processing stops, files already written may remain; use a fresh output directory for a revised series to avoid mixing runs.

## Interpret and troubleshoot

- **Trace fit:** `kobs` has units s−1; `A0` and `Ainf` are fitted absorbances, not substrate conversion. Quantitative yield needs a separate absorbance-to-product calibration. Systematic residual curvature or distinct fast/slow phases means the single-exponential model is inadequate. A fitted plateau below the initial absorbance contradicts the intended product-growth interpretation.
- **Identifiability:** An apparently good curve can still have poorly determined rate and plateau parameters. Large covariance condition numbers, large parameter errors, rates at the lower bound, or strong sensitivity to starting guesses call for examining trace duration, baseline and model adequacy. There is no universal condition-number cutoff here. `curve_fit` performs local optimization; compare plausible initial guesses when the result is unstable. For markedly different parameter scales, consult its documented `x_scale` option for `method="trf"`.
- **Uncertainty:** With no `sigma`, `curve_fit` uses equal observation weights and its default `absolute_sigma=False` scales covariance by residual variance. The reported errors are local linear approximations. If independently measured absorbance standard deviations are available, pass the aligned positive vector as `sigma` and use `absolute_sigma=True`; do not invent errors. `linregress` is also unweighted, and its standard errors assume normally distributed residuals. It does not propagate individual `kobs` errors. If their differences require weighting, use a separately justified weighted analysis rather than treating this example as weighted inference.
- **Concentration fit:** A positive linear slope is interpretable as `k2` only for the intended pseudo-first-order series. Retain the intercept as a diagnostic; a nonzero intercept can reflect additional processes or offsets and is not automatically evidence for a mechanism. R-squared alone does not establish linear kinetics. A negative slope or curved residual trend does not support the intended simple rate law.
- **Failure signals:** `RuntimeError` indicates failed optimization; `ValueError` can indicate invalid inputs or options. This example turns `OptimizeWarning` about covariance into an exception and rejects nonfinite results. Missing columns/files and malformed numbers are input errors. A constant signal or an insufficient concentration series produces no reportable `k2`, rather than a zero rate conclusion.

For model options and covariance semantics, consult the official [curve_fit reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html) and [linregress reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html). The exponential model and substrate-series analysis are documented in [the study's supplementary information](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10952092/supplementaryFiles), §3.1 equation 1 and Figures S6–S7; the download is an archive containing the original SI PDF.
