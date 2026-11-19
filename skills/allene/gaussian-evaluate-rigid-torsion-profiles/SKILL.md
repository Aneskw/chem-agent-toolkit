---
name: gaussian-evaluate-rigid-torsion-profiles
description: Calculate unrelaxed torsional energy profiles with Gaussian 16 from supplied rotated geometries, angle labels and justified electronic states. Use for rigid endgroup rotations rather than relaxed scans or transition-state searches.
---

# Rigid torsional energy profiles with Gaussian

Evaluate each supplied geometry independently at B3LYP/6-311+G(d,p) with an UltraFine integration grid. All nuclear coordinates stay fixed. This workflow starts after the geometry series has been prepared; it does not generate rotations.

## Environment and prepared inputs

Use licensed **Gaussian 16 Revision C.02** on a compatible Linux x86_64 AVX2 CPU installation. Obtain access through your institution or [Gaussian orders](https://gaussian.com/orders/), with the vendor's [installation entry](https://gaussian.com/techsupport/#install) and [platform requirements](https://gaussian.com/g16/g16_plat.pdf). The configured environment must expose `g16` and writable scratch space. On a cluster, run inside an allocated compute job using the site's scheduler setup. [GWDG's documented C.02 deployment](https://docs.hpc.gwdg.de/software_stacks/applications/gaussian/index.html) uses `module load gaussian/16-C.02`; module names elsewhere vary.

Prepare a separate working directory for each molecule and electronic-state series:

| Input | Required content |
|---|---|
| Geometry files | One complete molecule per angle, with consistent composition and atom order. Use Cartesian `Element x y z` rows in angstroms. For ordinary XYZ files, remove the atom-count and comment lines to obtain coordinate-only files such as `angle-000.coords`. |
| Angle manifest | Map each filename to its angle in degrees and the precise endgroup rotation definition, including atom/plane mappings. Verify the coordinates against that definition. |
| Rigid series | Structures differ only by the intended endgroup rotation; keep the remaining internal geometry consistent. Do not optimize individual points. |
| Electronic state | Supply justified integer charge, positive integer spin multiplicity and intended electronic-state treatment, consistently across the series. Do not infer multiplicity from charge alone. |

The method's published torsion grid is **0 through 170 degrees in 10-degree steps** ([method, page 6 and Figure 8b](https://doi.org/10.1002/chem.202304145)). Use the supplied rotation convention; labels alone do not define how the molecule was rotated. If the geometries or electronic states are missing, obtain those inputs before calculating.

## Prepare and run each point

The following Bash example assumes a supplied `angle-000.coords` in the current directory. The charge `-2`, multiplicity `1`, four CPU cores and 8 GB memory are example choices; replace them with the supplied state and allocated resources. The example does not establish that a particular dianion is a singlet.

```bash
charge=-2
multiplicity=1
cat > angle-000.com <<EOF
%NProcShared=4
%Mem=8GB
%Chk=angle-000.chk
# B3LYP/6-311+G(d,p) Int=UltraFine

Rigid torsion theta=0 degrees

${charge} ${multiplicity}
EOF
cat angle-000.coords >> angle-000.com
printf '\n\n' >> angle-000.com
g16 < angle-000.com > angle-000.log
```

Ensure a blank line separates the route, title and molecule specification, and that the coordinate block ends with a blank line. The [command-line guide](https://docs.icer.msu.edu/Running_Gaussian_by_Command_Lines/) documents input layout and redirection.

Repeat for each manifest entry, changing the angle title and all point-specific filenames, while preserving the route and electronic-state settings. There is no `Opt`, `Freq`, `Scan` or `--Link1--` section: with no job-type keyword, Gaussian performs its default single-point energy calculation. Adding `Opt` or a relaxed scan would change the profile's meaning.

Keep inputs, logs and checkpoints in persistent storage. Each checkpoint name must be unique. Shell `>` replaces an existing log, and reusing a checkpoint name can replace prior data; preserve earlier runs before rerunning a point.

## Collect and interpret the profile

Inspect each log, for example:

```bash
grep -E 'SCF Done:|Normal termination|Error termination|Convergence failure' angle-000.log
```

Accept a point only after confirming a converged SCF energy and `Normal termination of Gaussian 16` for that single-point job. Read the numerical energy after `=` on its `SCF Done:` line, in atomic units (Hartree); the method label in parentheses can depend on the electronic-state treatment. A printed energy alone does not establish successful completion. An error, convergence failure or missing normal termination leaves a missing point, never a zero energy. Diagnose the log before rerunning; document any changed settings and preserve comparability across the series.

Collect a table with `angle_deg, input_path, log_path, charge, multiplicity, E_hartree, status`. Retain failed angles with their status. For completed comparable points, choose and name one reference from the same series, for example its lowest computed energy, and calculate:

`delta_E_hartree(theta) = E_hartree(theta) - E_reference_hartree`

Plot angle against relative electronic energy and report missing angles and the reference used. Compare separate charge/spin series using their own references. These differences describe rigid torsional deformation on the supplied geometry series. The highest sampled point is not an optimized transition state or a relaxed reaction barrier; single-point electronic energies also contain no vibrational or thermal free-energy correction.
