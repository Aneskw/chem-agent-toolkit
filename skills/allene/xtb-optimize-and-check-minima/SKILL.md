---
name: xtb-optimize-and-check-minima
description: Optimize prepared molecular geometries with GFN2-xTB and inspect numerical vibrational frequencies to assess local-minimum character. Use for local structure refinement, not conformer searches or transition-state localization.
---

# GFN2-xTB geometry optimization and minimum checks

Turn a supplied molecular geometry into optimized coordinates and a frequency-based assessment of its stationary-point character. A successful local optimization does not establish the lowest-energy conformer.

## Set up xTB and the input

Use **xTB 6.8.0** from the [official release](https://github.com/grimme-lab/xtb/releases/tag/v6.8.0). Select the archive for the operating system and architecture, extract it with its resource directories intact, and make its `bin` directory available on `PATH`. Set `XTBPATH` to include the extracted `share/xtb` directory containing parameter/configuration files. The [official setup guide](https://xtb-docs.readthedocs.io/en/latest/setup.html) explains archive layout, environment variables and stack/OpenMP settings for larger calculations. Check the resolved executable with `xtb --version`; it should report 6.8.0.

Prepare these inputs before running:

| Input | Meaning |
| --- | --- |
| `molecule.xyz` | One molecular structure: atom count, comment line, then element symbols and Cartesian x/y/z coordinates in angstroms. Keep the `.xyz` extension. |
| `--chrg` | Integer total molecular charge. |
| `--uhf` | Number of unpaired electrons, **not spin multiplicity**; zero for a closed-shell singlet. |

Use a separate, clean working directory for each structure and copy the supplied XYZ into it. xTB writes fixed output names and normally reads an existing `xtbrestart`. Configuration files in the working directory or `XTBPATH` can also affect the calculation; check the reported settings. Keep the original supplied coordinates separately.

## Optimize and calculate frequencies

From the job directory, run this example for a neutral, closed-shell molecule:

```powershell
xtb molecule.xyz --gfn 2 --chrg 0 --uhf 0 --ohess tight > molecule.out 2> molecule.err
```

Replace the charge and unpaired-electron count for the actual system. This example uses no implicit solvent. `--gfn 2` explicitly selects GFN2-xTB; `--ohess tight` combines tight geometry optimization with a numerical Hessian at the resulting geometry. Use the composite `--ohess` run type rather than combining separate `--opt` and `--hess` flags: xTB uses only the first selected run type.

Read both logs and confirm SCC and geometry convergence before interpreting frequencies. Look for `GEOMETRY OPTIMIZATION CONVERGED`. A nonzero exit status or fatal error means the calculation failed. Even a normally terminated run can report `ANCopt failed to converge the optimization` or `Hessian on incompletely optimized geometry!`; xTB may continue calculations on the last geometry. A coordinate file or completed Hessian alone therefore does not validate the result.

## Inspect and hand off the result

Files are written in the job directory:

| Result | Access and use |
| --- | --- |
| `molecule.out`, `molecule.err` | Calculation settings, convergence, warnings and projected vibrational frequencies in cm^-1. |
| `xtbopt.xyz` | Optimized XYZ coordinates, separate from the supplied input. Inspect the resulting structure for unintended changes in connectivity. |
| `xtbopt.log` | Xmol trajectory; comment lines contain energies and gradient norms. Use it to inspect the optimization path. |
| `hessian` | Non-mass-weighted Cartesian Hessian. |
| `vibspectrum` | Turbomole-style vibrational spectrum data. |
| `g98.out` | Gaussian-format normal-mode data for inspection in a compatible molecular viewer; this is xTB output. |

In the projected-frequency printout, imaginary modes appear as negative frequencies. A converged structure with no significant imaginary vibrational modes supports a local minimum at this model level. Distinguish tiny near-zero rigid-body/numerical modes from substantive imaginary vibrations by examining the mode displacement; do not invent a universal frequency cutoff. A genuine imaginary vibrational mode means minimum character has not been established. Missing frequency output also leaves that check incomplete.

For small imaginary modes, xTB can write `xtbhess.coord`, a geometry distorted along an imaginary mode. If mode inspection supports trying that correction, preserve the first run and copy the distorted file into a new job directory. Repeat the same command with `xtbhess.coord` as input and the same charge/unpaired count; the optimized output is then `xtbopt.coord`, matching the input format. Recheck both convergence and frequencies. Do not assume the distorted structure is already a minimum. The [official quickstart](https://xtb-docs.readthedocs.io/en/latest/basics.html#characterisation-of-stationary-points) illustrates this recovery path.

Return the optimized-coordinate path, convergence outcome, imaginary-mode assessment and relevant unresolved warnings. Hand off a validated geometry for subsequent calculations together with its GFN2-xTB method and electronic state. These are computed structural diagnostics, not experimental validation or evidence of a global minimum. Consult the [6.8.0 CLI manual](https://github.com/grimme-lab/xtb/blob/v6.8.0/man/xtb.1.adoc) when adapting flags or interpreting other output files.
