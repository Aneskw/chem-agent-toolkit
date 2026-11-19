---
name: gaussian-compare-irc-validated-reaction-pathways
description: Use Gaussian 16 to optimize supplied intermediates and transition-state guesses, check vibrational character and IRC connectivity, and compare competing reaction pathways using consistent harmonic free energies.
---

# Validate and compare proposed reaction pathways

Start from proposed structures and a chosen computational model. This workflow characterizes those proposals; it does not generate a mechanism or sample a conformational ensemble.

## Environment and inputs

Use a licensed **Gaussian 16 Rev. C.02** installation on a compatible Linux AVX2 system. Obtain the software through [Gaussian](https://gaussian.com/pricing/) and follow its [installation instructions](https://gaussian.com/techsupport#install); check the [official platform matrix](https://gaussian.com/g16/g16_plat.pdf) for the installation's OS and hardware requirements. Use the site's configured Gaussian environment and writable scratch directory. The commands below assume that `g16` resolves to C.02 in a Bash shell on an allocated compute node.

Prepare these inputs before constructing jobs:

| Input | Required content |
| --- | --- |
| Proposed species | Cartesian element/x/y/z rows in angstroms, charge, and spin multiplicity for each intermediate and transition-state guess |
| Reaction definition | Which structures each proposed transition state should connect; the chemical step and reference state for each barrier |
| Computational model | Functional, basis, solvent settings if applicable, and any additional model input sections |
| Thermochemistry | Common temperature, pressure, isotope choices, and frequency scaling across comparisons |
| Resources | Memory and shared CPU count within the compute allocation |

Keep atom labels/order consistent when transferring a geometry. Use a separate job basename and checkpoint for each species and calculation stage. Run from a dedicated working directory; filenames below are relative to it. Shell `>` replaces an existing log of the same name.

## Optimize and calculate frequencies

The following is an adaptable input template for `ts-a.com`. Replace every angle-bracket field with supplied molecular data. The two resource settings and B3LYP/cc-pVDZ gas-phase model are illustrative; replace them with the chosen resources and model, adding its required solvent/options and extra input sections consistently to every job. Retain the blank separators and a final blank line.

```text
%NProcShared=4
%Mem=5GB
%Chk=ts-a.chk
# B3LYP/cc-pVDZ Opt=(TS,CalcFC) Freq Temperature=298.15 Pressure=1.0

Path A transition-state guess

<charge> <multiplicity>
<element x y z rows for the supplied TS guess>

```

For `reactant.com` and any other intended minimum, use the same layout and model, a unique `%Chk`, and `Opt Freq` instead of `Opt=(TS,CalcFC) Freq`. Make `ts-b.com` from the second supplied TS guess in the same way as `ts-a.com`. `TS` requests a saddle-point optimization; `CalcFC` computes the initial force constants. A suitable starting guess is still necessary.

```bash
g16 < reactant.com > reactant.log
g16 < ts-a.com > ts-a.log
g16 < ts-b.com > ts-b.log
```

`Opt Freq` performs the frequency analysis after optimization with the same model. Do not calculate frequencies using a different method or basis from that used to optimize the geometry. Keep final geometries, logs, and checkpoints. See the [Opt](https://gaussian.com/opt/) and [Freq](https://gaussian.com/freq/) interfaces for alternative optimization inputs or calculation availability.

## Accept structures before comparing energies

Read optimization convergence and the final frequency block in each log, not just the presence of a log file.

- A minimum should have no imaginary vibrational modes. Gaussian reports imaginary frequencies as negative values.
- A first-order transition structure should have one imaginary mode. Inspect its Cartesian displacement vectors in the normal-mode output: they must describe the proposed bond-making, bond-breaking, or proton-transfer motion.
- Multiple imaginary modes, a mode unrelated to the proposed step, or an unconverged optimization leave the assignment unresolved. Do not use that structure as the claimed barrier. For suspected convergence artifacts, refine the optimization; `Opt=Tight` with `Int=UltraFine` is a documented option, followed by a matching-model frequency analysis.

A suitable mode is necessary but does not establish which minima the transition structure connects.

## Follow each transition structure to its endpoints

After accepting `ts-a`, copy its **optimized** Cartesian coordinates from the optimization output into `ts-a-irc.com`. Preserve charge, multiplicity, atom order, and the computational model. Use this template with those external coordinates:

```text
%NProcShared=4
%Mem=5GB
%Chk=ts-a-irc.chk
# B3LYP/cc-pVDZ IRC=(CalcFC,Report=Cartesians,MaxPoints=30)

Path A connectivity check

<charge> <multiplicity>
<element x y z rows from the optimized TS>

```

```bash
g16 < ts-a-irc.com > ts-a-irc.log
g16 < ts-b-irc.com > ts-b-irc.log
```

Prepare `ts-b-irc.com` analogously from `ts-b`. `CalcFC` recomputes the starting Hessian, so this path does not require a checkpoint transfer. `Report=Cartesians` requests coordinates for inspecting and transferring path structures; the default report contains only energies and reaction coordinates. Both directions are followed unless `Forward` or `Reverse` is specified. Direction labels are defined by the transition vector, not by chemical reactant/product identity.

`MaxPoints=30` is an illustrative per-direction limit; the default is 10. Inspect the `Summary of reaction path following` and Cartesian coordinates on **both** branches. These relative electronic energies are referenced to the TS, not thermal free energies. Identify the connected chemical structures from their geometries. Reaching a point limit alone does not establish an endpoint: extend an insufficient path using the documented IRC controls rather than assign connectivity from an unfinished trace. See [IRC options and output](https://gaussian.com/irc/).

Read the units on the Cartesian report and express coordinates in angstroms for the new input. Transfer each branch's terminal geometry into a separately named minimum `Opt Freq` input and run it as above. Check the optimized endpoint identities and vibrational character. Use those converged minima for endpoint thermochemistry, not arbitrary points along the IRC.

## Compare consistent thermochemistry

Collect, for every accepted minimum and TS:

| Log field/result | Meaning |
| --- | --- |
| Final geometry and convergence | The stationary structure actually found |
| `Frequencies --` and normal modes | Vibrational character; frequencies are in cm⁻¹ |
| `Thermal correction to Gibbs Free Energy` | Correction including zero-point energy |
| `Sum of electronic and thermal Free Energies` | Electronic energy plus that correction, in Hartree |

At a common model and thermochemical convention, calculate each barrier as `G(TS) - G(reactant reference)` and reaction free energy as `G(product) - G(reactant reference)`. For branches from the same reference state, compare the two barriers. Balance composition when a reference contains multiple molecular species; use the sum of their free energies and apply a consistent standard-state convention.

Gaussian's default thermochemistry uses 298.15 K, 1 atm, unscaled frequencies, and the most abundant isotopes. Its harmonic ideal-gas analysis can give unreliable entropy contributions for very low-frequency internal rotations; a solvent electronic-energy model does not itself change that thermochemical convention. Do not silently mix standard states or methods, or add zero-point energy again to the reported corrected total. A higher-level single-point energy must not be mistaken for this corrected total.

Report a compact table of species, model, imaginary-mode assignment, G values and units, connectivity, and barrier references. Flag incomplete jobs, unresolved modes, or unfinished IRC branches as unresolved results. A smaller calculated barrier supports a preference within the selected model; it is not a measured rate or proof that unexamined mechanisms are absent.
