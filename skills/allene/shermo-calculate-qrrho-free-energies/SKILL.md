---
name: shermo-calculate-qrrho-free-energies
description: Calculate Grimme QRRHO thermal corrections and Gibbs energies with Shermo from completed Gaussian 09/16 frequency outputs, optionally using a higher-level single-point energy.
---

# Grimme QRRHO thermochemistry with Shermo

## Prepare the executable and inputs

Use **Shermo 2.6.2** for Windows or Linux. Download and extract the official [executable archive](https://sobereva.com/soft/shermo/Shermo_2.6.2.zip) from the [author homepage](https://sobereva.com/soft/shermo/). It includes `Shermo.exe` (Windows), `Shermo` (Linux), settings and examples; no Python environment or compilation is required. The [2.6.2 manual](https://sobereva.com/soft/shermo/Shermo_manual_2.6.2.pdf), sections 2–3, documents the interface.

Supply a completed, validated Gaussian 09/16 `freq` or `opt freq` output, here named `freq.out`. Shermo reads the final geometry when optimization is included, atomic masses, spin multiplicity, electronic energy and harmonic frequencies. Coordinates alone or a single-point output are insufficient. Anharmonic frequencies are ignored. Geometry optimization, frequency calculation and stationary-point validation are upstream tasks; electrochemical reference-potential conversion is a downstream task.

An optional higher-level electronic energy must be supplied in hartree (atomic units), for the same species and geometry with a consistent electronic/solvation convention. Shermo does not perform the single-point calculation.

## Calculate and inspect

Work in a calculation directory containing the supplied `freq.out`. The commands below assume the platform executable has also been placed there; otherwise substitute its full path. Choose an unused output filename: `>` creates or overwrites the report.

Windows PowerShell:

```powershell
.\Shermo.exe .\freq.out -noset -T 298.15 -P 1 -ilowfreq 2 -intpvib 100 -imagreal 0 > .\thermo.txt
Get-Content .\thermo.txt
```

Linux shell, with an executable `Shermo` binary:

```bash
./Shermo ./freq.out -noset -T 298.15 -P 1 -ilowfreq 2 -intpvib 100 -imagreal 0 > ./thermo.txt
```

These are representative choices; change them to the requested conditions and record the effective settings.

| Argument or setting | Meaning for this calculation |
| --- | --- |
| `-noset` | Ignore `settings.ini`; unspecified options use built-in defaults. Without it, Shermo searches the current directory, then `Shermopath`; command arguments override loaded settings. |
| `-T 298.15`, `-P 1` | Temperature in K and pressure in atm. |
| `-ilowfreq 2` | Grimme interpolation between harmonic and free-rotor entropy. It changes entropy only. Mode 3 also interpolates internal energy and is a different model. |
| `-intpvib 100` | Interpolation threshold in cm^-1; this does not raise all low frequencies to 100. |
| `-imagreal 0` | Do not convert imaginary modes to real ones. Imaginary modes are omitted from thermodynamic sums. |
| Unspecified defaults | `sclZPE`, `sclheat`, `sclS`, `sclCV` are 1.0; `defmass=3` reads masses from the output; `imode=0` includes translation and rotation; `conc=0` adds no concentration correction. |

If justified scale factors are supplied for the frequency method, pass them explicitly, for example `-sclZPE` for ZPE and `-sclS` for entropy. Do not transfer a factor between these contributions automatically.

To use a supplied higher-level energy, add `-E` followed by its numeric hartree value to the same command before redirection. This replaces the electronic energy used in the totals, not the frequency-derived correction. The default `E=0` is a sentinel meaning use the energy read from the input.

Before accepting results, inspect the printed running parameters and Molecular information: energy, multiplicity, masses, point group/rotational symmetry number, and frequency list. Check these against the supplied calculation and its stationary-point validation. Unexpected imaginary modes require upstream review; converting them to real modes is a separate approximation, unsuitable for a genuine transition-state mode. A missing/empty report, missing Total block or inconsistent molecular information is not a usable result. This workflow uses isolated-molecule ideal-gas thermochemistry; solids and adsorbates require a different treatment of translation and rotation.

## Read Gibbs energies and compare species

In the **Total** block of `thermo.txt`, distinguish:

| Printed label | Interpretation |
| --- | --- |
| `Thermal correction to G` | G correction including ZPE and finite-temperature enthalpy and entropy terms, reported in kJ/mol, kcal/mol and hartree. It excludes electronic energy. |
| `Electronic energy` | Check whether the input energy or supplied `-E` value was used. |
| `Sum of electronic energy and thermal correction to G` | Total G in hartree at the specified conditions: electronic energy plus the correction. |

To combine energies manually, add the correction in **hartree** to the higher-level electronic energy in hartree. Do not add electronic energy again to the printed sum. Printed partition functions remain the RRHO values even with `ilowfreq=2`; they do not encode the interpolated entropy.

For reaction energies, use stoichiometric sums of total G: products minus reactants. Use consistent energy conventions, temperature, pressure, scaling and low-frequency treatment across species, and retain units. Record per species the input identity, electronic energy source, effective settings, G correction and total G alongside the report.

For a solution concentration standard state, explicitly decide whether a correction is needed. The normal command leaves `conc=0`. A transparent postprocessing option is to add `RT ln(cB/cA)` to each species' G, with `cA=P/(RT)` from the chosen ideal-gas conditions and both concentrations in the same units; use R and energy units consistently. Shermo can instead apply it with `-conc 1M` (or another specified concentration), as documented in manual sections 2.3 and 3.8. If using that option, inspect the printed concentration-change term and resulting G at the specified concentration; do not add the same term a second time. Concentration correction is unavailable during temperature/pressure scans and does not itself supply a solvent electronic-energy model.
