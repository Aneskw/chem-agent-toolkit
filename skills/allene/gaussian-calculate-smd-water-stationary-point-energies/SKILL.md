---
name: gaussian-calculate-smd-water-stationary-point-energies
description: Use Gaussian 16 to optimize supplied minima or transition-state guesses in SMD water, calculate harmonic thermochemistry at 298 K, and obtain higher-basis single-point energies.
---

# Solution-phase stationary-point energies with Gaussian 16

Use chemically prepared geometries with known charge and spin multiplicity. This workflow produces stationary-point geometries, normal modes, thermal corrections and solution-phase single-point energies. It requires a suitable starting guess for each transition state; it does not discover mechanisms or establish pathway connectivity.

## Prepare the environment and inputs

Use **Gaussian 16 Rev. C.02** on a supported Linux system. Obtain licensed access through [Gaussian](https://gaussian.com/prices/) or a licensed computing center; follow the vendor's [installation instructions](https://gaussian.com/techsupport/#install) and [platform requirements](https://gaussian.com/g16/g16_plat.pdf). The x86_64 C.02 binary requires AVX2. A configured CPU installation is sufficient.

A concrete hosted option is [OSC Gaussian](https://www.osc.edu/resources/available_software/software_list/gaussian), which requires account/access validation. On OSC Pitzer, inside a compute allocation, initialize it with:

```bash
module load gaussian/g16c02
```

Elsewhere, use that site's C.02 environment setup and scheduler. Ensure `g16` resolves, scratch storage is configured and writable, and requested memory/cores fit the allocation. Use a separate working directory and unique basenames for each structure to avoid overwriting logs and checkpoints. If the site runs jobs in temporary storage, copy logs and checkpoints back before that storage is removed.

Required inputs:

| Input | Meaning |
|---|---|
| Cartesian geometry | One element symbol and three coordinates in angstroms per atom, including hydrogens. Remove an XYZ file's atom-count and comment lines before inserting its coordinate rows. |
| Charge / multiplicity | Integer total charge and spin multiplicity, e.g. `0 1` for a neutral singlet; determine these for the supplied chemical state. |
| Stationary-point type | Minimum or supplied transition-state guess. Process each supplied conformer separately. |
| Resources | Available shared-memory cores and total Gaussian memory. The examples use 4 cores and 4 GB as adjustable choices. |

## Optimize and compute frequencies

Write `species-opt.com` as plain text. Replace the angle-bracket fields with the supplied values and coordinate rows; retain the blank lines, including a blank line after the coordinates.

```text
%nprocshared=4
%mem=4GB
%chk=species-opt.chk
#p M062X/6-31G(d) SCRF=(SMD,Solvent=Water) Opt Freq Temperature=298

Supplied species: minimum optimization and thermochemistry

<charge> <multiplicity>
<element> <x> <y> <z>
<remaining atom rows>

```

For a supplied transition-state guess, replace `Opt` with `Opt=(TS,CalcFC)` and change the title. `TS` requests a transition-state search; `CalcFC` computes initial force constants at the selected method. It is a supported setup choice, not a guarantee that a distant guess will converge.

Run from the directory containing the input:

```bash
g16 species-opt.com
```

This invocation writes `species-opt.log` in the working directory. Keep the `.com`, `.log` and `.chk` files together. The combined `Opt Freq` job performs frequencies after optimization with the same functional, basis and solvent, as required for meaningful stationary-point frequencies. See [Opt](https://gaussian.com/opt/) and [Freq](https://gaussian.com/freq/) for conditional options.

Before continuing:

- Confirm optimization completion (`Optimization completed.` / `Stationary point found.`), convergence information, completed frequency analysis and normal job termination. An optimization message alone does not show that the frequency step succeeded.
- Inspect the final geometry for the intended chemical state. A minimum should have no imaginary vibrational modes; a first-order transition state should have one, with displacement along the intended chemical change. Inspect the mode vectors or animate them in a Gaussian-compatible viewer. Unexpected modes or incomplete convergence need investigation before accepting thermochemistry; do not automatically discard small negative modes using an invented cutoff.
- Record frequencies from the regular `Frequencies --` table in cm^-1. The preliminary full-matrix diagnostic also includes rotations/translations; do not count those as vibrational instabilities.

## Higher-basis single point

Take the final converged Cartesian geometry from `species-opt.log` (the final orientation table associated with the optimized structure). Transfer the element symbols and coordinate columns, excluding center-number, atomic-number and atomic-type columns. Preserve every atom and the charge/multiplicity.

Write `species-sp.com` using that geometry:

```text
%nprocshared=4
%mem=4GB
%chk=species-sp.chk
#p M062X/6-311+G(d,p) SCRF=(SMD,Solvent=Water) SP

Single point on optimized species

<same charge> <same multiplicity>
<optimized element and x y z rows>

```

```bash
g16 species-sp.com
```

Retrieve `species-sp.log` and verify successful SCF convergence and normal termination. Record its final `SCF Done` energy in hartree. SMD's non-electrostatic CDS contribution is already included in the reported total; do not add the separately printed CDS term again. This second job changes the basis for the energy only; retain the lower-level geometry and frequency corrections.

## Interpret and deliver results

Extract these fields from the completed optimization/frequency log, keeping their labels:

| Field | Use |
|---|---|
| `Zero-point correction` | ZPE correction, hartree per particle |
| `Thermal correction to Energy` | Internal-energy correction, including ZPE |
| `Thermal correction to Enthalpy` | Enthalpy correction, including ZPE |
| `Thermal correction to Gibbs Free Energy` | Gibbs correction, including ZPE |
| `Sum of electronic and thermal Free Energies` | Lower-level corrected total; not a correction to add to the single point |

For a combined higher-basis Gibbs estimate, use
`G_combined = E_SP(SMD water) + thermal correction to Gibbs Free Energy(lower level)`.
Use the analogous correction for enthalpy or ZPE-corrected energy; do not add ZPE a second time. Label combined estimates separately from raw Gaussian totals. Compare consistently prepared states, accounting for all species and stoichiometric coefficients when forming reaction or activation differences.

`Temperature=298` selects 298 K explicitly; Gaussian's default is 298.15 K. With no other settings, thermochemistry uses 1 atmosphere, unscaled frequencies and the most abundant isotopes. Its statistical-mechanical analysis uses ideal-gas expressions and harmonic vibrations even with implicit solvation. SMD water does not itself convert those thermal terms to a 1 M solution standard state. Report the convention used; any requested standard-state or low-frequency correction needs an explicit separate method. Low-frequency internal rotations can materially affect entropy.

Deliver the input/log/checkpoint paths, optimized geometry, stationary-point classification and relevant mode, temperature/pressure convention, lower-level corrections, higher-basis energy and any combined estimates with units. Failed SCF, failed optimization, missing frequency/thermochemistry output or abnormal termination means there is no accepted result for that stage; report the failed stage rather than treating its last printed energy as a completed calculation.
