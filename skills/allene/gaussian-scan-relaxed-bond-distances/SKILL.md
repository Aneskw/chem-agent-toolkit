---
name: gaussian-scan-relaxed-bond-distances
description: Run a Gaussian constrained, relaxed bond-distance scan from supplied molecular inputs and recover converged structures and electronic energies along the coordinate.
---

# Relaxed bond-distance scans with Gaussian 16

## Prepare the environment and inputs

Use licensed **Gaussian 16 Rev. C.02**, with its AMD/Intel x86_64 AVX2 Linux binary on an OS listed in the [official platform matrix](https://gaussian.com/g16/g16_plat.pdf), such as Red Hat Enterprise Linux 8.3. Obtain Gaussian through [Gaussian ordering](https://gaussian.com/orders/) or your institution's licensed installation. Follow the [official running/setup instructions](https://gaussian.com/running/). This workflow uses one Linux host; site scheduler submission is an external handoff when required.

In a Bourne-compatible shell, set the actual installation parent and an existing writable scratch directory:

```sh
export g16root=/path/containing/g16
. "$g16root/g16/bsd/g16.profile"
export GAUSS_SCRDIR=/path/to/scratch
```

Collect these inputs before creating the job:

| Input | Required meaning |
| --- | --- |
| Geometry | Element and Cartesian x, y, z per atom in angstroms; preserve atom order. Remove XYZ atom-count/comment lines if importing XYZ. |
| Electronic state | Total integer charge and spin multiplicity, in that order. |
| Atom pair `i j` | Gaussian's 1-based atom numbers; dummy atoms are not counted. |
| Scan range | Starting distance, increment in angstroms, and integer number of increments. Prepare the supplied geometry at the intended starting distance. |
| Model chemistry | Method, basis and any intended environment settings, kept consistent across the scan. |

A relaxed scan fixes the selected distance at each point while optimizing the remaining coordinates. It explores a path conditional on the starting structure and model; it does not establish that every alternative transition state is absent or automatically provide a free-energy profile.

## Create and run the scan

Save `scan.gjf` in a dedicated job directory. This complete water input is an illustrative template: replace its geometry, electronic state, model chemistry and scan line with the supplied molecular inputs. The example extends atom pair 1–2 from an initial 0.96 Å using three 0.05 Å increments.

```text
%Chk=scan.chk
# B3LYP/6-31G** Opt=ModRedundant NoSymm

Illustrative O-H relaxed distance scan

0 1
O  0.000000  0.000000  0.000000
H  0.000000  0.000000  0.960000
H  0.920000  0.000000 -0.240000

1 2 S 3 0.05

```

Keep blank separators after the route, title, geometry and scan section, including a final blank line. The general scan line is `i j S nsteps stepsize`: `S` requests successive constrained optimizations after incrementing the distance. The starting distance comes from the input geometry; it is not a separate value in this line. `NoSymm` prevents symmetry-breaking scan failures. Keep this Berny/ModRedundant interface; adding GIC options changes the coordinate interface. See [Opt documentation](https://gaussian.com/opt/) for scan syntax and conditional optimizer options.

From the directory containing `scan.gjf`, run:

```sh
g16 < scan.gjf > scan.log
```

Redirection creates or overwrites `scan.log`; use a fresh job directory for a new scan. `%Chk=scan.chk` retains a named checkpoint in the working directory. Preserve the full log for all scan points; the checkpoint alone is not the per-point structure archive.

## Recover and interpret results

Read `scan.log` in optimization order. A list of all `SCF Done` lines includes unconverged geometry iterations and is not a scan profile.

For each completed constrained optimization:

1. Locate `Optimization completed.` and its `Optimized Parameters` table. Read the selected `R(i,j)` value (angstroms) and check the convergence information for that optimization.
2. Take the electronic energy from the **final optimization step preceding that table**. For the B3LYP example, this is the final associated `SCF Done: E(...) = ...` value, in hartree. If using another method, use its appropriate final total-energy field rather than assuming the SCF energy is the correlated energy.
3. Retain the Cartesian orientation table belonging to that same final step. With `NoSymm`, look for `Input orientation` if `Standard orientation` is absent. Orientation rows contain center number, atomic number, atomic type, then x, y, z. Keep the coordinates and elements in center-number order; map atomic numbers to element symbols. Do not accidentally save the next increment's starting geometry or duplicate a repeated final table.
4. Save one XYZ file per converged point, for example `point-000.xyz`, with atom count, a comment containing distance and energy, then `element x y z` rows in angstroms. Retain charge/multiplicity in the accompanying records because XYZ does not encode them.

Create `scan.csv` with at least:

```text
point,distance_A,energy_hartree,relative_energy_hartree,geometry_file,status
```

Choose and declare a reference point, then compute `relative_energy_hartree = energy_hartree - reference_energy_hartree`. Record actual optimized distances and verify that the intended interval and increments were covered, including the starting point when reported. Preserve `scan.gjf`, `scan.log`, `scan.chk`, the table and all retained geometries together.

Check the job's `Normal termination of Gaussian` marker as well as each point's convergence. An SCF failure, `Optimization stopped`, missing final optimization data or incomplete distance coverage leaves a partial scan: mark the affected point as failed or missing and retain its diagnostics. Resolve the cause before interpreting the full requested interval; do not substitute the last unconverged energy or bridge missing points as completed results.

Plot relative electronic energy against the measured distance and inspect the corresponding structures for rearrangements or changes of coordination. A maximum on this constrained path is a candidate for further transition-state work, not a transition-state classification. A smooth dissociation curve supports conclusions only for the explored path. Thermal or solvent free energies require separately justified calculations; ordinary harmonic frequency analysis requires a stationary geometry at the same level of theory ([frequency documentation](https://gaussian.com/freq/)).
