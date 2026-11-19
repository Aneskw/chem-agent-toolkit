---
name: gaussian-compare-harmonic-reaction-free-energies
description: Use Gaussian 16 to optimize supplied reaction-path structures, check stationary points, and compare consistent Gibbs free energies and activation barriers.
---

# Reaction free energies with Gaussian 16

Use this workflow with prepared reactant, intermediate, product and transition-state guesses. It provides local optimizations and harmonic thermochemistry; the supplied structures and reaction stoichiometry determine which mechanism and conformers are examined.

## Environment and inputs

Use **Gaussian 16 Rev. C.02** with a valid license. Obtain it through [Gaussian orders](https://gaussian.com/orders/) and use the vendor's [installation entry](https://gaussian.com/techsupport/#install). The example uses the UNIX command line on an AVX2 Linux installation; check the [vendor platform table](https://gaussian.com/g16/g16_plat.pdf) for supported OS/build combinations.

Follow [Running Gaussian](https://gaussian.com/running/) to set `g16root` to the directory containing `g16`, source `$g16root/g16/bsd/g16.profile` in a Bourne-compatible shell, and set `GAUSS_SCRDIR` to writable scratch storage. Confirm the program banner identifies C.02. Use allocated compute resources; the example requests four shared-memory CPU cores and 4 GB of Gaussian memory.

Prepare these inputs before submission:

| Input | Required content |
|---|---|
| `reactant.mol`, `product.mol`, `ts.mol` | Gaussian molecular specifications: charge and spin multiplicity on the first line, then element and Cartesian x/y/z coordinates in angstroms, terminated by a blank line. No XYZ atom-count/comment header. |
| Additional species | Separate molecular specifications for any other intermediates, conformers or free reagents needed by the balanced comparison. |
| Reaction accounting | Define the reactant reference, product side, transition complex, and any spectator/free species explicitly. Preserve total atoms and charge across each comparison. |

The `.mol` suffix here is a local naming convention for plain Gaussian input fragments, **not an MDL Molfile**. Each fragment represents the complete calculated molecule or complex, including any explicitly modeled additives. For example, this is the format of a neutral singlet water fragment, not a proposed reaction structure:

```text
0 1
O  0.000000  0.000000  0.000000
H  0.000000  0.000000  0.960000
H  0.929421  0.000000 -0.240365

```

Choose one method, basis, solvation model, temperature and pressure for the comparison. The templates below use PBE-D3BJ/6-31G(d), SMD dichloromethane, 318.15 K and 1 atm. For a different study, change these consistently in every job. Do not mix frequencies with a geometry optimized at a different model chemistry. Gaussian 16's default general DFT integration grid is UltraFine.

## Optimize and calculate frequencies

Work in a fresh calculation directory containing the molecular fragments. Save this as `reactant.gjf`, retaining the blank lines:

```text
%NProcShared=4
%Mem=4GB
%Chk=reactant.chk
#p PBEPBE/6-31G(d) EmpiricalDispersion=GD3BJ Opt Freq
   SCRF=(SMD,Solvent=Dichloromethane) Temperature=318.15 Pressure=1.0

Reactant minimum and thermochemistry

@reactant.mol

```

The native `@` directive includes the supplied fragment. To prepare `product.gjf`, copy this template and change the title, checkpoint to `product.chk`, and included fragment to `@product.mol`. Use distinct filenames for each additional species.

For the supplied transition-state guess, save `ts.gjf`:

```text
%NProcShared=4
%Mem=4GB
%Chk=ts.chk
#p PBEPBE/6-31G(d) EmpiricalDispersion=GD3BJ Opt=(TS,CalcFC) Freq
   SCRF=(SMD,Solvent=Dichloromethane) Temperature=318.15 Pressure=1.0

Transition-state optimization and thermochemistry

@ts.mol

```

`TS` requests a saddle-point optimization and `CalcFC` computes the initial force constants. This needs a suitable TS guess; it does not search all possible reaction pathways. Combined `Opt Freq` performs the frequency calculation at the optimized structure.

Submit each job through the site's compute allocation, using these commands within the calculation directory:

```bash
g16 < reactant.gjf > reactant.log
g16 < product.gjf > product.log
g16 < ts.gjf > ts.log
```

These commands write logs in the working directory; `%Chk` preserves named checkpoint files there. Reusing names can overwrite previous results. Keep the original input fragments, job files, logs and checkpoints together.

## Accept structures before comparing energies

Inspect the complete log, not just the final energy-like number.

| Check | Interpretation and next action |
|---|---|
| Optimization | Require `Optimization completed.` / `Stationary point found.` and inspect the force/displacement convergence table. A failed SCF or exhausted optimization is not an accepted stationary point. |
| Minimum | Inspect the vibrational `Frequencies --` lines and normal modes. A minimum should have no imaginary vibrational modes. |
| Transition state | Require one imaginary vibrational mode, printed as a negative frequency, and inspect its displacement vector for the intended reaction motion. A single imaginary mode alone does not identify which reactant and product are connected. |
| Numerical/soft modes | Examine small negative frequencies and the low-frequency/translation-rotation diagnostics rather than deleting modes or applying an arbitrary cutoff. Refine the structure or numerical settings if convergence is inadequate. |
| Thermochemistry | Require a completed frequency analysis with the requested temperature/pressure and the corrected free-energy line below. Missing output is a failed/incomplete result, not zero free energy. |

If a TS connects uncertain endpoints, [Gaussian IRC](https://gaussian.com/irc/) provides a separate connectivity check starting from a characterized TS. Keep that validation distinct from merely finding a saddle point.

## Read and compare Gibbs free energies

For each accepted species, read this field from the **final frequency analysis** in its log:

```text
Sum of electronic and thermal Free Energies=
```

Its value is in Hartree per particle and already combines electronic energy with the thermal Gibbs correction. Do not add `Thermal correction to Gibbs Free Energy` again, and do not substitute `SCF Done` for this value.

Build a results table with species identifier, composition/charge, minimum-or-TS status, imaginary-mode assessment, temperature/pressure, free energy in Hartree and log/checkpoint paths. Keep rejected calculations outside the accepted energy comparison.

For a balanced reaction with stoichiometric coefficients:

```text
DeltaG_rxn (kcal/mol) =
    [sum(n_product * G_product) - sum(n_reactant * G_reactant)] * 627.5095

DeltaG_forward_barrier (kcal/mol) =
    [G_transition_state_side - G_reactant_reference_side] * 627.5095
```

For a simple same-composition sequence R -> TS -> P, the second expression is `(G_TS - G_R) * 627.5095`. If the TS contains several combined reagents, use the corresponding sum of separate reactant free energies or the explicitly defined prereaction complex. Include free/additional species as required to balance both sides. Compare additives through balanced reference states; directly subtracting differently composed complexes does not isolate an additive's effect.

Report the reference state beside every barrier. A negative energy relative to separated reagents does not by itself describe the barrier from a lower-energy preceding intermediate.

Gaussian's default thermochemical analysis uses ideal-gas statistical mechanics and harmonic vibrations. SMD adds solvent modeling but does not automatically turn this into 1 M solution thermochemistry. Very low-frequency modes and hindered rotations can materially affect entropy. Report these assumptions and any separately justified corrections; do not silently introduce a correction or frequency cutoff.

Retain the accepted structures and energy table as the result. These are predictions for the supplied structures and chosen model; local optimization does not establish exhaustive conformer sampling or experimental selectivity. For detailed output interpretation, consult the [Freq reference](https://gaussian.com/freq/); use the [Opt reference](https://gaussian.com/opt/) when revising optimization settings.
