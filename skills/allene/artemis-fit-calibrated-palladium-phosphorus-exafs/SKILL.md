---
name: artemis-fit-calibrated-palladium-phosphorus-exafs
description: Fit Pd K-edge reference and first-shell Pd–P EXAFS in Demeter Artemis to estimate coordination number and bond distance, starting from processed Athena spectra and supplied structural models.
---

# Reference-calibrated Pd EXAFS fitting

## Setup and required inputs

Use **Demeter 0.9.26 on 64-bit Windows**. Obtain the installer from the official [Demeter download page](https://bruceravel.github.io/demeter/); double-click the 64-bit installer and launch Artemis. The package provides the Athena/Artemis environment and FEFF-based analysis. This is an interactive GUI workflow requiring desktop access.

Have these inputs ready:

| Input | Required preparation |
|---|---|
| Athena project containing Pd-foil and sample spectra | Energy calibration, normalization, background removal and detector corrections already completed; usable χ(k) over the intended k range. |
| Pd-foil structural input | FEFF input, ATOMS input or CIF describing the reference; first Pd–Pd shell has known coordination number 12. |
| Sample structural input | Chemically justified FEFF input, ATOMS input or CIF that produces the proposed Pd–P single-scattering shell. |

Structural-model selection and raw-data processing are supplied preparation. If processing is unfinished, use the official [Athena processing example](https://bruceravel.github.io/demeter/documents/Athena/examples/data.html) before fitting. This workflow estimates parameters conditional on the supplied shell model.

## Import and calculate paths

In Artemis, click **Add** above **Data sets**, open the Athena project, select the foil spectrum and click **Import**. Its χ(k) plot should appear.

In the Data window, click **Import crystal data or a Feff calculation** and select the corresponding structural input. For ATOMS/CIF crystal input, use **Run Atoms** to generate FEFF input; an already prepared FEFF input goes directly to the FEFF step. Click **Run Feff**. From the resulting **Paths** list, drag the first-shell Pd–Pd single-scattering path onto the foil Data window's path list.

Check the path's scatterer, reference half-path length `reff` and degeneracy. Include the intended dataset and path using their **Include in fit** controls. Exclude other paths from this first-shell model. Merely marking a path for plotting does not determine whether it participates in the fit.

## Fit the foil amplitude

Open **GDS**. Enter these rows using the type, name and value/expression columns. Numbers below are illustrative initial guesses, not measured results.

| Type | Name | Initial value |
|---|---|---:|
| guess | amp | 0.8 |
| guess | enot | 0 |
| guess | delr | 0 |
| guess | ss | 0.005 |

On the foil path page enter:

| Path field | Entry | Meaning |
|---|---|---|
| N | `12` | Fixed reference coordination number |
| S02 | `amp` | Fitted amplitude reduction factor S₀² |
| ΔE0 | `enot` | Energy shift, eV |
| ΔR | `delr` | Correction to `reff`, Å |
| σ2 | `ss` | Mean-square relative displacement, Å² |

For this simple example leave additional path corrections `Ei`, `3rd` and `4th` at zero. Every named parameter used by a path must exist in GDS; every active variable must be used.

Set the Data window's k and R ranges to isolate the modeled shell. The [published Pd analysis, Table S6](https://ars.els-cdn.com/content/image/1-s2.0-S1001841725004711-mmc1.docx) used these ranges:

| Spectrum | k range, Å⁻¹ | R fit range, Å |
|---|---:|---:|
| Pd foil | 2.5–12.0 | 1.0–3.0 |
| Pd–P sample | 2.5–12.0 | 1.0–2.1 |

These are study-specific starting settings; restrict them to reliable measured data and the shell represented by the model. Rmin/Rmax also define the fitting interval. Inspect the **k-weight** checkboxes: the documented default selects **1, 2 and 3 simultaneously**. Use that selection for this example and record the window function and taper settings; keep the reference/sample processing and weighting conventions consistent. The plotting k-weight is a separate control.

Click **Fit**. Inspect the results in **Log/History**, including the uncertainty and correlations of `amp`, before transferring its fitted value. Before starting the sample session, export the foil fit as described below and record its fitted amplitude and uncertainty. Too many variables for the independent information in the chosen range makes the model unreliable. The amplitude and coordination number must not both float freely for the same single shell.

## Fit the sample coordination number

Use a fresh Artemis fitting session for the sample so the foil's variables and dataset do not remain active. Import the sample from the Athena project, calculate its supplied structural model, and drag its Pd–P single-scattering path onto the sample dataset.

Create the following GDS rows:

| Type | Name | Value or initial guess |
|---|---|---|
| set | s02_ref | Replace with the accepted foil `amp` value |
| guess | cn | `4` (illustrative starting coordination number) |
| guess | enot | `0` |
| guess | delr | `0` |
| guess | ss | `0.005` Å² |

Set the sample path fields to **N = 1**, **S02 = s02_ref*cn**, **ΔE0 = enot**, **ΔR = delr**, and **σ2 = ss**; use zero for the additional corrections as above.

Artemis requires `N` to be a number, not a fitted expression. Setting it to 1 lets the S02 expression carry the coordination-number factor. Keeping the FEFF degeneracy in N as well would count that factor again. Do not fit a second independent amplitude parameter alongside `cn`.

Set the sample's fit ranges and k-weights, then click **Fit**. Reassess the path model if substantial unexplained structure remains. The [official first-shell example](https://bruceravel.github.io/demeter/documents/Artemis/examples/fes2.html) illustrates the import, path assignment, GDS and Fit controls; its iron-specific structural choices are not Pd inputs.

## Export and interpret

Use **Data → Save data and fit** in each Data window to write column files to chosen paths, for example `pd-foil-fit-k.txt`, `pd-sample-fit-k.txt` and `pd-sample-fit-R.txt`. Select the desired k- or R-space form. Exported columns contain the abscissa, data, fit, background if co-refined, residual, running R-factor and window. Record the fit log's parameter values, uncertainties, correlations and settings alongside these files.

Report:

- `cn`: fitted Pd–P coordination number conditional on fixed S₀².
- `reff + delr`: fitted single-scattering bond distance in Å.
- `ss`, `enot`, R-factor and parameter uncertainties, plus the paths, ranges, weights and windows used.

Compare both χ(k) and R-space data/fit plots and inspect residuals. An uncorrected Fourier-magnitude peak position is not the fitted bond distance. A low R-factor alone does not establish a unique structure or exclude Pd–Pd contributions. Unphysical coordination/disorder values, large uncertainties or strong correlations call for revisiting processing or model adequacy. Fixed `s02_ref` means the fit does not propagate reference-calibration uncertainty into `cn`.

If FEFF produces no relevant path, or fitting stops on a model sanity check, there is no usable fitted shell result: inspect the structural input, path assignment, include controls and GDS definitions before proceeding.
