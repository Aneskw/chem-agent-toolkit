---
name: gaussian-validate-stationary-points
description: Optimize prepared molecular structures with Gaussian 16 and validate minima or supplied transition-state guesses using frequencies, convergence diagnostics and thermochemical corrections.
---

# Validate molecular stationary points with Gaussian

Use this workflow when coordinates, charge, multiplicity and an appropriate model chemistry are already supplied. It produces an optimized geometry, vibrational classification and thermochemical quantities. Finding reaction pathways or the global minimum requires additional work.

## Environment and input contract

Use licensed **Gaussian 16 Rev. C.02** on a supported Linux AVX2 platform. Obtain it through [Gaussian Orders/Contact](https://gaussian.com/orders/) and follow the vendor's [installation instructions](https://gaussian.com/techsupport/#install). Check the [official platform requirements](https://gaussian.com/g16/g16_plat.pdf) before choosing a binary. This workflow uses one compute node; network parallel setup is outside its scope.

Start in an allocated compute environment with `g16` on PATH and site-configured writable Gaussian scratch storage. On managed clusters, load the site's C.02 module; module names and scheduler directives are site-specific.

| Input | Required preparation |
| --- | --- |
| Molecular structure | Element symbols and Cartesian coordinates in angstroms; chemically reasonable starting geometry |
| Electronic state | Total integer charge and spin multiplicity |
| Model chemistry | Validated method, basis sets, any ECPs, dispersion and solvent settings |
| Search goal | Local minimum, or an already prepared transition-state guess |
| Resources | Allocated CPU cores, memory and scratch capacity; match Gaussian requests to the allocation |

Keep the same method, basis, ECP and other model settings for optimization and frequency evaluation. Frequencies at a geometry optimized with a different model do not validate that geometry. Supply any general-basis/ECP input sections required by the chosen model; the compact example below uses a built-in basis.

## Prepare and run a job

Save the following as `water.com`, including a blank line after the last atom. This is an illustrative minimum search, with example resource settings and water coordinates; replace them for the supplied system. Do not replace an established scientific model with this example's B3LYP/6-31G(d).

```text
%NProcShared=4
%Mem=5GB
%Chk=water.chk
# B3LYP/6-31G(d) Opt Freq

Water minimum and frequency validation

0 1
O   0.000000   0.000000   0.000000
H   0.000000   0.000000   0.960000
H   0.929422   0.000000  -0.240364

```

`Opt` searches for a local minimum by default; `Freq` evaluates the final structure using the same model. Thermochemistry defaults are 298.15 K, 1 atm, unscaled frequencies and the most abundant isotopes. Read the temperature and pressure actually reported in the log. If supplied conditions differ, set them explicitly, for example `Temperature=298.0 Pressure=1.0` on the route line.

From the directory containing the input, invoke Gaussian using a Linux shell:

```bash
g16 < water.com > water.log
```

The log contains the optimized coordinates, convergence diagnostics, frequencies, displacement vectors and thermochemistry. `%Chk=water.chk` names the checkpoint file relative to this working directory. Use distinct job/log/checkpoint names for each structure or retry; shell redirection replaces an existing log.

### Supplied transition-state guess

Keep the supplied model and geometry, change the names, and replace `Opt` with `Opt=(TS,CalcFC)`. For the example model, the route becomes:

```text
# B3LYP/6-31G(d) Opt=(TS,CalcFC) Freq
```

`TS` requests a transition-state search; `CalcFC` computes initial force constants. A minimum geometry is not automatically a useful TS guess. Keep the curvature test enabled; adding `NoEigenTest` does not establish a valid transition state. See [Opt options](https://gaussian.com/opt/) for search details.

## Inspect the result

1. Find `Optimization completed.` and `Stationary point found.`, then inspect the final optimized geometry. A started job, an intermediate geometry or a converged electronic energy alone is insufficient.
2. Confirm that the frequency calculation also completed. Read the `Frequencies --` rows in the harmonic vibrational analysis, in cm^-1, and inspect their associated displacement vectors.
3. Classify the projected vibrational modes: no imaginary modes supports a local minimum; exactly one supports a first-order saddle point. Gaussian prints imaginary frequencies as negative values. For a proposed TS, verify that its imaginary-mode displacements describe the intended chemical motion. Multiple imaginary modes or the wrong motion do not validate the intended TS.
4. Separately inspect the preliminary `Low frequencies ---` diagnostic, which includes rotations and translations. Do not count its near-zero entries as extra imaginary vibrations. Disagreement with the later vibrational frequencies can indicate contamination or inadequate convergence.

For ambiguous soft modes, revisit convergence and integration accuracy rather than applying an arbitrary frequency cutoff. A DFT retry can use `Opt=Tight Int=UltraFine Freq`, or `Opt=(TS,CalcFC,Tight) Int=UltraFine Freq` for a TS. Repeat optimization and frequencies consistently. Gaussian also documents `Opt=CalcAll` when the exact Hessian reveals incomplete geometric convergence. See [frequency output and convergence diagnostics](https://gaussian.com/freq/) and the [vibrational-analysis note](https://gaussian.com/wp-content/uploads/dl/vib.pdf).

## Read thermochemistry and report

The thermochemistry block supplies these fields in Hartree per particle:

| Log field | Meaning |
| --- | --- |
| `Zero-point correction` | ZPVE contribution |
| `Thermal correction to Energy/Enthalpy/Gibbs Free Energy` | Corresponding correction, already including ZPVE |
| `Sum of electronic and zero-point Energies` | Electronic energy plus ZPVE |
| `Sum of electronic and thermal Energies/Enthalpies/Free Energies` | Corresponding corrected total |

Do not add ZPVE a second time to a thermal correction or corrected total. These are ideal-gas statistical-mechanical quantities with harmonic vibrations; soft internal rotations can strongly affect entropy. They are not automatically solution-standard-state free energies.

When vibrational data are requested, retain paired `Frequencies --` (cm^-1) and `IR Inten --` (km/mol) rows from the same completed analysis. These are harmonic stick-spectrum data; do not introduce an undocumented frequency scale or broadening.

For a same-level reaction comparison, use `delta_G = sum(nu_i * G_i)`, with positive stoichiometric coefficients for products and negative coefficients for reactants. Define the reactant reference explicitly for a barrier. Keep the energy definition, model and thermochemical conditions consistent; compare totals with totals, not with corrections.

Geometry curvature does not certify electronic wavefunction stability. If that is in question, assess it separately using the documented [Stable facility](https://gaussian.com/stable/) before relying on the frequency result.

Return the final geometry, input/log/checkpoint paths, actual model and conditions, convergence status, imaginary-mode count and motion, and the selected energy/correction fields with units. Label incomplete calculations as incomplete and unresolved soft-mode cases as unresolved. A stationary-point classification supports a local calculation; it does not by itself prove global stability or reaction connectivity.
