---
name: gaussian-assemble-two-level-free-energies
description: Use Gaussian 16 to optimize supplied molecular models, validate minima or transition structures with harmonic frequencies, and compare composite free energies using higher-basis single-point energies.
---

# Gaussian stationary points and composite free energies

Use a lower-basis optimization and frequency calculation to obtain a validated structure and thermal correction, then evaluate a larger-basis electronic energy at that same geometry. Inputs are supplied molecular models with known charge and spin multiplicity. This workflow covers gas-phase molecules and explicitly included molecular complexes; it does not add continuum solvation or establish reaction-path connectivity.

## Environment and inputs

Use **Gaussian 16 Rev. C.02, AVX2 Linux binary**, on a compatible platform listed in the [official platform matrix](https://gaussian.com/g16/g16_plat.pdf). Obtain licensed software through [Gaussian orders](https://gaussian.com/orders/) and follow the [official installation entrypoint](https://gaussian.com/techsupport/#install). The commands below use a Bourne-compatible shell on the calculation host.

If the site has not already configured Gaussian, adapt this [documented execution setup](https://gaussian.com/running/):

```sh
export g16root=/path/to/parent-of-g16
. "$g16root/g16/bsd/g16.profile"
export GAUSS_SCRDIR=/path/to/existing/writable/scratch
```

Work in a directory with unique filenames for each species and enough disk space for scratch/checkpoint files. Choose memory and shared processors within the host allocation.

| Input | Required preparation |
|---|---|
| Geometry | All atoms, including any explicit ligands/solvent, in angstroms; preserve the intended chemical model |
| Electronic state | Total charge and positive spin multiplicity, such as `0 1` for a neutral singlet |
| Optimization/frequency model | Selected method, basis for every element, any ECPs, and numerical settings, kept identical for optimization and frequencies |
| Single-point model | Selected higher-level method and basis/ECP assignments with coverage for every atom, evaluated at the accepted lower-level geometry |
| Stationary-point goal | A minimum guess, or a chemically informed transition-state guess |
| Comparison | Species identities, stoichiometric coefficients, reference state and common temperature/pressure |

## Optimize and validate

The following `model.gjf` is a small illustrative water input. Replace its geometry, title, charge/multiplicity and route with the supplied system and optimization/frequency model. B3LYP/6-31G** and the later B3LYP/6-311G** step illustrate this water calculation; they are not defaults for arbitrary molecular complexes. Check basis coverage before adapting them. A metal-containing system may require explicit mixed basis/ECP sections through `Gen`/`GenECP`; provide the complete selected assignments at each level (see the [Gaussian basis reference](https://www.conflex.co.jp/gaussian_support/basissets.php)). Resource choices are examples. Preserve blank lines between route, title and molecular specification, and terminate the geometry with a blank line.

```text
%Mem=2GB
%NProcShared=2
%Chk=model.chk
# B3LYP/6-31G** Opt Freq Temperature=298.15 Pressure=1.0

Water minimum example

0 1
O   0.000000   0.000000   0.000000
H   0.000000   0.000000   0.960000
H   0.929422   0.000000  -0.240365

```

```sh
g16 < model.gjf > model.log
```

`Opt Freq` first optimizes and then calculates frequencies at the optimized geometry using the same method and basis. Keep this pairing: frequencies at a geometry optimized with a different model chemistry are not a valid stationary-point analysis. Temperature is in kelvin and pressure in atmospheres. Defaults are 298.15 K, 1 atmosphere, unscaled frequencies and the most abundant isotopes; the example makes temperature and pressure explicit.

For a supplied transition-state guess, replace `Opt` with `Opt=(TS,CalcFC)` and retain `Freq`. `TS` seeks a saddle point; `CalcFC` computes force constants at the first point. This alternative needs a suitable guess and does not identify the intended reaction automatically.
Before accepting the thermal correction, inspect `model.log`:

- Require `Optimization completed.` and `Stationary point found.` for the optimization, followed by the completed frequency analysis. An interrupted job or unconverged optimization is incomplete even if some energies were printed.
- Inspect the vibrational frequencies; imaginary modes are reported as negative frequencies. Zero imaginary modes supports a local minimum. One supports a first-order saddle point; inspect that mode's displacement to check the intended motion. Additional imaginary modes require resolving the structure before using it as the intended minimum or transition structure. Do not discard small negative modes automatically.
- Record `Thermal correction to Gibbs Free Energy`, temperature and pressure. This correction already includes zero-point energy. A printed thermochemistry table alone does not validate the geometry.

## Higher-basis energy at the optimized geometry

Make `sp.gjf` from the preceding input with these edits:

| Part | Replacement |
|---|---|
| Checkpoint | `%Chk=sp.chk`, to retain the optimization checkpoint separately |
| Route | Supplied single-point method/basis/ECP; `# B3LYP/6-311G**` for the water illustration only. Remove `Opt Freq` and include any required additional basis/ECP sections. |
| Title | A unique single-point job title |
| Molecular specification | Same charge/multiplicity, followed by the **converged optimized coordinates** from `model.log`, as `element x y z` in angstroms |

Use the final optimized structure, not the original guess. If the output coordinate table uses atomic numbers, map them to element symbols and omit its column headings, center numbers and atom-type columns. Keep every atom, including explicit ligands/solvent. Retain the input's section-separating blank lines and final blank line.

```sh
g16 < sp.gjf > sp.log
```

This input performs an electronic single-point calculation, without changing the geometry or repeating frequencies. Read its converged electronic energy in Hartree from `sp.log`. A failed SCF calculation supplies no accepted single-point result. Do not run higher-basis frequencies on the lower-basis geometry to obtain a replacement thermal correction.

## Combine and compare

Repeat the paired jobs for each supplied species. Record a compact table containing species identity, both calculation levels and basis/ECP assignments, charge/multiplicity, imaginary-mode count, temperature/pressure, lower-level correction, higher-level electronic energy and geometry/log paths.

For each validated structure, calculate:

```text
G_composite [Hartree] = E_single_point [Hartree] + Gcorr_opt_freq [Hartree]
Delta_G = sum(stoichiometric_coefficient * G_composite)_products
        - sum(stoichiometric_coefficient * G_composite)_reactants
Delta_G [kcal/mol] = Delta_G [Hartree] * 627.5095
```

For a barrier, replace the product sum with the transition structure and use the declared reactant reference. Account for every molecule: comparing aggregates with different numbers of atoms requires a balanced reaction including associated/free ligands or solvent molecules. Use consistent computational settings, temperature and pressure across the comparison.

Add the correction once. Do not add a lower-basis `Sum of electronic and thermal Free Energies` to a higher-basis electronic energy, and do not add zero-point energy separately. The larger-basis energy and smaller-basis correction must belong to the same optimized structure and electronic state.

The result is a model free-energy estimate with ideal-gas, harmonic thermochemistry at the stated pressure. It does not establish a solution standard state, a global minimum, a measured barrier or transition-state connectivity. Very low vibrational modes and internal rotations can materially affect entropy; retain relevant warnings with the result rather than interpreting the harmonic correction as exact.

For option details, consult [Opt](https://gaussian.com/opt/), [Freq](https://gaussian.com/freq/) and the [official thermochemistry explanation](https://gaussian.com/wp-content/uploads/dl/thermo.pdf), especially sections 3.1 and 4.1.
