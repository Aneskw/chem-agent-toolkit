---
name: gaussian-combine-supplied-single-point-thermochemistry
description: Use Gaussian 16 to optimize supplied molecular structures, validate minima or transition-state guesses with harmonic frequencies, and extract Gibbs thermal corrections or combine them with supplied higher-level electronic energies.
---

# Gaussian stationary points and Gibbs energies

## Environment and inputs

Use **Gaussian 16 Rev. C.02, Linux x86_64 AVX2 binary**, on a platform listed in the [official platform table](https://gaussian.com/g16/g16_plat.pdf). Obtain licensed software through [Gaussian orders](https://gaussian.com/orders/) and follow the [official installation instructions](https://gaussian.com/techsupport/#install). Start in a configured Gaussian environment where `g16` resolves, with writable working and scratch storage and sufficient allocated memory/CPUs. The example below uses a single node; cluster submission and scratch configuration follow the site's Gaussian setup.

Supply these before choosing an input deck:

| Input | Required meaning |
|---|---|
| Molecular specification | Atom identities and coordinates, total charge, and spin multiplicity; a plausible starting structure or transition-state guess |
| Model chemistry | Method, basis/ECP assignments, solvent, and other electronic-structure settings selected for the task |
| Thermochemistry conditions | Temperature, pressure, isotopes, and frequency scaling; Gaussian defaults are 298.15 K, 1 atm, most abundant isotopes, and unscaled frequencies |
| Optional higher-level energy | Electronic energy at the exact optimized geometry and matching species/electronic state, with its method and units recorded |

Keep optimization and frequency model chemistry consistent. A frequency calculation at a geometry optimized with a different method/basis does not validate that geometry as a stationary point of the frequency calculation's potential surface. Reaction-path proposals, conformer coverage, and scientific selection of basis/ECP/solvent are supplied preparation.

## Optimize and calculate frequencies

Create a separate working directory and distinct checkpoint/log names for each structure. This complete minimum-search example adapts coordinates from Gaussian's optimization documentation; its HF/6-31G(d) model and resource values illustrate the interface and are not universal accuracy settings. Save as `structure.com`, including the blank line after the coordinates:

```text
%NProcShared=4
%Mem=5GB
%chk=structure.chk
# HF/6-31G(d) Opt Freq Temperature=298.15 Pressure=1.0

Illustrative minimum search

0 1
C   0.000   0.000   0.000
C   0.000   0.000   1.505
O   1.047   0.000  -0.651
H  -1.000  -0.006  -0.484
H  -0.735   0.755   1.898
H  -0.295  -1.024   1.866
O   1.242   0.364   2.065
H   1.938  -0.001   1.499

```

Coordinates here are in angstroms; `0 1` means neutral singlet. For the actual system, substitute its complete prepared molecular specification and model chemistry, retaining any required basis/ECP or solvent input sections. Match `%NProcShared` and `%Mem` to allocated resources. `Opt Freq` runs the optimization followed by frequencies at the optimized geometry.

From that working directory, run in a Linux shell:

```bash
g16 < structure.com > structure.log
```

The log captures textual results; `%chk` retains `structure.chk` for subsequent Gaussian work. Shell `>` replaces an existing log, so use distinct names for subsequent attempts.

### Supplied transition-state guess

Replace `Opt` with `Opt=(TS,CalcFC)`, keep `Freq`, and use the prepared transition-state coordinates and correct charge/multiplicity. `TS` changes the optimization goal; `CalcFC` computes the initial force constants at the chosen method. This is a local transition-state search from a supplied guess, not automatic reaction discovery. Keep the selected model chemistry and thermochemistry conditions consistent with the other structures being compared.

## Inspect before using the energy

Use the final optimized structure and completed frequency section in `structure.log`:

1. Confirm optimization reports `Optimization completed.` / `Stationary point found.` and inspect its force/displacement convergence results. A partially written log or failed optimization is not a thermochemistry result.
2. Inspect every `Frequencies --` group and its normal-coordinate vectors. Gaussian represents imaginary modes with negative frequency values; harmonic frequencies are reported in cm^-1. A minimum should have no imaginary vibrational modes; a first-order transition state should have exactly one. For the latter, inspect the mode's atom displacements to verify the intended bond changes. One imaginary mode alone does not establish reaction connectivity.
3. If the mode count is wrong, revisit the geometry/search rather than accepting the structure's energy as the requested stationary-point type. Very soft modes merit checking convergence and, for DFT, integration-grid adequacy; do not discard them by an arbitrary frequency cutoff.

The [Opt reference](https://gaussian.com/opt/) documents optimization controls and convergence output; the [Freq reference](https://gaussian.com/freq/) documents normal modes and thermochemistry. Preserve both the log and checkpoint, including unsuccessful attempts when diagnosing a search.

## Read and combine Gibbs energies

Locate the thermochemistry block associated with the final frequency calculation:

| Gaussian output label | Use |
|---|---|
| `Thermal correction to Gibbs Free Energy` | Additive correction, including zero-point contribution; reported in Hartree per particle |
| `Sum of electronic and thermal Free Energies` | Gibbs estimate already combining that calculation's electronic energy and thermal correction |
| `Zero-point correction` | A component already included in the Gibbs thermal correction; do not add it again |

For a single-level calculation, use the reported `Sum of electronic and thermal Free Energies` directly. For a supplied higher-level single-point electronic energy at the same optimized geometry, construct:

```text
G_composite = E_electronic_high + thermal_correction_to_G_low
```

Keep both terms in Hartree. Do not add the lower-level Gibbs total to the higher-level energy. Record the electronic-energy source separately from the correction source so geometry, charge, multiplicity, and calculation levels remain traceable. Higher-level job preparation and execution are an external handoff here.

For comparisons, form product-minus-reactant sums with the reaction's stoichiometric coefficients; a barrier uses the transition-state value minus its specified reactant reference. Use consistent thermochemistry conditions and reference states across those sums. Solvent treatment in the electronic calculation does not itself turn Gaussian's default ideal-gas thermal terms into a solution standard-state correction.

Return a compact record for each structure: optimized geometry, convergence status, imaginary-mode count and assignment, temperature/pressure, Gibbs correction, reported Gibbs total, and optional composite Gibbs value with units and source log paths. Label failed or unclassified structures explicitly instead of reporting a validated minimum or transition state.

Gaussian's default thermochemistry uses harmonic vibrations and ideal-gas statistical mechanics. Very low-frequency internal rotations can materially affect entropy; the resulting Gibbs estimate is not a measured solution free energy. If rotor or standard-state corrections are required, they need an explicitly selected, separately supported treatment.
