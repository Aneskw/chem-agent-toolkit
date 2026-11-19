---
name: gaussian-calculate-smd-dioxane-single-point-energies
description: Calculate PBE0-D3BJ/def2-TZVP solvent single-point energies with Gaussian 16 for prepared catalyst and reaction geometries, and extract comparable energies in SMD 1,4-dioxane.
---

# Solvent single-point energies with Gaussian

Use supplied optimized structures to calculate solvent electronic energies. Structure optimization, transition-state identification and frequency-derived thermal corrections are separate inputs or tasks; a single-point calculation does not establish a Gibbs free-energy barrier.

## Environment and inputs

Use **Gaussian 16 Revision C.02**, with its supported Linux AVX2 binary and a valid license. Obtain access through your institution or [Gaussian](https://gaussian.com/). For a new licensed installation, follow the official [UNIX binary setup](https://gaussian.com/g16/g16bin_install.pdf) and [platform requirements](https://gaussian.com/g16/g16_plat.pdf).

An existing installation must expose `g16` and provide writable scratch space with sufficient capacity. Use the site's module/environment setup. For a standalone Bash setup, the vendor specifies `g16root` as the parent of the installed `g16` directory, exports `GAUSS_SCRDIR`, and sources `$g16root/g16/bsd/g16.profile`. Confirm C.02 in the job's Gaussian version banner. Run on an allocated compute node when using a cluster.

Prepare one coordinate file per structure and retain its charge, spin multiplicity and structural identity.

| Item | Required form |
| --- | --- |
| `state_a.coords` | Optimized geometry: one `Element x y z` line per atom, distances in angstroms. Omit XYZ atom-count and comment lines. |
| Charge/multiplicity | Integer net charge and spin multiplicity (`2S+1`), appropriate to that structure. |
| Resources | CPU count and memory within the allocated job resources; writable scratch directory. |
| Results | `state_a.log` contains energies and diagnostics; `state_a.chk` is the checkpoint requested below. |

## Prepare and run a single point

In a fresh working directory containing the supplied `state_a.coords`, construct the input below. The example assumes a **neutral singlet**; replace `0 1` when necessary. Four cores and 4 GB are illustrative resource choices. Use a unique stem for each state: the shell redirections overwrite existing input/log files.

```bash
cat > state_a.com <<'EOF'
%nprocshared=4
%mem=4GB
%chk=state_a.chk
#p PBE1PBE/Def2TZVP SP EmpiricalDispersion=GD3BJ
   SCRF=(SMD,Solvent=1,4-Dioxane)

State A solvent single point

0 1
EOF
cat state_a.coords >> state_a.com
printf '\n\n' >> state_a.com

g16 < state_a.com > state_a.log
```

Keep the blank lines separating the route, title and molecular specification, and the blank line terminating the coordinates. The job calculates energy at the supplied geometry; it does not optimize it.

The method mapping is `PBE1PBE` = PBE0, `EmpiricalDispersion=GD3BJ` = D3 with Becke-Johnson damping, and `Def2TZVP` = the def2-TZVP basis. `SMD` explicitly selects the solvent model rather than the default SCRF model. See the Gaussian 16 [DFT](https://www.conflex.co.jp/gaussian_support/dft.php), [basis](https://www.conflex.co.jp/gaussian_support/basissets.php) and [SCRF](https://www.conflex.co.jp/gaussian_support/scrf.php) manuals for these interfaces.

## Extract and compare energies

Inspect the end of `state_a.log` for `Normal termination of Gaussian` and check that the echoed method, solvent and charge/multiplicity match the intended input. An error termination, convergence failure or truncated log does not supply an accepted result, even if an earlier energy appears.

Read the final converged `SCF Done:` energy for this single-point job. Its `A.U.` unit is hartree. The separately printed `SMD-CDS (non-electrostatic) energy` is already included in the reported total: **do not add it again**.

Repeat with unique filenames for the other prepared states. Record the structure identifier, charge/multiplicity, method, solvent, energy and termination status. For states with the same composition, form the relative solvent electronic energy as `E(state) - E(reference)`. For reaction steps involving separate molecules, first balance the species and use the corresponding energy sums. Compare each catalyst model against its own consistent reference rather than subtracting totals for different catalyst compositions.

These are model energies at supplied geometries. Free-energy profiles additionally require a consistent, separately established thermal and standard-state treatment.
