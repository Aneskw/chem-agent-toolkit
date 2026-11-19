---
name: goodvibes-calculate-cli-quasi-harmonic-thermochemistry
description: Use the GoodVibes 4.4.0 CLI to calculate Grimme or Truhlar quasi-harmonic Gibbs energies from completed Gaussian frequency outputs, optionally incorporating matched higher-level single-point energies.
---

# Corrected thermochemistry from Gaussian logs

Use GoodVibes to replace the frequency calculation's electronic energy with a higher-level single-point energy while retaining its thermal contributions and applying Grimme quasi-RRHO entropy. Optimization, conformer sampling and validation of stationary points are upstream work. Coordinates or an XYZ energy comment cannot replace a frequency log.

## Setup and input preparation

Use **GoodVibes 4.4.0** with **Python 3.9 or newer**. Obtain it through the [official project](https://github.com/patonlab/GoodVibes/tree/v4.4.0):

```shell
python -m pip install goodvibes==4.4.0
```

Run the installed `goodvibes` executable in that Python environment. Gaussian itself is not needed for this postprocessing step; its completed output files are supplied inputs.

Prepare one pair per structure in a working directory:

| File | Required content |
| --- | --- |
| `reactant.log` | Completed Gaussian frequency calculation: electronic energy, frequencies and molecular/rotational data |
| `reactant_TZ.log` | Completed higher-level single-point calculation for the same geometry, charge and multiplicity |
| `transition_state.log`, `transition_state_TZ.log` | Equivalent pair for the transition structure |

Names are illustrative. With `--spc TZ`, a frequency input `NAME.log` is paired with `NAME_TZ.log` or `NAME_TZ.out`. Keep paired files together and list the frequency files as positional inputs. Gaussian 09/16 `.log` and `.out` files are supported.

Use consistent frequency methods and consistent single-point methods/solvation across comparisons. Supply solvent-corrected single-point logs if the protocol requires implicit solvation: `--conc` changes the thermochemical standard state, not the electronic solvation model.

## Calculate and inspect

From the directory containing those pairs, run:

```shell
goodvibes reactant.log transition_state.log --spc TZ --temp 333.15 --conc 1.0 --qs grimme --fs 100 --imag --check --output thermo
```

Adapt these settings to the intended protocol:

| Setting | Meaning |
| --- | --- |
| `--temp 333.15` | Temperature in Kelvin; 333.15 K = 60 °C. Default is 298.15 K. |
| `--conc 1.0` | Solution standard concentration in mol/L. Omission uses the gas-phase 1 atm standard state. |
| `--qs grimme --fs 100` | Grimme free-rotor interpolation for vibrational entropy, with a 100 cm⁻¹ cutoff |
| `--imag` | Display imaginary frequencies for inspection |
| `--check` | Report input consistency diagnostics |
| `--output thermo` | Write `GoodVibes_thermo.dat` in the current directory |

This example retains harmonic enthalpy. Adding `-q` enables both the entropy treatment and Head-Gordon quasi-harmonic enthalpy; `--qh` also enables that enthalpy correction. Use those only when the selected protocol calls for them.

Frequency scaling is automatic: GoodVibes looks up separate harmonic and ZPE factors where available. Inspect and retain the reported factors with the result. To supply a protocol's factors explicitly, add `-v FACTOR --zpe-vscal ZPE_FACTOR`; both factors are dimensionless. For deliberately unscaled frequencies and ZPE, use `-v 1.0 --zpe-vscal 1.0`. These choices affect the calculated energies.

For a Gaussian file containing frequency and subsequent single-point Link1 jobs, the documented alternative is `--spc link`; separate matching files are the normal path above.


## Read the results

Read the table and diagnostics in `GoodVibes_thermo.dat`:

- `E`: electronic energy from the frequency calculation.
- `E_SPC`: replacement electronic energy from the single-point calculation.
- `G(T)_SPC`: harmonic Gibbs energy incorporating that replacement.
- `qh-G(T)_SPC`: the desired entropy-corrected Gibbs energy for this example.

Energy columns, including `T.S` and `T.qh-S`, are in Hartree. The SPC correction is already included in both Gibbs columns: do not add `E_SPC - E` again.

For each chemically balanced reaction or activation step, sum the relevant corrected species energies with their stoichiometric coefficients. An activation barrier is the transition-state energy minus the energy of its corresponding reactant state; include all separate reactant species when required by the model. Convert a Hartree difference to kcal/mol by multiplying by 627.5095. Comparing two conformers directly requires the same composition. These are computed free energies; a barrier difference alone does not establish an observed product ratio.

## Resolve incomplete or suspect output

- A missing matching SPC file causes an error identifying the expected suffix. Correct the name or provide the calculation.
- `----` in `E_SPC` means no usable SPC energy was parsed. Do not accept even a numerical Gibbs entry as the requested corrected result.
- `No frequency information found`, missing species rows or a linear-molecule warning require checking the original calculation and parser output. Missing thermochemistry is not a zero energy or evidence that a species is absent.
- Inspect consistency diagnostics and the original logs. Minima should have zero imaginary frequencies; transition structures should have one whose displacement follows the intended reaction. A printed table and `--check` do not establish stationary-point validity or reaction connectivity.
- The example leaves imaginary frequencies uninverted. Do not add `--invert` merely to suppress an unexpected negative mode; it changes frequencies used in thermochemistry.

For options beyond this path, consult the [versioned README examples and CLI reference](https://github.com/patonlab/GoodVibes/blob/v4.4.0/README.md).

## Truhlar entropy-only analysis without SPC

For a protocol specifying Truhlar treatment, use `--qs truhlar`: positive frequencies below the cutoff are raised for entropy. Grimme's interpolation is a different treatment; choose the requested scientific protocol. With no requested single-point replacement, omit `--spc` and provide frequency files only. This complete example retains harmonic enthalpy and deliberately unscaled frequencies/ZPE:

```sh
goodvibes conformer_A.log conformer_B.log --qs truhlar --fs 100 -v 1.0 --temp 298.15 --conc 1.0 --check --imag --output thermochemistry --json thermochemistry.json
```

The command writes `GoodVibes_thermochemistry.dat` and `thermochemistry.json` and prints a table to the console.

| Result | Access and meaning |
|---|---|
| Harmonic Gibbs energy | `G(T)` in the table; `results[*].thermo.gibbs_free_energy` in JSON. |
| Corrected Gibbs energy | `qh-G(T)`; `results[*].thermo.qh_gibbs_free_energy`. This includes electronic energy and thermal contributions, rather than only the correction. |
| Input identity | Match each JSON result by `file` or `name`. |
| Frequency diagnostics | Inspect `im freq` in the report and `thermo.im_frequency_wn` in JSON. |

The example's `-v 1.0` also sets inherited ZPE scaling to 1.0. Apply the same completion, imaginary-mode and standard-state checks as the main workflow; do not add the SPC difference or a standard-state correction twice.
