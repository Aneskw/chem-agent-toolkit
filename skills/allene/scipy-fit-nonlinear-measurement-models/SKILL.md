---
name: scipy-fit-nonlinear-measurement-models
description: Fit a supplied nonlinear model to prepared measurement arrays with SciPy curve_fit when parameter bounds, uncertainty weighting, or covariance diagnostics matter.
---

# Fit nonlinear measurements with uncertainty diagnostics

Use a scientifically justified model supplied for the task. This workflow estimates its parameters by local least squares; it does not select a mechanism or establish that the model is scientifically correct.

## Environment and inputs

Use **SciPy 1.18.1**, Python **3.12 or newer**, and NumPy **>=2.0,<2.8**. Follow the [official installation guide](https://scipy.org/install/) to create and activate a virtual environment, then install the pinned release:

```shell
python -m pip install "scipy==1.18.1"
```

Prepare these inputs before fitting:

| Input | Contract |
| --- | --- |
| `xdata`, `ydata` | For the normal single-predictor path, matching finite float64 arrays of shape `(M,)`. Preserve paired observations and units. |
| `f(x, *parameters)` | Returns float64 predictions of shape `(M,)`, in the same units as `ydata`. The predictor must be its first argument. |
| `p0`, bounds | Initial parameter guesses and lower/upper bounds in the model's parameter order. Choose bounds justified by the task; the default is unbounded. |
| `sigma`, if available | Scalar or `(M,)` standard deviations of errors in `ydata`; a full positive-definite `(M,M)` error covariance is also supported. These are measurement uncertainties, not parameter errors. |

Use more observations than fitted parameters for residual-based covariance estimation. Empty `ydata` is an error, not a meaningful empty fit.

## Representative fit

The following inputs are illustrative, not measured results. Replace the arrays, uncertainties, initial guesses and bounds with those supplied for the task. This example assumes a positive exponential decay with a nonnegative baseline. If `x` is time, `b` has inverse-time units; `a` and `c` have the units of `y`.

```python
import numpy as np
from scipy.optimize import curve_fit

xdata = np.array([0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4], dtype=np.float64)
ydata = np.array([3.02, 1.80, 1.22, 0.83, 0.68, 0.57, 0.56, 0.49, 0.52],
                 dtype=np.float64)
sigma = np.full(ydata.shape, 0.10, dtype=np.float64)  # illustrative absolute SDs

def model(x, a, b, c):
    return a * np.exp(-b * x) + c

popt, pcov = curve_fit(
    model, xdata, ydata,
    p0=[2.5, 1.3, 0.5],
    bounds=([0.0, 0.0, 0.0], [np.inf, np.inf, np.inf]),
    method="trf",
    sigma=sigma,
    absolute_sigma=True,
    check_finite=True,
)

fitted = model(xdata, *popt)
residuals = ydata - fitted
standardized_residuals = None
if sigma is not None and np.ndim(sigma) < 2:
    standardized_residuals = residuals / sigma
parameter_sd = np.sqrt(np.diag(pcov))
covariance_condition = (
    np.linalg.cond(pcov) if np.isfinite(pcov).all() else np.inf
)

print(dict(zip(("a", "b", "c"), popt)))
print("Approximate parameter SDs:", parameter_sd)
print("Covariance condition number:", covariance_condition)
```

`popt` has shape `(N,)` and follows the model's parameter order; `pcov` has shape `(N,N)`. The standardized diagnostic applies only to scalar/vector standard deviations; with covariance input or `sigma=None`, `standardized_residuals` stays `None` and raw `residuals` remain available. Elementwise division by an observation covariance matrix is not valid weighting. Predictions, residuals and diagnostics remain in memory. `curve_fit` creates no output files; retain these arrays along with the input units, model and fitting options when handing results onward.

### Choose weights and solver deliberately

- With absolute measurement standard deviations, use `sigma=...` and `absolute_sigma=True`, as above. For independent errors this minimizes the sum of squared residuals divided by their variances.
- If only relative uncertainty magnitudes are known, use `absolute_sigma=False` (the default). SciPy rescales the covariance using residual variance. With no uncertainty information, omit `sigma`; this gives equal weights. Do not invent absolute uncertainties.
- `method="trf"` supports bounds. The automatic choice is `lm` for unbounded fits and `trf` when bounds are supplied; `lm` cannot handle bounds or fewer observations than parameters.
- If parameter magnitudes differ by orders of magnitude, supply a task-appropriate `x_scale=[...]` with `trf`, in parameter order. The [curve_fit reference](https://github.com/scipy/scipy/blob/v1.18.1/scipy/optimize/_minpack_py.py#L590) gives a scaling example. Scaling changes the optimizer's parameter steps, not the model's units.

## Interpret the fit

Inspect residuals against the predictor to assess systematic model mismatch. A successful optimizer return establishes a local solution, not model validity. Report parameter estimates with their units and the weighting/bounds used.

`parameter_sd` is an approximate one-standard-deviation uncertainty based on a local linear approximation. It is not automatically a confidence interval. Large covariance condition numbers, nonfinite covariance entries, or redundant parameters indicate unreliable uncertainty estimates; review model identifiability before interpreting them. `trf` uses a pseudoinverse for rank-deficient Jacobians, so a returned covariance matrix alone does not establish identifiability. There is no universal condition-number acceptance cutoff in this workflow.

A `RuntimeError` means optimization failed. A `ValueError` can indicate invalid data or incompatible options; retain finite-value checking and correct the input or configuration. An `OptimizeWarning` that covariance could not be estimated means the parameter uncertainty is unresolved even if parameter values were returned. Address the reported cause rather than presenting that output as a reliable fit.
