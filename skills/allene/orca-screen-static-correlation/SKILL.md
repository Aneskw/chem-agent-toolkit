---
name: orca-screen-static-correlation
description: Use ORCA fractional-occupation density analysis to screen the amount and spatial distribution of static correlation from prepared molecular coordinates and an electronic state.
---

# Screen static correlation with ORCA FOD

FOD provides a scalar diagnostic and a spatial map of potentially strongly correlated electrons. Use it as an initial indication when judging whether a single-reference treatment warrants further investigation; combine it with more sophisticated diagnostics before drawing a multireference conclusion.

## Prepare ORCA and the molecular input

Use **ORCA 6.1.1**, including its bundled `orca_plot` utility. Obtain the platform build through the [official release and download links](https://www.faccts.de/orca-6-1-1/): the ORCA Forum requires registration for academic downloads; FACCTs provides academic and commercial acquisition. Follow the [installation instructions](https://www.faccts.de/docs/orca/6.1/manual/contents/quickstartguide/installation.html). The example below uses a serial calculation. Make the ORCA executables available on `PATH`, opening a new terminal after installation, or invoke them by their installed paths.

Required inputs:

| Input | Preparation |
|---|---|
| Molecular geometry | A prepared single-structure XYZ file: atom count, comment line, then element and x/y/z coordinates in Ångström. |
| Net charge | Integer molecular charge. |
| Multiplicity | Integer `2S+1`; use the intended electronic state. |
| Calculation directory | Put the XYZ and input file together; use a fresh directory/basename for each system to keep results distinct. |

This workflow evaluates the supplied geometry; geometry optimization is a separate preparation step.

## Run the diagnostic

For a neutral singlet, save this ASCII input as `screen.inp` beside the externally supplied `molecule.xyz`:

```text
! FOD
* xyzfile 0 1 molecule.xyz
```

Replace `0 1` with the actual charge and multiplicity. The external-file coordinate directive has no closing star line. The `FOD` keyword selects **TPSS/def2-TZVP with TightSCF**, using electronic smearing at **5000 K**.

From that directory, run in a terminal (Windows Command Prompt or a POSIX shell):

```sh
orca screen.inp > screen.out 2>&1
```

Inspect `screen.out` for SCF convergence and `ORCA TERMINATED NORMALLY` before interpreting it. Retain `screen.gbw` and `screen.densities` for plotting.

If deliberately choosing a different functional, replace the simple input line and add the corresponding electronic temperature. For example, the documented B3LYP alternative is:

```text
! B3LYP def2-TZVP TightSCF
%scf
  SmearTemp 9000
end
* xyzfile 0 1 molecule.xyz
```

The manual's empirical prescription is `T_el = 20000 K × a_x + 5000 K`, with Fock-exchange fraction `a_x` expressed as a fraction: TPSS 0 → 5000 K, B3LYP 0.20 → 9000 K, PBE0 0.25 → 10000 K, M06-2X 0.54 → 15800 K. This is an electronic smearing parameter, not a molecular sample temperature. FOD depends strongly on the functional's gap and smearing; record both and use a consistent protocol for comparisons. See [FOD basic usage](https://www.faccts.de/docs/orca/6.1/manual/contents/spectroscopyproperties/fod.html#basic-usage) when customizing.

## Read the scalar and atomic output

In `screen.out`, locate:

- `FOD:` and `N_FOD =`: the integrated FOD, a size-extensive scalar indicating the overall amount of static correlation. Account for molecular size when comparing values; do not invent a universal cutoff.
- `FOD BASED MULLIKEN REDUCED ORBITAL CHARGES`: atomic/orbital contributions that help locate the signal. These refer to the FOD, rather than ordinary molecular partial charges. Match the zero-based atom labels to the input ordering.

With `SmearTemp > 0`, the FOD analysis is printed automatically. The usual spin-squared expectation is omitted because it is undefined for fractional occupations. Missing FOD output or unconverged SCF is an incomplete diagnostic, not evidence of negligible correlation.

## Export the spatial density

The density named `screen.scfp_fod` is stored **inside `screen.densities`**; it need not exist as a separate file. Keep the container with `screen.gbw` and run:

```sh
orca_plot screen.gbw -i
```

Use the displayed menu labels, following this sequence:

1. **List all available densities** (9): confirm `screen.scfp_fod` is present.
2. **Enter type of plot** (1), then **electron density** (2). Reject the default density name with `n` and enter `screen.scfp_fod`.
3. **Enter number of grid intervals** (4): enter `120`, the documented high-resolution example. This can produce large cubes and take considerable time.
4. **Select output file format** (5): choose **Gaussian cube** (7).
5. Confirm that the selected density is the FOD, then **Generate the plot** (11). Record the actual path printed after `PLOTTING FINISHED` / `Output file:`; do not assume the cube filename.
6. **Exit** (12).

The [utility reference](https://www.faccts.de/docs/orca/6.1/manual/contents/utilitiesvisualization/utilities.html#orca-plot) supplies these generation/exit menu numbers. Follow the live labels if they differ.

Hand the resulting cube to a cube-capable molecular viewer. Display its positive isosurface at **0.005 e/Bohr³**, keeping that value fixed across compared systems. For borderline cases, additionally inspect **0.002 e/Bohr³**, explicitly labeling that different level. No visible surface at a chosen contour does not establish zero FOD.

Report the input state and geometry identifier, functional/basis/SmearTemp, `N_FOD`, dominant atomic contributions, cube path, contour level and whether the map is localized or delocalized. Strong delocalized FOD motivates further multireference assessment; it does not itself prove a classification or select a replacement method. If the FOD density is missing from the container, resolve the calculation/file mismatch before interpreting an ordinary SCF density as FOD.
