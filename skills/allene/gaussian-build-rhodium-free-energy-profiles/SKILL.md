---
name: gaussian-build-rhodium-free-energy-profiles
description: Build solution-phase reaction free-energy profiles in Gaussian from prepared organorhodium intermediates and transition-state guesses, with frequency and IRC validation and consistent thermal corrections.
---

# Validated reaction energies with Gaussian

Use this workflow when structures and a proposed reaction network already exist. It combines gas-phase M06 optimization and harmonic thermochemistry with larger-basis SMD single-point calculations. Transition-state searches require a prepared guess; this workflow does not generate a mechanism or select a spin state.

## Environment and starting material

Use **Gaussian 16 Revision C.02**, licensed Linux AVX2 binaries on a platform listed in the [official platform document](https://gaussian.com/g16/g16_plat.pdf). Obtain software, installation instructions and support through [Gaussian](https://gaussian.com/) or the [CONFLEX Gaussian product/support entry](https://www.conflex.co.jp/product_gaussian.php). Load the installation's environment or site module so that `g16` resolves. The [institutional command-line guide](https://docs.icer.msu.edu/Running_Gaussian_by_Command_Lines/) illustrates execution; module names and scheduler directives are site-specific.

Provide allocated compute resources and a writable working/scratch area configured by that installation. Run on the site's permitted compute nodes. The examples request four shared-memory cores and 5 GB; adapt these to the allocation. Use unique job prefixes: shell `>` replaces an existing log, and `%chk` names a checkpoint written by the job.

| Input | Required preparation |
| --- | --- |
| Structure for every species | Complete `Element x y z` Cartesian rows in angstroms, including all hydrogens; preserve atom order when moving a structure between jobs. |
| Electronic state | Independently assigned total charge and spin multiplicity for each species. Coordinates alone do not establish these. |
| Reaction network | Labels, proposed TS connections, stoichiometry and a reference state, including free molecules or ions released/consumed. |

For an existing research example, [Supplementary Data 1](https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-024-52209-5/MediaObjects/41467_2024_52209_MOESM4_ESM.docx) contains labeled Cartesian structures. Copy the desired coordinate block into an input file; the DOCX is not a Gaussian input deck. The method and energy table are in [Supplementary Information S92-S94](https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-024-52209-5/MediaObjects/41467_2024_52209_MOESM1_ESM.pdf).

## Optimize and classify each structure

Create `min-opt.com` using the following template. Replace both angle-bracket fields with supplied input; they are not Gaussian syntax. This template covers C/H/Rh species.

```text
%nprocshared=4
%mem=5GB
%chk=min-opt.chk
#p M06/GenECP Opt Freq Integral=UltraFine 6D 7F Temperature=298.15 Pressure=1.0

Prepared minimum: gas-phase optimization and frequencies

<charge> <multiplicity>
<complete Cartesian coordinate rows>

C H 0
6-31G(d)
****
Rh 0
LANL2DZ
****

Rh 0
LANL2DZ

```

Leave a blank line after the coordinates, between basis and ECP sections, and at the end. `GenECP` reads the orbital basis and effective core potential separately: the two Rh blocks serve different purposes. For O-containing species, for example, add O to the light-element selector. List only elements actually present and assign a supported basis to every atom. For a metal-free companion molecule, use `M06/Gen` with the light-atom basis block and omit both Rh blocks. Consult the [GenECP](https://www.conflex.co.jp/gaussian_support/gen.php) and [ECP input](https://www.conflex.co.jp/gaussian_support/pseudo.php) references when changing element assignments.

The explicit `6D 7F` choice uses Cartesian d functions for the lower-level calculation; the larger-basis step below uses `5D 7F`. Keep each level's convention identical across all species. `Integral=UltraFine` makes the Gaussian 16 DFT grid explicit. These are declared implementation settings, not recovered original job settings.

Run from the directory containing the input, after the environment is loaded:

```bash
g16 < min-opt.com > min-opt.log
```

For a transition state, make `ts-opt.com` with its supplied guess and electronic state, a distinct `%chk=ts-opt.chk`, and replace `Opt` with `Opt=(TS,CalcFC)` in the same route. Keep `Freq` and the other lower-level settings. Run `g16 < ts-opt.com > ts-opt.log`.

Inspect the completed optimization and frequency output before accepting an energy:

- Check convergence and the final job termination, not just the presence of an `SCF Done` line. A partial log or SCF/optimization failure does not supply a validated stationary point.
- A minimum must have **no imaginary vibrational frequencies**. A TS must have **one**, with a displacement pattern consistent with the proposed reaction. Negative values in `Frequencies --` denote imaginary modes. Inspect the associated displacement vectors or animate the mode in GaussView if available. Extra imaginary modes or the wrong reaction motion require revisiting the structure, not silently deleting frequencies.
- Save the final optimized coordinates, frequency information, log and checkpoint under the species label. Use the final coordinates rather than the initial guess in subsequent jobs.

## Validate transition-state connectivity

Create `ts-irc.com` from the lower-level input, using the **final validated TS coordinates** and the same charge, multiplicity, basis/ECP blocks and `6D 7F` convention. Give it a distinct checkpoint and this route:

```text
#p M06/GenECP IRC=(CalcFC,MaxPoints=30,Report=Cartesians) Integral=UltraFine 6D 7F
```

```bash
g16 < ts-irc.com > ts-irc.log
```

`CalcFC` supplies the initial Hessian; the default traces both directions. `Report=Cartesians` requests path coordinates without changing the default mass-weighted path definition. `MaxPoints=30` is an illustrative limit per direction, not a scientific acceptance threshold.

Locate `Summary of reaction path following` and match each branch's terminal point to its reported Cartesian geometry. Recover **both** structures separately; the last geometry in the log is not both endpoints. Read the reported coordinate units and convert to angstroms for the new inputs, preserving elements, atom order, charge and multiplicity. Forward/reverse labels describe the transition-vector phase rather than guaranteed reactant/product identities. The summary's relative electronic energies are not a free-energy profile.

If a branch stops before its endpoint can be assigned, extend it using the [IRC documentation](https://www.conflex.co.jp/gaussian_support/irc.php). Put each terminal geometry into a separate same-level minimum `Opt Freq` deck using the preceding template and unique checkpoint/log names. Confirm convergence, no imaginary vibrational modes, and the actual chemical identity of both optimized endpoints. Accept the proposed network edge only when those identities match the intended connection; otherwise report it as unresolved or a different connection. Keep the IRC and endpoint artifacts separate from the TS thermochemistry job.

## Calculate solution single-point energies

For each validated stationary point, create a separate `species-sp.com`. Insert its **final gas-phase optimized coordinates** and unchanged electronic state:

```text
%nprocshared=4
%mem=5GB
%chk=species-sp.chk
#p M06/GenECP SCRF=(SMD,Solvent=TetraHydroFuran) Integral=UltraFine 5D 7F

SMD THF single-point energy on validated geometry

<charge> <multiplicity>
<complete final optimized Cartesian coordinate rows>

C H 0
6-311+G(d,p)
****
Rh 0
SDD
****

Rh 0
SDD

```

Adapt the element selectors as above. There is no `Opt` or `Freq` in this step: the larger basis and solvent are used for the single-point energy, while thermochemistry comes from the lower-level frequency job.

```bash
g16 < species-sp.com > species-sp.log
```

This uses the current named-THF solvent parameters; the [solvent table](https://www.conflex.co.jp/gaussian_support/scrf.php) lists dielectric constant **7.4257**. If a task requires another dielectric constant or exact historical settings, establish and document those inputs before changing the solvent model.

## Assemble and interpret the profile

Keep one row per species and retain units explicitly:

| Field | Source and meaning |
| --- | --- |
| `E_gas_low` (Hartree) | Final lower-level electronic energy; useful for auditing, not the final profile energy. |
| `Gcorr_gas` (Hartree) | `Thermal correction to Gibbs Free Energy` from the lower-level frequency log. |
| `E_SMD_high` (Hartree) | Converged `SCF Done` energy from the larger-basis SMD single-point log. |
| `G_solution` (Hartree) | `E_SMD_high + Gcorr_gas`. |
| Validation | Frequency classification and, for each TS, identified IRC endpoints. |

Gaussian's SMD total SCF energy already includes the separately printed `SMD-CDS (non-electrostatic) energy`; **do not add that term again**. The gas-phase Gibbs correction already includes zero-point contributions; do not add ZPE again or add the entire lower-level `Sum of electronic and thermal Free Energies` to the solvent energy. The [frequency output reference](https://www.conflex.co.jp/gaussian_support/freq.php) distinguishes corrections from corrected totals.

For a state containing multiple components, sum their `G_solution` values with their stoichiometric coefficients. Subtract the same balanced reference-state sum from every state. A forward barrier is the TS-state sum minus its connected reactant-state sum; reverse barriers use the connected product state. Only compare states with consistent total composition and charge. Report differences in Hartree, or convert consistently to the requested energy unit before plotting.

The example retains harmonic ideal-gas thermal corrections at 298.15 K and 1 atm, without an additional solution standard-state or low-frequency correction. Apply the same thermochemical convention to every component and report it. A solvent single-point calculation does not by itself change that thermal convention.

Deliver the labeled energy table, relative-state/barrier table, calculation settings and retained logs/checkpoints; include optimized geometries and IRC connections so the assignments can be inspected. Missing or failed calculations remain incomplete rows, not zero energies. Relative energies describe the chosen structures, electronic states and computational model; they are predictions rather than measured kinetics or proof that all competing pathways were found.
