---
name: gaussian-calculate-solution-reaction-energy-profiles
description: Refine prepared minima or transition-state guesses with Gaussian M06-2X/SMD water calculations and assemble reaction or activation energies with consistent thermal corrections and reference states.
---

# Calculate solution-phase DFT reaction energy profiles

Use Gaussian 16 Rev. C.02 to optimize supplied structures, characterize them by frequencies, and combine larger-basis single-point energies with lower-level thermal corrections. Choose minimum mode for reactants, intermediates and products; for a supplied transition-state guess, read [Transition-state mode](references/transition-states.md) before preparing its optimization.

This workflow needs chemically prepared structures and species correspondence. Molecular construction, protonation selection, mechanism discovery, conformer searching and homodesmotic reaction design are external preparation. Results cover the supplied structures; selecting one conformer does not establish an ensemble free energy or the lowest accessible barrier.

## Environment and declared inputs

Use a licensed Gaussian 16 C.02 Linux AVX2 binary on a platform in the [official platform list](https://gaussian.com/g16/g16_plat.pdf), such as Red Hat Enterprise Linux 8.3. Obtain software through [Gaussian orders](https://gaussian.com/orders/) or the licensed site administrator; follow the [official installation and support entry](https://gaussian.com/techsupport#install) and [running instructions](https://gaussian.com/running/). The examples use a single host with shared-memory CPUs; distributed Linda execution is outside these examples.

Supply:

| Input | Required meaning |
| --- | --- |
| Geometry per species/conformer | Element symbols and Cartesian x, y, z in angstroms; all atoms included. An XYZ file must lose its atom-count and comment lines when inserted into a Gaussian molecule section. |
| Charge and multiplicity | Signed integer net charge and positive spin multiplicity for each structure; do not infer them from coordinates. |
| Species ledger | Unique ID, role (minimum or TS guess), conformer ID and correspondence to the balanced reaction and each barrier reference. |
| Thermodynamic convention | Temperature, frequency pressure, standard state, energy type (electronic, ZPE-corrected, enthalpy or Gibbs), and any explicitly supplied correction scheme. State whether a barrier is relative to separated reactants or a preassociated complex. |

The normal example uses 298.0 K, unscaled Gaussian harmonic thermochemistry at 1 atm, and SMD water at both electronic levels. SMD does not convert ideal-gas translational thermochemistry into a 1 M solution standard state. If the requested convention requires additional standard-state or low-frequency corrections, obtain their definitions and per-species terms before reporting that convention; record them separately and apply consistently. Do not silently call raw Gaussian free energies 1 M values.

## Prepare and characterize each structure

On the licensed Linux calculation host, initialize a Bourne-compatible shell. Replace these paths with existing site-approved locations; scratch must be writable and have sufficient capacity. Run in a persistent species/conformer directory so relative checkpoint names remain unambiguous.

```sh
export g16root=/licensed/software
. "$g16root/g16/bsd/g16.profile"
export GAUSS_SCRDIR=/scratch/user/job001
cd /work/profile/reactant_A/conf01
```

For minimum mode, save the following as `optfreq.gjf`. This is a complete illustrative methanethiolate input, not a published geometry. Replace the title, charge/multiplicity and all coordinate lines with the supplied species. Match `%Mem` and `%NProcShared` to allocated resources; their example values are not scientific requirements. Keep blank lines separating the route, title and molecule sections, including a blank line after the coordinates.

```text
%Mem=8GB
%NProcShared=4
%Chk=optfreq.chk
#p M062X/6-31G(d) Opt Freq SCRF=(SMD,Solvent=Water) Temperature=298.0 Pressure=1.0 Units=Ang

Methanethiolate illustrative minimum guess

-1 1
S   0.000   0.000   0.000
C   1.820   0.000   0.000
H   2.180   1.030   0.000
H   2.180  -0.515   0.892
H   2.180  -0.515  -0.892

```

```sh
g16 < optfreq.gjf > optfreq.log
```

Inspect `optfreq.log` for completed optimization, its final convergence table, frequency analysis and normal termination. A normally terminated frequency calculation alone does not establish successful optimization. Confirm the optimized species still has the intended composition, charge, spin and chemical identity. For an accepted minimum, the projected vibrational `Frequencies --` entries should have no imaginary frequencies (printed as negative numbers). The separate `Low frequencies ---` diagnostic includes translations and rotations; do not count those as vibrational instabilities.

Investigate unexpected negative modes or inconsistent low-frequency diagnostics before using thermal corrections. Inspect their displacement vectors; if convergence is inadequate, rerun optimization and frequencies consistently with tighter criteria, e.g. `Opt=Tight`, keeping the same method, basis and solvent. Gaussian 16 already uses an UltraFine DFT grid by default. Do not delete negative modes or impose an arbitrary numerical cutoff to force acceptance. Low-frequency internal rotations can also make harmonic entropy unreliable even for a converged minimum; unresolved cases must remain identified in the result.

## Carry accepted geometry into the larger basis

Only after accepting the optimization/frequency result, save `singlepoint.gjf` in the same directory:

```text
%Mem=8GB
%NProcShared=4
%OldChk=optfreq.chk
%Chk=singlepoint.chk
#p M062X/6-311+G(d,p) SP SCRF=(SMD,Solvent=Water) Geom=AllCheck

```

`%OldChk` copies the accepted checkpoint into a distinct new checkpoint. `Geom=AllCheck` reads its geometry, title, charge and multiplicity, so do not append a title or molecule section. The explicit route selects the new basis and preserves SMD water. This is a single point, with no reoptimization or new thermal correction. Keep the original frequency checkpoint and log intact.

```sh
g16 < singlepoint.gjf > singlepoint.log
```

Require normal termination and a converged final SCF energy at the intended larger-basis route. Record its `SCF Done` energy in hartree as `E_SP`. For the ordinary ground-state SMD route above, the reported energy includes the SMD non-electrostatic contribution; do not add the separately printed `SMD-CDS` term again or add a second solvation correction. If calculation settings or electronic state change, re-evaluate this workflow rather than borrowing energies from a different job.

## Assemble the energy ledger and profile

For each accepted species, retain inputs, both logs, both checkpoints and an accessible export of the optimized geometry (the final coordinate table in the log is in angstroms; retain its element/atomic-number mapping). Record the Gaussian revision, both routes, temperature, pressure, mode classification, conformer ID and any unresolved thermochemical limitations.

Extract these fields from that species' accepted `optfreq.log`; all corrections are in hartree per particle:

| Symbol | Gaussian output field |
| --- | --- |
| `ZPE` | `Zero-point correction` |
| `C_E` | `Thermal correction to Energy` |
| `C_H` | `Thermal correction to Enthalpy` |
| `C_G` | `Thermal correction to Gibbs Free Energy` |

Form `E_ZPE = E_SP + ZPE`, `U = E_SP + C_E`, `H = E_SP + C_H`, or `G_raw = E_SP + C_G`, according to the requested energy type. Thermal corrections already include ZPE. The log's `Sum of electronic and thermal Free Energies` contains the lower-level electronic energy; do not add that whole sum to `E_SP`. Each correction must come from the same accepted geometry/species as its single point.

A practical CSV ledger can use these columns, with paths relative to the profile directory:

```text
species_id,conformer_id,role,charge,multiplicity,optfreq_log,sp_log,E_SP_Eh,C_G_Eh,extra_G_Eh,G_final_Eh,imaginary_mode_count,connectivity_status
```

For Gibbs profiles, use `G_final = E_SP + C_G + extra_G`. Set `extra_G=0` only for the explicitly chosen raw convention; otherwise use the declared per-species correction and record its source, units and definition alongside the ledger. The column layout is bookkeeping glue, not Gaussian output.

Compute balanced differences in hartree, then multiply by 627.5095 for kcal/mol. Use products-positive stoichiometric coefficients: `delta_r G = sum(nu_i * G_final_i)`. For a supplied mapping `A + B -> P` through `TS`, the complete accounting is:

```text
G_reference = G_A + G_B
delta_r_G = G_P - G_reference
delta_forward_G_dagger = G_TS - G_reference
delta_reverse_G_dagger = G_TS - G_P
```

Every species named here needs its own accepted calculation chain. Include additional reactants/products and their coefficients when required to balance atoms and charge. A complex-relative barrier instead uses `G_TS - G_complex`; identify that reference explicitly. For a multistep profile, keep the same total composition at every plotted level, including spectator or separated species where necessary. Apply the same sums to H or electronic energy when those are requested; label their meaning accurately.

Deliver the species ledger and a relative-energy table identifying every level's composition, reference, units and thermodynamic convention. Include optimized geometry locations, characterization status and TS connectivity status. Failed or uncharacterized species leave a missing level/barrier; an incomplete calculation is not a zero energy. A saddle with unverified connectivity can be reported as a characterized saddle energy, but does not establish the assigned mechanistic activation barrier. Report conformer coverage and low-frequency limitations with the affected comparisons; computed energies are model estimates, not measured rates.