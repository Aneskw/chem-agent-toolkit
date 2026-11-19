---
name: scipy-fit-rate-concentration-or-loading
description: Fit prepared concentration-rate measurements with SciPy and inspect coefficients, uncertainty, and residuals when assessing consistency with first-order dependence.
---

# Fit concentration-dependent reaction rates

Fit one controlled concentration series at a time using ordinary linear least squares, with measured rate as the response. Rate extraction and experimental design must already be complete. Keep other conditions fixed within a series; analyze different varied components separately.

## Environment and inputs

Use Python >=3.12 and SciPy **1.18.1**, with NumPy installed as its dependency. Follow the [official setup instructions](https://scipy.org/install/) and install the pinned release in the intended environment:

```sh
python -m pip install scipy==1.18.1
```

Supply a UTF-8 CSV named `rate-series.csv` in the working directory with these headers and one measurement per subsequent row:

| Column | Meaning in this example |
| --- | --- |
| `concentration_mol_L` | Concentration of the single varied component, mol/L |
| `rate_mol_L_s` | Prepared measured rate, mol/(L s) |

These column names and units are an example contract. Adapt both labels and interpretation if the supplied data use different units or catalyst loading instead of concentration; this workflow performs no unit or loading conversion. Use at least three paired finite measurements at nonconstant concentrations so the fit has residual degrees of freedom. Resolve missing measurements explicitly before fitting.

## Fit and export

Run this Python example with the prepared CSV present. It prints the fit summary and writes `rate-fit.csv` beside the input, replacing that output file if it exists. The input file is read only.

```python
import csv
import numpy as np
from scipy import stats

with open('rate-series.csv', encoding='utf-8-sig', newline='') as handle:
    records = list(csv.DictReader(handle))
x = np.array([float(r['concentration_mol_L']) for r in records])
y = np.array([float(r['rate_mol_L_s']) for r in records])

if x.size < 3 or not (np.isfinite(x).all() and np.isfinite(y).all()):
    raise ValueError('Need at least three finite concentration-rate pairs')
if np.max(x) == np.min(x):
    raise ValueError('Concentrations must vary')

res = stats.linregress(x, y, nan_policy='raise')
fitted = res.intercept + res.slope * x
residual = y - fitted
summary = {
    'slope_s_inverse': float(res.slope),
    'intercept_mol_L_s': float(res.intercept),
    'slope_stderr_s_inverse': float(res.stderr),
    'intercept_stderr_mol_L_s': float(res.intercept_stderr),
    'r_squared': float(res.rvalue ** 2),
    'pvalue_slope_zero': float(res.pvalue),
}
print(summary)

with open('rate-fit.csv', 'w', encoding='utf-8', newline='') as handle:
    writer = csv.writer(handle)
    writer.writerow(['concentration_mol_L', 'rate_mol_L_s',
                     'fitted_rate_mol_L_s', 'residual_mol_L_s'])
    writer.writerows(zip(x, y, fitted, residual))
```

## Read the result

| Result | Meaning |
| --- | --- |
| `slope`, `stderr` | Rate change per concentration change and its standard error; both have units s^-1 for the example |
| `intercept`, `intercept_stderr` | Fitted rate at zero concentration and its standard error, in mol/(L s) |
| `rvalue**2` | Coefficient of determination for this fitted line |
| `pvalue` | Two-sided test of zero slope; the default alternative is `two-sided` |
| Exported residual | Measured rate minus fitted rate, in mol/(L s), in original row order |

Keep the result object rather than unpacking five values: the legacy five-value form omits `intercept_stderr`. Standard errors assume residual normality. This interface provides no measurement-error weights.

Inspect residuals against concentration for curvature or systematic structure. A linear trend with an intercept compatible with zero can support proportional rate dependence over the measured range. A substantial offset means the fitted relationship is affine rather than directly proportional. The slope is dimensional and is **not the reaction order**. A high R-squared or small zero-slope p-value alone does not establish first-order kinetics or a mechanism; interpret the fit with the controlled conditions and measurement uncertainty.

Missing headers or nonnumeric cells stop input loading; repair the input contract rather than silently discarding rows. The example rejects empty, undersized, nonfinite and constant-concentration inputs before regression. `nan_policy='raise'` also rejects NaNs at the SciPy call. If coefficients or uncertainty diagnostics are nonfinite, report them as undefined and inspect the measurements instead of treating them as a usable fit.

See the official [linregress interface](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html) for parameter and return-value details.

For catalyst or acid loading series, replace the concentration column and output labels with the supplied loading unit, such as mg or mol%, and report the slope as rate-unit per loading-unit. A mass or mol%-based slope is not s^-1. Fit each varied component separately while keeping the other experimental conditions fixed.
