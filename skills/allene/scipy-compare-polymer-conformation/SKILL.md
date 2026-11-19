---
name: scipy-compare-polymer-conformation
description: Compare linear and cyclic polymer conformation at matched molecular weight from prepared SEC-MALS/viscometry exports, using SciPy log-log regression and property ratios.
---

# Compare polymer conformation at matched molecular weight

Use absolute molecular weight to align linear and cyclic polymer measurements before comparing radius of gyration, intrinsic viscosity or hydrodynamic volume. This workflow summarizes approximately linear regions in log-log coordinates with SciPy; calibration and reduction of instrument signals must already be complete.

## Environment and prepared inputs

Use **SciPy 1.18.1**, NumPy >=2.0 and Python 3.12-3.14. Follow the [official SciPy setup instructions](https://scipy.org/install/); in an appropriate Python environment, the pinned installation command is:

```sh
python -m pip install scipy==1.18.1
```

Prepare two CSV files, `linear.csv` and `cyclic.csv`, in the working directory. Each has a single header row and two numeric columns, `mw_g_mol,property`. These are this example's interchange columns; map your instrument export to them. Each row pairs a slice's absolute molecular weight with its measured property. Samples may have different row counts and molecular-weight grids.

| Field/choice | Required meaning |
| --- | --- |
| `mw_g_mol` | Absolute molecular weight in g/mol; do not substitute a sample-average molecular weight for each slice. |
| `property`, `kind="rg"` | Rg in nm for both samples; the output ratio is **Rg_cyclic squared / Rg_linear squared**. |
| `property`, `kind="eta"` | Intrinsic viscosity, in the same units for both samples; output is eta_cyclic / eta_linear. |
| `property`, `kind="hydrodynamic_volume"` | Already reduced hydrodynamic volume, with the same definition and units for both samples; output is volume_cyclic / volume_linear. A radius column is a different quantity. |

Use comparable polymer chemistry and measurement conditions. Supply only a scientifically justified, approximately linear log-log region for each sample, retaining the original exports separately. Record the selected ranges, units and exclusions with the result. All included values must be finite and positive. Each fit needs at least three paired rows and variation in molecular weight; this is a computational prerequisite, not a sufficient sample-size criterion.

The fit is unweighted least squares in log10 coordinates: `log10(property) = intercept + slope * log10(MW)`. It gives equal weight to included log-space observations. Use this path only when that representation is suitable for the data; it is not a universal model for an entire chromatogram.

## Fit and inspect the two samples

Run this in a Python session from the directory containing the prepared files. Set `kind` to the property being compared. The code preserves inputs and writes diagnostics under `conformation-output`; existing files with these names are overwritten, so choose a fresh output directory for another comparison.

```python
from pathlib import Path
import csv
import numpy as np
from scipy.stats import linregress

kind = "rg"  # or "eta", "hydrodynamic_volume"
power = {"rg": 2, "eta": 1, "hydrodynamic_volume": 1}[kind]
out = Path("conformation-output")
out.mkdir(exist_ok=True)
fits = {}
summary = []

for sample in ("linear", "cyclic"):
    # Two-column, header-bearing CSV supplied by the analyst.
    data = np.loadtxt(f"{sample}.csv", delimiter=",", skiprows=1,
                      usecols=(0, 1), ndmin=2)
    if data.shape[0] < 3:
        raise ValueError(f"{sample}: need at least three paired rows")
    if not np.isfinite(data).all() or (data <= 0).any():
        raise ValueError(f"{sample}: values must be finite and positive")
    mw, prop = data.T
    x, y = np.log10(mw), np.log10(prop)
    if x.min() == x.max():
        raise ValueError(f"{sample}: molecular weight must vary")
    result = linregress(x, y)
    fitted_log = result.intercept + result.slope * x
    residual = y - fitted_log
    if not np.isfinite([result.slope, result.intercept,
                        result.stderr, result.intercept_stderr]).all():
        raise ValueError(f"{sample}: nonfinite regression result")
    fits[sample] = (result, mw.min(), mw.max())
    summary.append([sample, kind, len(x), mw.min(), mw.max(),
                    result.slope, result.intercept, result.rvalue**2,
                    result.stderr, result.intercept_stderr])
    np.savetxt(out / f"{sample}-residuals.csv",
               np.column_stack((mw, x, y, fitted_log, residual)),
               delimiter=",", comments="",
               header="mw_g_mol,log10_mw,observed_log10_property,"
                      "fitted_log10_property,residual_log10_property")

with (out / "fits.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["sample", "kind", "n", "mw_min", "mw_max", "slope",
                     "intercept", "r_squared", "slope_stderr",
                     "intercept_stderr"])
    writer.writerows(summary)
print(out / "fits.csv")
```

Inspect `linear-residuals.csv` and `cyclic-residuals.csv`, especially residuals versus `log10_mw`. Systematic curvature makes a single power-law comparison misleading even with high R-squared. If the selected region is unsuitable, reconsider it based on the measurement context or stop this fitting path; do not select points simply to obtain a desired ratio. `fits.csv` retains coefficients, fit ranges and diagnostics. See the official [linregress interface](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html) for result definitions.

## Compare within the shared molecular-weight range

After inspecting the diagnostics, continue in the same Python session. This evaluates the two fitted relations on an illustrative 50-point reporting grid within their overlap. The rows are fitted estimates, not 50 new measurements.

```python
linear, lmin, lmax = fits["linear"]
cyclic, cmin, cmax = fits["cyclic"]
lo, hi = max(lmin, cmin), min(lmax, cmax)
if hi <= lo:
    raise ValueError("No molecular-weight interval shared by both fits")

log_mw = np.linspace(np.log10(lo), np.log10(hi), 50)
mw_common = 10.0**log_mw
log_linear = linear.intercept + linear.slope * log_mw
log_cyclic = cyclic.intercept + cyclic.slope * log_mw
linear_property = 10.0**log_linear
cyclic_property = 10.0**log_cyclic
ratio = 10.0**(power * (log_cyclic - log_linear))
values = np.column_stack((mw_common, linear_property, cyclic_property, ratio))
if not np.isfinite(values).all() or (values <= 0).any():
    raise ValueError("Invalid back-transformed values; inspect inputs and fits")
np.savetxt(out / "matched-ratios.csv", values, delimiter=",", comments="",
           header=f"mw_g_mol,linear_{kind},cyclic_{kind},"
                  f"cyclic_over_linear_power_{power}")
print(out / "matched-ratios.csv")
```

No overlap means these data cannot support a matched-weight interval comparison. Obtain suitable measurements rather than extrapolating either relation. Malformed CSVs, insufficient rows, constant molecular weight and nonfinite results require correcting the preparation or reconsidering the fit, rather than interpreting the output as a topology result.

## Read the results

- `matched-ratios.csv` contains common molecular weight, fitted properties in the input property units and a dimensionless ratio. A ratio below one means the cyclic sample has a smaller compared quantity at that molecular weight. For `rg`, the properties remain Rg while the ratio uses their squares. It is not the unsquared radius ratio or an average across the molecular-weight distribution.
- The log-log slope describes property scaling with molecular weight within the selected range. The intercept depends on the chosen units. R-squared describes the fit; it does not establish cyclic topology. Standard errors from `linregress` assume residual normality, and adjacent chromatographic slices may not be independent observations. The table supplies no propagated uncertainty or confidence interval for the ratios.
- Preserve both samples' ranges and diagnostics alongside ratio curves. A ratio varying across the overlap should remain a curve or reported range, rather than silently becoming one universal value. New values calculated here are regression estimates derived from measurements.

The [poly(allenamer) conformation study](https://doi.org/10.1002/anie.202425648), pp. 5-7 and Figure 6, illustrates comparison of squared Rg, intrinsic viscosity and hydrodynamic volume at given absolute molecular weight. Use such measurements as evidence consistent with compact cyclic conformation together with other structural evidence. There is no universal ratio cutoff in this workflow, and a ratio alone does not quantify cyclic purity.
