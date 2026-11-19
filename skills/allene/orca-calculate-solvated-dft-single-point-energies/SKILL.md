---
name: orca-calculate-solvated-dft-single-point-energies
description: Calculate PW6B95-D3(BJ)/def2-TZVPP energies with SMD in ORCA from prepared molecular geometries, charge, multiplicity and solvent; use for fixed-geometry energy comparisons.
---

# Solvated DFT single points with ORCA

## Setup and inputs

Use **ORCA 6.1.1**. Obtain the platform-specific distribution through the [official release and download links](https://www.faccts.de/orca-6-1-1/): the ORCA Forum serves academic users; FACCTs provides academic and commercial downloads. Registration or an appropriate license is required. Follow the [ORCA 6.1 installation instructions](https://www.faccts.de/docs/orca/6.1/manual/contents/quickstartguide/installation.html). Keep the distribution's modules together and make its executable directory available through PATH; reopen the command window after installation. The example is a serial job, without parallel directives.

Prepare one job directory per structure with:

| Input | Required content |
| --- | --- |
| `prepared.xyz` | One supplied geometry in standard XYZ format: atom count, comment line, then element and Cartesian x/y/z per atom, in angstroms. |
| Charge | Integer net molecular charge. |
| Multiplicity | Integer `2S+1` for the intended electronic state. |
| Solvent | A supported SMD solvent name from [Table 2.56](https://www.faccts.de/docs/orca/6.1/manual/contents/essentialelements/solvationmodels.html). |

These calculations keep the supplied geometry fixed. Geometry optimization, stationary-point validation and thermal corrections must be provided separately when needed.

## Prepare and run

Create the ASCII file `job.inp` beside `prepared.xyz`:

```text
! PW6B95 def2-TZVPP D3BJ TightSCF DEFGRID3 SMD(dichloromethane)
* xyzfile 0 1 prepared.xyz

```

Here `0 1` and `dichloromethane` are example choices: substitute the actual charge, multiplicity and solvent. End the xyzfile line with an OS-appropriate newline. Unlike an inline coordinate block, this external-file directive needs no closing star.

The settings select:

| Setting | Operational meaning |
| --- | --- |
| `PW6B95`, `def2-TZVPP` | Hybrid meta-GGA functional and orbital basis. The basis covers H-Rn; def2-ECP is automatically used for Rb-Rn, including Au. |
| `D3BJ` | Atom-pair dispersion with Becke-Johnson damping. |
| `TightSCF` | The documented tight convergence preset. |
| `DEFGRID3` | Explicit higher-quality integration grids; ORCA 6.1 otherwise defaults to DEFGRID2. |
| `SMD(solvent)` | Continuum solvation with electrostatic and cavity-dispersion-solvent-structure (CDS) contributions. |

ORCA 6.1 hybrid DFT defaults to RIJCOSX with the def2/J auxiliary basis. Inspect the echoed settings, including ECP assignments for heavy atoms.

From this directory, run in a Windows command prompt or a POSIX shell:

```sh
orca job.inp > job.out 2> job.err
```

Use a fresh directory or basename for each independent job. Redirection replaces existing output logs with the same names. `orca` must resolve to the intended 6.1.1 installation; otherwise use its full executable path with shell-appropriate quoting. Main output goes to `job.out`, stderr to `job.err`, and ORCA writes auxiliary files in the working directory.

## Inspect and retain results

Accept an energy only after inspecting:

- The echoed functional, basis/ECPs, dispersion, grid, charge, multiplicity and SMD solvent.
- An explicit `SCF CONVERGED AFTER ... CYCLES` message and the convergence report.
- `ORCA TERMINATED NORMALLY` at the end of the job, with no unresolved errors.

A missing final energy, failed SCF or incomplete termination leaves the job without an accepted result. Inspect both logs and resolve the cause before reporting an energy; the presence of an energy line alone does not establish convergence. For convergence options, consult the [SCF manual](https://www.faccts.de/docs/orca/6.1/manual/contents/essentialelements/scf.html).

Read the value following `FINAL SINGLE POINT ENERGY` in `job.out`, in Hartree (Eh). Check the SMD section, including `SMD CDS free energy correction energy` and `Total Energy after SMD CDS correction`. ORCA includes CDS in its total energy and dispersion in its final single-point energy: **do not add either correction again**.

Retain `job.inp`, `prepared.xyz`, both logs and `job.gbw`. The GBW file stores geometry, basis and wavefunction information needed for supported SCF restarts or orbital reuse; it is not a replacement for the text energy record.

Report the energy with geometry identity, charge, multiplicity, solvent, ORCA version and settings. Compare compositionally balanced states calculated consistently. This solvated single-point result includes the SMD contribution but is not a complete molecular Gibbs free energy: temperature-dependent thermal and standard-state corrections require a separate, explicitly defined thermochemistry workflow.
