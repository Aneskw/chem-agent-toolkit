---
name: gaussian-scan-relaxed-bending-profiles
description: Calculate relaxed bending-energy profiles with Gaussian 16 from supplied non-linear molecular geometries, matched core-angle mappings, and justified electronic states. Use when both bending angles must stay fixed while other coordinates relax.
---

# Relaxed bending profiles with Gaussian

Calculate one constrained optimization per supplied angle point at B3LYP/6-311+G(d,p), freezing both core bending angles. This workflow starts with prepared geometries; it does not generate the angle grid or implement a coupled scan. Exclude the exactly linear 180-degree endpoint, which needs separately validated linear-coordinate treatment.

## Environment and inputs

Use licensed **Gaussian 16 Revision C.02**, CPU execution on a compatible Linux x86_64 AVX2 host. Obtain access through your institution or [Gaussian orders](https://gaussian.com/orders/); use the official [installation instructions](https://gaussian.com/techsupport/#install) and [platform requirements](https://gaussian.com/g16/g16_plat.pdf). A configured installation must expose `g16`, writable scratch space, and a persistent working directory. On a managed cluster, obtain a compute allocation and follow its scheduler/resource setup before running the commands below. The [GWDG setup](https://docs.hpc.gwdg.de/software_stacks/applications/gaussian/index.html) is one documented C.02 deployment (`module load gaussian/16-C.02` there; module names elsewhere vary).

Supply these inputs for each profile:

| Input | Required content |
|---|---|
| Geometries | One full molecule per non-linear target angle; Cartesian `Element x y z` rows in angstroms, with consistent atom order. If supplied as XYZ, remove the atom-count and comment lines before inserting into Gaussian input. |
| Two angle mappings | Ordered triples `(i,j,k)` and `(l,m,n)`; the middle atom is the vertex. Gaussian numbering starts at 1, excluding dummy atoms. |
| Electronic state | Justified integer charge and spin multiplicity, plus the intended electronic-state model; keep these consistent across a profile. |
| Grid | Target angles in degrees. Both mapped angles must already have the same target value in every starting geometry. |

Check the mapped angles from the supplied coordinates before preparing jobs. `F` freezes the existing coordinate value: it does not set a requested angle or make unequal angles equal. Preserve the full molecular composition and atom order.

## Prepare and run a point

The following Bash example consumes the external file `beta145.coords`, containing only coordinate rows and a final newline. It assumes both angles are already 145 degrees and, **for this example only**, that the first five atoms map to `C1,C2,C3,C2',C1'`, with a justified charge of -2 and singlet multiplicity. Replace the state, indices, filenames and resource choices to match your supplied system. The 8 GB / 4-core values are example allocations, not chemical settings; request sufficient scheduler memory beyond Gaussian's `%Mem`.

```bash
cat > beta145.com <<'EOF'
%Chk=beta145.chk
%Mem=8GB
%NProcShared=4
# B3LYP/6-311+G(d,p) Opt=(Tight,ModRedundant) Int=UltraFine NoSymm

Equal core bends, beta=145 degrees

-2 1
EOF
cat beta145.coords >> beta145.com
cat >> beta145.com <<'EOF'

A 1 2 3 F
A 5 4 3 F

EOF
g16 < beta145.com > beta145.log
```

The blank line after the Cartesian coordinates introduces the ModRedundant section; retain the trailing blank line. The leading `A` declares an angle and `F` freezes it. All other coordinates remain available to the optimizer. `Tight` tightens geometry convergence, `Int=UltraFine` supplies the integration grid, and `NoSymm` permits geometry changes that break symmetry. See the official [Opt documentation](https://gaussian.com/opt/) for this syntax.

Repeat with each supplied geometry and unique `.com`, `.log`, and `.chk` names. Input/log redirection and reused checkpoint names can overwrite earlier artifacts, so use a fresh point directory or new names for reruns. Keep checkpoints in persistent storage; site scratch files may be removed after the job.

## Validate and collect the profile

For each `.log`, inspect the echoed route, charge/multiplicity and initial parameters to confirm the intended job and both frozen angle definitions. Then:

1. Require `Optimization completed.` and its converged `Optimized Parameters` block, and check the end of the job for `Normal termination of Gaussian 16`. A printed SCF energy alone does not establish geometry convergence. If the log is incomplete, reports a convergence failure, `Number of steps exceeded`, or `Non-Optimized Parameters`, mark that point unresolved and inspect the failure before retrying; do not enter an intermediate energy as a successful point.
2. Locate both angles by their atom triples in `Optimized Parameters`, not by generated labels such as `A1`. Verify each against the target and against the other using the available output precision. If either differs, investigate the geometry/mapping/constraints before collecting the point.
3. Take the electronic energy from the **final converged optimization step preceding that block**. For B3LYP this is the `SCF Done` energy in atomic units (hartree). Keep the energy paired with that step's final Cartesian orientation table (angstroms); do not select an earlier orientation or energy. Use the available Cartesian orientation table; do not require a particular orientation heading.
4. Save the final geometry as an XYZ file: atom count, comment identifying the point, then element and x/y/z rows in the original atom order. Map the orientation table's atomic numbers back to elements. Retain the log and checkpoint alongside it.

Create a table with columns `target_deg, angle1_deg, angle2_deg, energy_hartree, charge, multiplicity, log_path, geometry_path, status`. Record failed/missing points explicitly. For accepted points within one composition, charge, state model and computational setup, calculate `delta_energy_hartree = energy_hartree - min(accepted energies)` and plot it against the matched bending angle.

The smallest sampled energy identifies the lowest accepted grid point; it does not locate an exact continuous minimum. These are constrained electronic energies, not thermal free energies. Optimization success establishes relaxation in the allowed coordinates, not an unconstrained minimum or proof that the chosen electronic state is the ground state. Keep different electronic-state profiles separate.
