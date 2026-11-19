---
name: stda-predict-xtb-ecd-transitions
description: Calculate electronic excitation energies and ECD transition strengths for a prepared chiral oligomer with xtb4stda and std2, with optional Gaussian-broadened spectra.
---

# Predict oligomer ECD with sTDA-xTB

Start with an optimized oligomer geometry and known molecular charge and spin. This workflow computes transitions for that geometry; geometry construction, conformer populations and experimental spectra are external inputs. Spectral agreement supports a model comparison but does not by itself establish aggregate structure.

## Obtain the executables

Use a Linux/Bash environment with **xtb4stda 1.0** and **std2 2.0.1** on `PATH`.

- Obtain the standalone `xtb4stda` binary from the [official v1.0 release](https://github.com/grimme-lab/xtb4stda/releases/tag/v1.0). Obtain the same tag's source archive, including hidden parameter files, from the [versioned repository](https://github.com/grimme-lab/xtb4stda/tree/v1.0). Set `XTB4STDAHOME` to its extracted root containing `.param_stda1.xtb`, `.param_stda2.xtb` and `.xtb4stdarc`; put the executable's directory on `PATH` and make the binary executable. The [v1.0 setup instructions](https://github.com/grimme-lab/xtb4stda/blob/v1.0/README.md) also provide source-build alternatives.
- Obtain [std2 2.0.1](https://github.com/Theoretical-Chemistry-Group-UCLouvain/std2/releases/tag/v2.0.1) and follow its [versioned installation instructions](https://github.com/Theoretical-Chemistry-Group-UCLouvain/std2/blob/v2.0.1/README.md#installation). Make requires Intel `ifx`, MKL, CMake and libcint; Meson supports other compilers and linear-algebra backends. Follow the selected build's `PATH` and, where required, `LD_LIBRARY_PATH` setup. For large oligomers, use the documented ILP64 build when LP64 size limits matter.

`xtb4stda` is the specialized ground-state program; an ordinary GFN2-xTB executable is not its replacement. Use `std2` for the excited-state step rather than the older `stda` binary bundled with xtb4stda.

For larger systems the upstream resource guidance is `ulimit -s unlimited` and `export OMP_STACKSIZE=4G`. Set `OMP_NUM_THREADS` and `MKL_NUM_THREADS` to the cores allocated to the job.

## Prepare one calculation directory

| Input | Preparation |
|---|---|
| `oligomer.xyz` | External optimized geometry: XYZ atom count, comment line, then element and x/y/z coordinates in angstroms. A TURBOMOLE `coord` data group is an alternative. |
| `.CHRG` | Molecular charge as an integer on the first line for charged systems. |
| `.UHF` | Number of unpaired electrons (`nalpha - nbeta`) on the first line for open-shell systems; this is not spin multiplicity. |

Use a fresh directory for each geometry/charge/spin combination. The neutral closed-shell example below uses neither charge nor spin file. For a charged/open-shell input, create the appropriate files before the first command. Do not inherit hidden files from another job.

## Generate the transitions

Place `oligomer.xyz` in the calculation directory, enter it, and run these commands sequentially:

```bash
xtb4stda oligomer.xyz > groundstate.out 2>&1
# Inspect groundstate.out and confirm a newly written, nonempty wfn.xtb.
std2 -xtb -e 10 > excitedstates.out 2>&1
# Inspect excitedstates.out and the newly written tda.dat.
head -n 24 tda.dat
```

Proceed to `std2` only after the ground-state job succeeds. `wfn.xtb` is the binary wavefunction handoff, read from the current directory. `-xtb` selects that input instead of a Molden file and sets the method parameters alpha, beta and ax automatically.

`-e` is an energy threshold in **eV** for the excitation configuration space; important configurations above it are added perturbatively. The manual describes the example as computing excitations up to 10 eV. **10 eV is an example choice**, to be adjusted for the spectral region of interest; the documented default is 7 eV. Keep the threshold in the calculation record.

The default is sTDA-xTB with the A+B/2 correction for velocity-form rotatory strengths. Adding `-rpa` changes the method to sTD-DFT-xTB; `-oldtda` removes that correction. XsTD methods cannot use this xTB ground state. Do not add these switches as incidental tuning options.

## Read and optionally broaden the results

Preserve `groundstate.out`, `excitedstates.out`, `wfn.xtb`, the original `tda.dat`, input geometry and charge/spin files. Inspect the logs for parameter-file errors, failed electronic calculations or incomplete excited-state output; file existence alone does not establish success. A missing `wfn.xtb` prevents the handoff. Missing/empty transition data must be investigated before interpreting it as an absent ECD signal.

In `tda.dat`, skip the keyword/value header through `DATXY`. Subsequent numeric rows contain:

| Column | Quantity |
|---|---|
| 1 | State index |
| 2 | Excitation energy, eV |
| 3, 4 | Oscillator strength in length and velocity representations, dimensionless |
| 5, 6 | Rotatory strength in length and velocity representations, in 10^-40 erg cm^3 |

The default sTDA path writes corrected velocity rotatory strengths in column 6; the log labels these `Rv(corr)`. Preserve signed rotatory strengths and distinguish them from nonnegative oscillator strengths. Inspect the actual header rather than assuming every calculation mode emits the same plotting settings.

For a continuous ECD trace, use the versioned [g_spec source](https://github.com/Theoretical-Chemistry-Group-UCLouvain/std2/blob/v2.0.1/g_spec/g_spec.f). It is a standalone Fortran program in the std2 source tree, separate from the main executable. If unavailable on `PATH`, compile that file with GNU Fortran, for example (replace the absolute source path):

```bash
gfortran -O2 -ffixed-line-length-none \
  /absolute/path/std2-2.0.1/g_spec/g_spec.f -o g_spec
cp tda.dat ecd-input.dat
# Review/edit only the plotting header of ecd-input.dat as described below.
./g_spec < ecd-input.dat > plotting.out
head spec.dat
head rots.dat
```

For an already installed plotting executable, use `g_spec` instead of `./g_spec`. Run in the calculation directory; existing `spec.dat` and `rots.dat` may be overwritten, so preserve prior plots before changing settings.

For the default corrected sTDA path, the generated header already selects `NM` and `VELO`, omits `UV` (thus selects CD), and uses the numerical settings below. For a deliberate ECD plotting setup, review the copy before invoking `g_spec`:

| Header item | Meaning and example setting |
|---|---|
| `UV` | Omit for CD; include only for absorption. |
| `VELO` | Include to select velocity strengths; omit for length strengths. |
| `NM` | Include for wavelength in nm; omit for energy in eV. Raw transition energies remain in eV. |
| `WIDTH` then `0.20` on the next line | Gaussian half width at 1/e maximum, in eV; not FWHM. |
| `SHIFT` then `0.00` | Energy shift in eV, applied before conversion to wavelength. |
| `LFAKTOR` then `0.5` | Additional stick-only scaling; with `RFAKTOR=1`, the generated default halves stick values. |
| `RFAKTOR` then `1.0` | Overall scaling applied to both the broadened spectrum and sticks. |

Keep `MMASS` and its value, `DATXY`, and all transition rows intact. These width/shift/scale values are software defaults, not publication-specific choices. The uncorrected writer can insert `UV`, so explicitly check it when working with other calculation modes.

`spec.dat` contains the Gaussian-broadened molar CD spectrum (molar extinction for UV), in L mol^-1 cm^-1, multiplied by `RFAKTOR`. For CD, `rots.dat` contains the selected rotatory strengths multiplied by `LFAKTOR` and `RFAKTOR`, still in 10^-40 erg cm^3; these sticks are not converted to molar CD. For UV, stick values are oscillator strengths multiplied by 10^5 and both scale factors. Both files use the x axis selected by `NM`. Keep stick amplitudes distinct from broadened intensities when labeling or comparing plots.

Return the transition data with the calculation settings; include the plotted files only if requested. For experimental comparison, report representation, cutoff, width definition/value, shift, scales and axis units. A single-geometry spectrum contains no conformer/population averaging; that requires externally supplied populations and an explicit downstream combination.
