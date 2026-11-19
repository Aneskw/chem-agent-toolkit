---
name: larch-fit-exafs-scattering-paths
description: Fit prepared EXAFS k/chi spectra to supplied FEFF scattering paths with Larch, apply shared parameter constraints, and inspect structural parameters, uncertainties and fit diagnostics.
---

# Fit EXAFS spectra with Larch scattering paths

## Prepare the environment and inputs

Use **xraylarch 2026.3.1**, imported as `larch`, with Python 3.11 or newer. Obtain it through the [official installation guide](https://xraypy.github.io/xraylarch/installation.html) and [pinned release](https://github.com/xraypy/xraylarch/releases/tag/2026.3.1). For an existing compatible Python environment, install `python -m pip install "xraylarch==2026.3.1"`. Run the example with that environment's Python. Its Matplotlib plots do not require the Larch GUI extras.

This workflow starts after measurement, normalization and background subtraction. Obtain the following from the data/model provider:

| Input | Contract |
|---|---|
| Prepared spectrum | ASCII columns `k chi`: equal-length finite 1-D arrays, increasing k in inverse angstroms; chi is dimensionless and **not k-weighted**. Adapt labels if the file has extra columns. Diagnostic Fourier spectra below use data interpolated onto the fitting grid; original input arrays are retained separately. |
| Scattering paths | Actual FEFF `feffNNNN.dat` output files for the absorber, edge and structural model; a coordinate file alone is insufficient. Confirm each path's geometry, nominal distance `reff` and degeneracy `degen`. |
| Fit specification | Usable k interval, R interval in angstroms, k-weight, window/taper, starting values, bounds and shared/fixed parameters justified for this sample. |
| Amplitude calibration | Supplied S0 squared calibration and the intended degeneracy/occupancy convention. Do not infer coordination numbers from an uncalibrated amplitude. |
| Optional noise estimate | `epsilon_k`: positive scalar or array matching chi, in chi units. Otherwise Larch estimates noise automatically. |

Use the [path interface](https://xraypy.github.io/xraylarch/xafs_feffpaths.html#feffpath) to check path definitions. File degeneracy is retained unless explicitly overridden; `s02` defaults to 1, while `e0`, `deltar` and `sigma2` default to zero. `e0` is an energy shift in eV, `deltar` is a distance shift in angstroms, and `sigma2` is mean-square relative displacement in square angstroms.

## Define and run the fit

The example assumes supplied Pd-P and Pd-Cl single-scattering paths. Replace the filenames, calibration and fit specification with the supplied model. All numbers below are illustrative choices, not published fit settings. Sharing one energy shift is also a model choice; use separate parameters when justified. Retain the supplied path set when adapting the template.

Save this as `fit_exafs.py` in a working directory containing `prepared.chi` and the `paths/` directory; run `python fit_exafs.py`. Outputs below overwrite files with the same names in that directory.

```python
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from larch.io import read_ascii
from larch.fitting import param_group, param
from larch.xafs import (
    feffpath, feffit_transform, feffit_dataset, feffit, feffit_report,
)

data = read_ascii('prepared.chi', labels='k chi')
if (data.k.ndim != 1 or data.k.shape != data.chi.shape
        or data.k.size < 2 or not np.all(np.isfinite(data.k))
        or not np.all(np.isfinite(data.chi))
        or not np.all(np.diff(data.k) > 0)):
    raise ValueError('Expected finite, equal-length k/chi arrays, increasing k')

# Replace with supplied calibration and approved starting values/bounds.
pars = param_group(
    s02=param(0.90, vary=False),
    de0=param(0.0, vary=True),
    dr_p=param(0.0, vary=True),
    dr_cl=param(0.0, vary=True),
    sig2_p=param(0.003, min=0, vary=True),
    sig2_cl=param(0.003, min=0, vary=True),
)
paths = [
    feffpath('paths/pd_p/feff0001.dat', label='Pd-P',
             s02='s02', e0='de0', deltar='dr_p', sigma2='sig2_p'),
    feffpath('paths/pd_cl/feff0001.dat', label='Pd-Cl',
             s02='s02', e0='de0', deltar='dr_cl', sigma2='sig2_cl'),
]
for p in paths:
    print(p.label, p.geom, p.reff, p.degen)

# Example ranges: replace with this spectrum's usable intervals.
trans = feffit_transform(kmin=3, kmax=12, kweight=2,
                         dk=2, window='kaiser',
                         rmin=1.2, rmax=3.0, fitspace='r')
if data.k.min() > trans.kmin or data.k.max() < trans.kmax:
    raise ValueError('Prepared k coverage does not cover the requested fit range')
# If available, assign data.epsilon_k before constructing the dataset.
dset = feffit_dataset(data=data, pathlist=paths, transform=trans)
result = feffit(pars, dset)
report = feffit_report(result)
Path('fit-report.txt').write_text(report, encoding='utf-8')
print(report)
print('Fit status:', result.success, result.message)

# Read fitted values from the returned result, not the starting group.
for name in ('de0', 'dr_p', 'dr_cl', 'sig2_p', 'sig2_cl'):
    p = result.params[name]
    print(name, p.value, p.stderr, p.correl)
fitset = result.datasets[0]
for path, shift in zip(fitset.pathlist, ('dr_p', 'dr_cl')):
    print(path.label, 'fitted distance (A):',
          path.reff + result.params[shift].value)
```

Continue the same script to save spectra and inspect data/model agreement. In 2026.3.1, fitting interpolates chi onto the zero-origin model grid with spacing `fitset.transform.kstep`, but the returned `fitset.data.chir` transforms the original samples directly. For inputs with a different origin or spacing, rebuild the diagnostic data transform on the fitting grid as below. This uses the pinned transform's `fftf` method with its existing window and k-weight, matching the fit interpolation. Keep the original arrays separately; interpolation does not extend the usable measured range.

```python
d, m = fitset.data, fitset.model
# fftf expects samples on its own zero-origin grid; model.k is that grid.
chi_on_fit_grid = np.interp(m.k, d.k, d.chi)
r = m.r
chir_on_fit_grid = fitset.transform.fftf(chi_on_fit_grid)[:r.size]
np.savez('fit-spectra.npz',
         input_k=data.k, input_chi=data.chi,
         fit_k=m.k, data_chi_on_fit_grid=chi_on_fit_grid, model_chi=m.chi,
         r=r, data_chir_on_fit_grid=chir_on_fit_grid, model_chir=m.chir)
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
axes[0].plot(d.k, d.k**2 * d.chi, label='data')
axes[0].plot(m.k, m.k**2 * m.chi, label='model')
axes[0].set(xlim=(trans.kmin, trans.kmax),
            xlabel='k (1/A)', ylabel='k^2 chi(k)')
for chir, label in ((chir_on_fit_grid, 'data'), (m.chir, 'model')):
    axes[1].plot(r, np.abs(chir), label=label + ' magnitude')
    axes[1].plot(r, chir.real, '--', label=label + ' real')
axes[1].set(xlim=(0, 5), xlabel='R (A)', ylabel='chi(R)')
for ax in axes:
    ax.legend()
fig.tight_layout()
fig.savefig('fit-comparison.png', dpi=160)
plt.close(fig)
```

`param()` is fixed by default: specify `vary=True` for each variable. Shared string expressions refer to names in `pars`. Unique path labels matter: the dataset stores paths by label, so duplicate labels can discard paths. The dataset copies the input path objects and k/chi arrays; fitted spectra and path outputs belong to `result.datasets`. Recreate the transform and dataset when changing ranges or weights, since transform windows are cached.

## Inspect and interpret results

Use `fit-report.txt` for fitted values, uncertainties, correlations, path summaries and goodness of fit; `fit-spectra.npz` separates original `input_k/input_chi` from interpolated `data_chi_on_fit_grid` and fitted `model_chi` on `fit_k`; both Fourier spectra use `r`. `fit-comparison.png` compares the original k-space data with the model and the grid-corrected Fourier spectra. See the [fitting manual](https://xraypy.github.io/xraylarch/xafs_feffit.html) for conditional options such as simultaneous datasets or multiple k-weights.

- Check `result.success` and `result.message`. Exceptions, an absent result or failed convergence are failure signals. `result.errorbars=False` or missing standard errors means uncertainty estimation failed; it does not mean zero uncertainty. Check bounds and strong correlations before using parameter estimates.
- Compare data/model oscillations and both magnitude and real part in R space. A small `result.rfactor` describes relative misfit, not a unique or proven structural model. Uncertainties depend on the supplied/estimated noise and model assumptions.
- Compare `result.nvarys` with `result.n_independent`. The approximate information limit is `2 * (kmax-kmin) * (rmax-rmin) / pi + 1`; reduce free parameters through physically justified constraints if the model approaches/exceeds that information. Dense sampling or several k-weights do not provide independent new measurements.
- For these single-scattering paths, distance is `reff + deltar`; `sigma2` is in square angstroms. For multiple scattering this is an effective path distance, not automatically one bond length.
- The example fixes S0 squared and retains file degeneracies, so it does not estimate coordination numbers. To fit shell coordination with a calibrated S0 squared, the manual's two-shell example uses `degen=1` and `s02='s02*n1'` (and a variable `n1` in the parameter group) so coordination appears once in the amplitude. Apply that convention only with the appropriate supplied shell model; do not also multiply by the original degeneracy or fit an unconstrained S0 squared and coordination together.

Retain the input data, path files, calibration, parameter expressions and transform settings with the report so the model can be inspected and rerun.
