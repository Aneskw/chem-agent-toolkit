---
name: artemis-fit-palladium-exafs-coordination
description: Fit palladium EXAFS coordination models in Demeter Artemis with FEFF paths, starting from processed Athena data and structural references, and export structural parameters and fit diagnostics.
---

# Palladium EXAFS fitting with Artemis and FEFF

## Prepare the software and inputs

Use **Demeter 0.9.26 for Windows 64-bit**, obtained through the official [Windows Installer](https://bruceravel.github.io/demeter/#windows). Run the installer, then launch Artemis in the installed Demeter suite. This workflow uses its graphical interface and FEFF calculation controls. The [0.9.26 guide](https://bruceravel.github.io/demeter/documents/Artemis/) documents this interface.

Have these external inputs ready:

| Input | Required content |
|---|---|
| Athena project | Processed Pd EXAFS datasets for a known solid calibration reference and the samples; processing and energy calibration are upstream tasks. |
| Structural models | Appropriate `atoms.inp`, CIF, or `feff.inp` files with Pd as absorber and the intended edge and local structure. Supply a model for each chemically distinct environment to be tested. |
| Fit specification | Reliable k interval in Å⁻¹, R interval in Å, transform windows, and justified shell constraints for each dataset. |

For the allylpalladium application, the [study supplement, §4.3, pp. 24–26](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10952092/supplementaryFiles) (ZIP containing `SC-015-D3SC06408E-s001.pdf`) identifies CCDC 1102405 for allylpalladium chloride dimer and ICSD 41431 for the oxygen-containing reference. Obtain the corresponding structure files through [CCDC/FIZ Access Structures](https://www.ccdc.cam.ac.uk/structures/), whose identifier field accepts CCDC and ICSD numbers, if using those models. The spectra and project files are external inputs, not included here.

## Import data and generate paths

1. In Artemis, click **Add** above **Data sets**, open the Athena project, select the solid reference and click **Import**. Repeat for solution datasets when ready.
2. In its Data window, click **Import crystal data or a Feff calculation** and select the structural input. For crystal/ATOMS input, check the absorber and structure, then click **Run Atoms** to create FEFF input. Direct `feff.inp` input starts at the FEFF stage.
3. Check the FEFF input and click **Run Feff**. A completed calculation supplies the **Paths** interpretation list. Select relevant paths and drag them onto the dataset's path list. Paths must be associated with the dataset they model.
4. Examine single- and multiple-scattering contributions against the data using the plotting list. Select paths on physical and spectral grounds; a path's list position is not a transferable shell assignment. A first-shell model is appropriate only when excluded paths do not contribute materially in the chosen range.

The [worked example, §§13.1.1–13.1.3](https://bruceravel.github.io/demeter/documents/Artemis/examples/fes2.html) illustrates these exact controls; its iron paths and numerical settings are not Pd inputs.

## Parameterize and run a reference fit

Open **GDS** from the Main window. `guess` parameters vary during fitting; `set` parameters remain fixed; `def` expressions are reevaluated from other parameters. Define every name used in path expressions and use every `guess`/`def` parameter in the model.

For a representative C/Cl shell model, create `amp`, `enot`, `dr_c`, `dr_cl`, `ss_c`, and `ss_cl` as `guess` parameters. Illustrative initial values are 0.9, 0, 0, 0, 0.01, and 0.005 respectively; choose values appropriate to the supplied structure and data. These are starting choices, not reported fit results. Add `n_c` and `n_cl` as `set` parameters containing known reference coordination numbers. For the study's solid allylpalladium dimer these are 3 and 2.

For each single-scattering shell group, record `D`, the sum of FEFF degeneracies of the paths representing that shell. Keep each path's numeric **N** equal to its FEFF degeneracy and enter these expressions on its Path page:

| Path field | C shell | Cl shell | Meaning |
|---|---|---|---|
| `S02` | `amp*n_c/D_c` | `amp*n_cl/D_cl` | Amplitude scaled to total shell coordination; define `D_c`, `D_cl` as numeric `set` constants from the actual path list. |
| ΔE₀ | `enot` | `enot` | Energy shift in eV, shared across paths. |
| ΔR | `dr_c` | `dr_cl` | Change from FEFF half path length in Å. |
| σ² | `ss_c` | `ss_cl` | Mean-square path-length variation in Å². |

This normalization is an adaptation of the documented amplitude expression: the sum of numeric path degeneracies times `n/D` equals the requested coordination. Apply it to a defined single-scattering shell group, not indiscriminately to multiple-scattering paths. **N cannot contain a variable or expression**; unknown coordination belongs in `S02`. Do not also replace N by the fitted coordination, which would count it twice. See [Path parameters](https://bruceravel.github.io/demeter/documents/Artemis/path/pathparams.html).

If the model includes inequivalent C distances, retain their individual FEFF distances unless an effective-shell approximation has explicitly been supplied. The study instead used one effective carbon environment with N=3 and notes that this can increase apparent σ² because the three Pd–C distances differ. The grouped-path template above does not reproduce that collapse automatically. Oxygen-containing sample models require their own reference paths, coordination, ΔR and σ² parameters; do not reuse a Cl path for O.

In the Data window, explicitly choose fit space **R**, set the reliable **kmin/kmax** and **Rmin/Rmax**, and choose the fitting k-weight(s). For the study-style settings use k² weighting and a **Hanning** window, with forward k taper width 1 Å⁻¹ and backward R taper width 0 Å. The supplement calls both widths “dk”; use the respective k- and R-space controls. When available, **Data → Set window function** sets the functional form in both directions; independent window controls require the `Artemis → window_function` preference set to `user`. The study used sample-dependent k ranges; it does not supply a universal numerical fitting interval.

Check **Data → Show Nidp** and compare independent points with the number of `guess` parameters. Ensure only intended datasets and paths have **Include in fit** checked; marking a path is separate from including it. Give the fit a descriptive name and click **Fit**. Resolve sanity-check errors such as missing symbols, unused variables, or absent paths before interpreting a fit. See [Running a fit](https://bruceravel.github.io/demeter/documents/Artemis/fit/index.html).

## Transfer calibration and fit samples

Inspect the reference fit first. Then record its fitted `amp` and `enot`, change them to `set` with those numerical values, and use them across the solution models. For each solution, change `n_c` and `n_cl` to `guess` if coordination is unknown, retain sample-specific distance/disorder parameters, and rerun the fit. Fit the reference separately or remove its **Include in fit** check when fitting a solution alone. Add oxygen paths only for a model that calls for them.

The study calibrated amplitude and E₀ on solid allylpalladium dimer and held them fixed for solution fits. Refit your own reference; its published values are not universal calibration constants. Fixing these terms makes subsequent uncertainties conditional on that calibration.

## Inspect and export results

Use **Log** and **History** to inspect the following before reporting parameters:

- `guess` estimates and error bars, their correlations, independent points, and number of fitted variables;
- χ², reduced χ², R-factor, noise estimates, and sanity/happiness messages;
- data and fit in k and R space, including the real part as well as magnitude. **Rmr** shows magnitude and real part; **Rk** adds χ(k). A small R-factor or a favorable button color alone does not establish a unique structure.

For a single-scattering path, report distance as **R = FEFF half path length + ΔR**, not the uncorrected Fourier-peak position. Report N from the shell coordination variable, not solely the numeric N box. With split paths, report their distinct distances rather than inventing an average. Report σ² in Å²; multiply by 1000 only if explicitly labeling a table in units of 10⁻³ Å².

The [Log guide, §9.1](https://bruceravel.github.io/demeter/documents/Artemis/logjournal.html) states that error bars are given for `guess` parameters and are **not propagated to evaluated path parameters** in this interface. Direct `dr` uncertainties also describe R when the FEFF distance is treated as fixed. More complex derived expressions require covariance-aware propagation; do not attach a guessed error bar. Inspect strong coordination/amplitude/disorder correlations and unstable or unphysical values before drawing structural conclusions.

Export to user-selected filenames and retain the model alongside the report:

| Action | Result |
|---|---|
| **History**, right-click the desired fit → **Save log file** | Text fit report with parameters and diagnostics. |
| **History**, right-click → **Export fit** | Artemis project containing that fit alone in its history. Saving the full project retains the broader history. |
| Data window **Data → Save data and fit** | Column data in selected k/R/q representation, including data, fit, residual and window arrays. |

Verify that the exported history entry is the intended model. **Restore fitting model** replaces the current window state; it is not a passive comparison action. See [History](https://bruceravel.github.io/demeter/documents/Artemis/history.html) and [Data menu](https://bruceravel.github.io/demeter/documents/Artemis/data.html#the-data-menu) for export choices.
