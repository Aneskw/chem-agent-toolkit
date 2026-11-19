---
name: scipy-estimate-linear-regression-inference
description: Fit prepared paired measurements with SciPy linregress and report the fitted line, R-squared, slope test, and confidence intervals for slope and intercept when a linear relationship is independently justified.
---

# Linear regression with coefficient uncertainty

## Setup and inputs

Use SciPy **1.18.1** with Python **3.12 or newer** and NumPy **>=2.0,<2.8**. Follow the [official installation guide](https://scipy.org/install/) in a suitable Python environment; the pinned pip command is:

```sh
python -m pip install "scipy==1.18.1"
```

Provide real, finite, one-dimensional `x` and `y` arrays of equal length, in paired observation order. This workflow requires more than two observations and variation in `x` so coefficient uncertainty can be computed. Keep each variable in consistent units. If observations need exclusion, decide that upstream and remove whole pairs together.

This is an unweighted least-squares fit with a free intercept. Establish the linear relationship and any scientific transformation before using it; the fit does not choose a kinetic model or establish catalyst order.

## Fit and report

Replace the illustrative arrays below with the prepared measurements. The example keeps the full result object because five-value tuple unpacking loses access to `intercept_stderr`.

```python
import numpy as np
from scipy import stats

# Illustrative input, not publication data.
x = np.asarray([0, 1, 2, 3, 4], dtype=float)
y = np.asarray([1.2, 2.9, 5.1, 6.8, 9.2], dtype=float)

if x.ndim != 1 or y.ndim != 1 or x.shape != y.shape:
    raise ValueError("Provide equal-length one-dimensional paired arrays")
if x.size <= 2 or not (np.isfinite(x).all() and np.isfinite(y).all()):
    raise ValueError("Provide more than two finite observation pairs")
if np.ptp(x) == 0:
    raise ValueError("x must vary")

result = stats.linregress(x, y)  # default alternative='two-sided'
y_fit = result.intercept + result.slope * x

# Separate two-sided 95% confidence intervals, N-2 residual degrees of freedom.
q = abs(stats.t.ppf(0.025, x.size - 2))
slope_ci = (result.slope - q * result.stderr,
            result.slope + q * result.stderr)
intercept_ci = (result.intercept - q * result.intercept_stderr,
                result.intercept + q * result.intercept_stderr)

report = {
    "slope": result.slope,
    "intercept": result.intercept,
    "r_squared": result.rvalue**2,
    "slope_pvalue_two_sided": result.pvalue,
    "slope_stderr": result.stderr,
    "intercept_stderr": result.intercept_stderr,
    "slope_ci95": slope_ci,
    "intercept_ci95": intercept_ci,
}
if not np.isfinite([result.slope, result.intercept, result.rvalue,
                    result.pvalue, result.stderr, result.intercept_stderr]).all():
    raise ValueError("Non-finite regression statistics; inspect degenerate inputs")
print(report)
```

The result, `report`, and `y_fit` stay in memory; no file is created automatically. `y_fit` follows the input order and represents fitted responses at the supplied `x` values. The input arrays are not modified by this example.

## Interpret the results

| Output | Meaning |
| --- | --- |
| `slope`, `intercept` | Fitted line `y = intercept + slope*x`; units are y-units/x-units and y-units, respectively. |
| `rvalue**2` | Coefficient of determination; dimensionless. It does not establish that the scientific model is appropriate. |
| `pvalue` | Default two-sided test of zero slope, using a t-distributed Wald statistic. It is not R-squared or the probability that the model is correct. |
| `stderr`, `intercept_stderr` | Standard errors of the coefficients, in their respective coefficient units; SciPy documents the residual-normality assumption. |
| `slope_ci`, `intercept_ci` | Separate coefficient confidence intervals under that inference assumption; these are not prediction intervals for new measurements or a joint confidence region. |

Inspect non-finite results before reporting inference. In the selected release, constant `y` makes correlation and associated inference undefined; constant `x` also makes the slope undefined. The checks above reject these cases through input validation or result inspection.

For interface details, consult the [linregress manual](https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.linregress.html); the chosen patch's [implementation and confidence-interval example](https://github.com/scipy/scipy/blob/v1.18.1/scipy/stats/_stats_py.py#L10772-L10971) specify the interface used here.
