---
name: shermo-analyze-vibrational-thermochemistry
description: Use Shermo to calculate thermochemical corrections from completed molecular frequency outputs and inspect individual vibrational contributions when electronic and Gibbs free-energy preferences differ.
---

# Compare molecular thermochemistry and vibrational contributions

## Prepare Shermo and inputs

Obtain **Shermo 2.6.2** from the [official executable package](http://sobereva.com/soft/shermo/Shermo_2.6.2.zip), linked on the [project page](http://sobereva.com/soft/shermo/). Unpack it: `Shermo.exe` runs on Windows and `Shermo` on Linux; no Python environment is required. Use the [matching manual](http://sobereva.com/soft/shermo/Shermo_manual_2.6.2.pdf), especially §§2.3–2.4 for settings and input details.

Start with completed Gaussian 09/16 `freq` or `opt freq` output files, here supplied as `inputs/TS1.out` and `inputs/TS2.out`. Shermo reads the electronic energy, multiplicity, atomic masses, coordinates and harmonic frequencies; for optimization jobs it loads the final geometry. Anharmonic frequencies are ignored. Electronic-structure calculations and stationary-point validation must already be complete. This workflow uses molecular ideal-gas thermochemistry; it does not establish that a structure is a minimum or transition state.

## Calculate an explicit baseline

The following illustrative baseline uses 298.15 K, 1 atm, unscaled frequencies and harmonic RRHO. These are example choices to replace with the requested conditions. Shermo's default `ilowfreq` is **2**, so explicitly setting it to **0** matters.

| Option | Meaning in this run |
| --- | --- |
| `-noset` | Ignore `settings.ini`; unspecified options use built-in defaults. Otherwise the current directory's settings file takes precedence over the `Shermopath` directory's file, and CLI options override settings. |
| `-T 298.15 -P 1` | Temperature in K; pressure in atm. |
| `-ilowfreq 0` | Harmonic RRHO treatment. |
| `-prtvib -1` | Write individual-mode contributions to `vibcontri.txt` in the current directory. |
| Unspecified scale factors | `sclZPE`, `sclheat`, `sclS`, `sclCV` each default to 1.0. |
| Unspecified `conc` | Default 0: no additional concentration correction; results correspond to the specified T and P. |

In PowerShell, replace the executable path with its actual unpacked location. Run from a working directory containing `inputs`. Use new output directories for each structure and treatment: output redirection replaces an existing log, and the fixed `vibcontri.txt` name needs its own directory.

```powershell
$shermo = 'C:\tools\Shermo_2.6.2\Shermo.exe'
$ts1 = (Resolve-Path '.\inputs\TS1.out').Path
$ts2 = (Resolve-Path '.\inputs\TS2.out').Path
New-Item -ItemType Directory -Path '.\TS1-rrho', '.\TS2-rrho' | Out-Null

Push-Location '.\TS1-rrho'
& $shermo $ts1 -noset -T 298.15 -P 1 -ilowfreq 0 -prtvib -1 > thermo.txt
Pop-Location

Push-Location '.\TS2-rrho'
& $shermo $ts2 -noset -T 298.15 -P 1 -ilowfreq 0 -prtvib -1 > thermo.txt
Pop-Location

Get-Content '.\TS1-rrho\thermo.txt'
Get-Content '.\TS1-rrho\vibcontri.txt'
Get-Content '.\TS2-rrho\thermo.txt'
Get-Content '.\TS2-rrho\vibcontri.txt'
```

On Linux, invoke the unpacked executable by its path, e.g. `/opt/Shermo_2.6.2/Shermo /data/TS1.out -noset -T 298.15 -P 1 -ilowfreq 0 -prtvib -1 > thermo.txt`, from a dedicated directory; substitute actual paths.

Inspect each log's running parameters and **Molecular information** before using its **Total** block: verify energy, multiplicity, masses, point group/rotational symmetry number and loaded frequencies against the intended input. Ordinary harmonic calculations ignore imaginary modes; inspect their presence upstream rather than treating a completed Shermo run as validation. Missing totals, missing requested `vibcontri.txt`, or inconsistent loaded data leave the analysis incomplete. Diagnose the input/parameters before comparing results. Single-file runs are necessary here: the `.txt` conformer-list mode does not support `prtvib`.

## Select low-frequency and standard-state treatments

For flexible molecules, compare the baseline with an explicitly chosen quasi-RRHO treatment in new directories. Repeat the same commands for both structures, replacing `-ilowfreq 0` with one of:

| Options | Treatment |
| --- | --- |
| `-ilowfreq 2 -intpvib 100` | Grimme interpolation between harmonic and free-rotor models for entropy only. |
| `-ilowfreq 3 -intpvib 100` | Interpolation for entropy and internal energy. |

`intpvib` is the interpolation threshold in cm^-1; 100 is the documented default and an explicit example choice. Keep all other conditions consistent. For modes 2/3, printed partition functions remain the harmonic ones; they do not encode the quasi-RRHO corrections.

If the requested standard state is 1 mol/L, add `-conc 1M` to both single-temperature runs. Shermo computes `RT ln(cB/cA)`, with `cA=P/(RT)`, and prints a separate concentration-corrected Gibbs energy after the Total-block sums; select the output as described below. Concentration correction is not applied during temperature/pressure scans. It converts concentration conventions within the model; it does not supply a solvation free energy.

## Interpret and report

Use the **Total** block's `Thermal correction to G` as `Gcorr`; it excludes the concentration correction. Let `Cconc` be the separately printed `delta-G of conc. change`, or zero when `conc=0`. Select the Gibbs energy for reporting as follows:

| Setting | Output to use as `G` |
| --- | --- |
| `conc=0` | `Sum of electronic energy and thermal correction to G` (`E + Gcorr`). |
| Nonzero `conc` | Final `Gibbs free energy at specified concentration` (`E + Gcorr + Cconc`), in Hartree. |

Thermal corrections already include ZPE; do not add ZPE again. Use the analogous H sum for enthalpy. If a separate, supplied single-point energy at the same geometry is intended, calculate `G = E_singlepoint + Gcorr + Cconc` with all terms in matching units, or specify it with `-E <energy-in-hartree>` and select the appropriate output above. Record that substitution. The final concentration-corrected value already includes `Cconc`; do not add it again.

For a consistent sign convention, define every difference as TS1 minus TS2:

- `deltaE = E(TS1) - E(TS2)` and `deltaG = G(TS1) - G(TS2)`; a negative difference favors TS1 under that model.
- `deltaG = deltaE + deltaGcorr + deltaCconc`. For both structures at the same T, P and target concentration, `Cconc` is identical and cancels in the difference, although each reported G must use the selected standard state. Compare the electronic term and corrections separately to explain a reversal.
- Entropy enters as `-T*deltaS`. Convert J/mol/K to kJ/mol with `/1000`, or cal/mol/K to kcal/mol with `/1000`, before combining with energy. Keep Hartree totals and molar-energy corrections in consistent units.

In `vibcontri.txt`, the second table gives mode, unscaled wavenumber (cm^-1), ZPE, `U(T)-U(0)`, `U(T)` (kcal/mol), `CV(T)` and `S(T)` (cal/mol/K). Wavenumber and frequency labels remain unscaled even when scale factors affect thermodynamic contributions. Examine low-wavenumber modes and their `S(T)` values to locate the vibrational contribution to the entropy difference. Mode indices are local to each structure; do not assume equal indices identify the same physical motion. Inspect upstream normal-mode visualizations if assigning motions is required.

Report T, P, concentration convention, all scale factors, low-frequency model/threshold, electronic energy source, deltaE, deltaGcorr, Cconc (if used) and deltaG, with links/paths to both logs and mode tables. Distinguish vibrational entropy from total entropy, which also contains translation, rotation and electronic terms. A low-frequency contribution supports a thermochemical explanation within the selected model; it alone does not establish a reaction mechanism or product ratio.
