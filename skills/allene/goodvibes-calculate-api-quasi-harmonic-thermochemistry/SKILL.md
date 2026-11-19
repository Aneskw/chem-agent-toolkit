---
name: goodvibes-calculate-api-quasi-harmonic-thermochemistry
description: Use the pinned GoodVibes Python API to calculate and report quasi-harmonic thermochemistry from completed quantum-chemistry frequency outputs with GoodVibes, including optional single-point energy corrections and Supporting Information tables.
---

# Quasi-harmonic thermochemistry with GoodVibes

## Setup and inputs

Use [GoodVibes](https://github.com/patonlab/GoodVibes) with Python >=3.10. This workflow targets commit `a3e5c6f1353735db8ff142584372b78e97bb3f3e`; install that source revision in the execution environment:

```sh
python -m pip install "goodvibes @ https://github.com/patonlab/GoodVibes/archive/a3e5c6f1353735db8ff142584372b78e97bb3f3e.zip"
```

Prepare completed frequency outputs containing electronic energy, frequencies, and molecular/rotational data. Supported native formats include Gaussian `.log`/`.out`, ORCA `.out`, NWChem `.out`, QChem `.out`/`.qcin`, and xTB frequency `.out` files. Geometry optimization, conformer searches, transition-state connectivity checks, and electronic-structure solvent models are upstream work.

For a composite calculation, place each corresponding single-point output alongside its frequency output. With `spc="TZ"`, `inputs/structure.log` pairs with `inputs/structure_TZ.log` or `.out`. The suffix is exact: `def2_TZVP` requires `spc="def2_TZVP"`. Supply only frequency files to the main input list; SPC partners are located separately. Verify that each pair represents the intended same structure and electronic state.

## Choose the correction settings

Use the requested scientific protocol. The example below chooses Truhlar entropy correction, 100 cm⁻¹ cutoff, 298.15 K, and 1 mol/L as illustrative settings.

| Option | Meaning and relevant default |
| --- | --- |
| `QS` | `"truhlar"` or `"grimme"` entropy treatment; default `"grimme"`. |
| `QH` | Head-Gordon enthalpy correction, independent of `QS`; default `False`. When enabled, `h_freq_cutoff` controls it (default 100 cm⁻¹). |
| `s_freq_cutoff` | Entropy cutoff in cm⁻¹; default 100. |
| `temperature` | Temperature in K; default 298.15. |
| `concentration` | mol/L; `None` uses the 1 atm reference via P/RT, not 1 mol/L. |
| `freq_scale_factor`, `zpe_scale_factor` | `None` looks up separate harmonic and ZPE factors from the frequency calculation's level of theory. An explicit frequency factor with ZPE left `None` also sets the ZPE factor. Set both to `1.0` for deliberately unscaled results. |
| `spc`, `strict_spc` | `"TZ"` pairs files; `"link"` uses a linked single-point job; `None` requests no SPC. Strict mode raises for unusable requested SPC instead of falling back to the frequency-level energy. |

Concentration changes the translational standard state. It does not supply a solvent electronic energy. The optional `solv` parameter is a free-space correction, separate from a continuum-solvent calculation.

## Calculate and export

Run from a project directory containing the prepared `inputs/` files. Save this adaptable example as `thermochemistry.py`, replace the input paths and options, then run `python thermochemistry.py`:

```python
from pathlib import Path
from goodvibes import compute_batch, write_si

# External inputs: frequency outputs only. Each needs a _TZ SPC partner.
paths = ["inputs/structure.log"]  # Add other frequency outputs here.
options = dict(
    QS="truhlar",
    QH=False,
    s_freq_cutoff=100.0,
    temperature=298.15,
    concentration=1.0,
    freq_scale_factor=None,
    zpe_scale_factor=None,
    spc="TZ",
    strict_spc=True,
    invert=None,
    symm=False,
)
results = compute_batch(paths, jobs=1, **options)
for r in results:
    if not r.has_thermo or r.qh_gibbs_free_energy is None:
        raise ValueError(f"No usable thermochemistry for {r.file}")
    print(r.name, "qh-G / hartree:", r.qh_gibbs_free_energy)
    print("SPC applied:", r.spc_applied, "imaginary modes / cm^-1:",
          r.im_frequency_wn, "n_imag:", r.n_imag)
    print("scaling:", r.freq_scale_factor, r.zpe_scale_factor,
          r.scale_factor_source)
    print("symmetry:", r.point_group, r.symmno, r.symmetry_source)

out = Path("results")
out.mkdir(exist_ok=True)
written = write_si(results, out / "thermochemistry.md", units="hartree")
print("Written:", written)
```

For frequency-level energies only, set `spc=None`. For a single structure, `compute_thermo(paths[0], **options)` returns one `ThermoResult`; `compute_batch` returns a list in input order and applies the same options to each entry. An empty input list returns `[]`, not a successful calculation. Use separate calls when structures require different correction settings.

`write_si` creates or overwrites its destination and returns the paths written; it leaves QC inputs unchanged. Markdown contains a table and an available-coordinates appendix. Change the extension to `.tex` for LaTeX, or `.csv`/`.tsv` for a full-column table plus a `<stem>_coordinates.xyz` sidecar when coordinates exist. `.xyz` exports coordinates alone. `units="kcal/mol"` or `"kJ/mol"` converts reported energies; the API results remain in atomic units.

## Interpret and inspect

- **Energies:** `scf_energy` is the frequency-level electronic energy; `sp_energy` is the optional higher-level energy. When `spc_applied=True`, its difference from the original electronic energy has already been incorporated into enthalpies and free energies. Do not add it again.
- **Thermal quantities:** energies are Hartree, entropies Hartree/K, and frequencies cm⁻¹. With `QH=False`, `qh_gibbs_free_energy` uses harmonic enthalpy and corrected entropy; with `QH=True`, it uses corrected enthalpy as well. `qh_enthalpy` is `None` when disabled. SI columns `TS` and `qh_TS` report T times entropy, not entropy itself; table energies are absolute.
- **Missing data:** unavailable result fields are `None`. SP-only outputs cannot substitute for frequency calculations. `MissingSinglePointError` in strict mode means the requested correction was not available; repair the partner or explicitly choose a calculation without SPC. Non-strict mode can warn and retain the frequency-level energy. A linked job whose parsed SPC equals the frequency-level energy is treated as unapplied.
- **Scaling and symmetry:** review the reported factors and their sources. A missing QM scaling lookup uses 1.0 with `ScaleFactorWarning`; resolve the level-of-theory identification or deliberately specify factors. `symm=False` avoids extra pymsym detection but does not erase symmetry information parsed from the output; an assumed symmetry source signals an assumption rather than a detected point group.
- **Stationary points:** inspect imaginary modes against the supplied minimum/TS assignment. `invert=None` avoids requesting conversion of imaginary modes into real modes. Corrected energies and a mode count do not establish reaction connectivity or validate a mechanism.

For interface details beyond these settings, consult the [API guide at the pinned revision](https://github.com/patonlab/GoodVibes/blob/a3e5c6f1353735db8ff142584372b78e97bb3f3e/docs/source/api_guide.md).
