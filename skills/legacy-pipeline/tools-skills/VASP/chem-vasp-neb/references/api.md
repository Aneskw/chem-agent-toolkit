# Native VASP NEB API

## Request

| Field | Meaning |
|---|---|
| `image_files` | Required ordered list of 3..100 single-frame images, including endpoints |
| `output_dir` | Required new output directory with an existing parent |
| `parameters` | Required ASE `Vasp` keywords, normalized to lowercase |
| `engine` | `stock` (default) or `vtst`; declaration of the available build, not binary detection |
| `climb` | Boolean, default false; true requires `engine:"vtst"` |
| `fixed_atoms` | Optional unique one-based original-image indices; combined with `FixAtoms` |

Explicit common parameters: `xc`, positive `encut`, positive `ediff`, `ispin:1/2`, `kpts:[nx,ny,nz]`, positive `nsw`, negative `ediffg`. Other accepted ASE keywords describe the actual physical model, including potential setup, magnetism, charge, dispersion and dipole treatment. Preserve original input order for atom-indexed quantities. Existing fixed masks must match after applying `fixed_atoms`, and fixed coordinates must agree within 1e-8 Å in every image. Initial magnetic moments must also agree. A full-rank cell and all three PBC flags true are required; vacuum is explicit input for slabs/molecules.

The helper does not generate intermediates or match repeated elements. It uses the same ASE species permutation for every image and records it in the manifest. Per-element `setups` are supported; indexed setups, custom tags, execution keywords, `kspacing` and advanced chain options are rejected. Unusual accepted parameter combinations still require physical review.

## Engine controls

| Mode | Helper settings | Requirements |
|---|---|---|
| Stock NEB | Default `ibrion:1`, `potim:0.1`, `nfree:2`; optional `ibrion:3` with positive `potim` | No `lclimb`, `iopt`, `ichain`, `maxmove` |
| VTST NEB | `ibrion:3`, `potim:0`, `ichain:0`, `lclimb:false`; default `iopt:3` | Verified VTST binary; `iopt` in 1, 2, 3, 4, 7 |
| VTST CI-NEB | Same VTST settings with `lclimb:true` | `engine:"vtst"`, `climb:true` |

Every mode writes `isif:2`, derives `images` from the list, and defaults `spring:-5`. Contradictory supplied tags fail. Numerical defaults are starting settings, not convergence guarantees. Do not use `IBRION=2` for this native NEB wrapper. The stock `POTIM` is an ionic step parameter; VTST `POTIM=0` disables VASP's built-in optimizer so `IOPT` can act.

VTST example:

```json
{"image_files":["initial.extxyz","middle.extxyz","final.extxyz"],"output_dir":"cineb-01","engine":"vtst","climb":true,"parameters":{"xc":"PBE","encut":500,"ediff":1e-6,"ispin":1,"kpts":[1,1,1],"nsw":100,"ediffg":-0.03,"iopt":3}}
```

ASE accepting a tag and a binary ignoring an unknown tag do not prove CI-NEB ran. Verify site build documentation and actual VTST optimizer/climbing-image messages. TSAgent's native CI-NEB settings rely on a VASP+VTST module; they are not ordinary VASP defaults. [Official VASP clarification](https://vasp.at/forum/viewtopic.php?p=33172) distinguishes native stock NEB from VTST climbing image.

Preparation does not inspect the binary. If its capabilities or launcher/allocation are unknown, report that limitation; do not interpret a declared `engine` or prepared INCAR as evidence that CI-NEB executed.

## Execution

Run the site command from the NEB root. A configured Linux example is:

```bash
cd neb-01
mpirun -np 4 vasp_std > vasp.stdout 2> vasp.stderr
```

The rank count is illustrative. For several internal images, allocate ranks consistently with the build's image parallelization and `NCORE`/`KPAR`; endpoints are excluded from the moving-image count. Use the site's scheduler, modules and account when appropriate. Capture logs, job ID, exit status and output paths. An `sbatch` success means submission, not convergence. Do not hardcode TSAgent's cluster resources or execute in each image directory separately.

This is **native** NEB: VASP controls image optimization. ASE `NEB(images)` with separate `Vasp` calculators and an ASE optimizer is a different supported approach; it does not require VTST for ASE's climbing image, but it is not the workflow or directory contract here. Do not mix native `IMAGES`/ionic motion with an outer ASE NEB optimizer.

## Continue an existing band

Use source paths explicitly: unchanged endpoint geometries and each internal image's final nonempty, readable `CONTCAR`. Prepare a new directory with those image files, preserving count/order, cell, constraints, potentials and physical settings. Tighten convergence or enable VTST climbing image only as needed. If `CONTCAR` lacks original identities, reconstruct from the previous manifest/`ase-sort.dat`; fixed indices must refer to the actual order of the supplied continuation files.

This helper is a geometry restart and does not copy outputs or electronic restart files. Reuse compatible per-image `WAVECAR`/`CHGCAR` only when requested and with explicit `istart`/`icharg`. Do not copy old `OUTCAR` into a fresh job as though it were its result. When changing ENCUT, potentials, charge/spin or corrections, recheck endpoint energy compatibility and whether the electronic restart remains valid.

## Read energies and convergence

Read the last frame from a complete per-image `vasprun.xml` without launching a calculator:

```python
from ase.io import read

image = read("neb-01/01/vasprun.xml", index=-1)
energy_ev = image.calc.results["energy"]
free_energy_ev = image.calc.results.get("free_energy")
raw_forces_ev_per_angstrom = image.calc.results.get("forces")
```

If XML is unavailable, ASE supports `read(".../OUTCAR", format="vasp-out", index=-1)` for recoverable energies/forces. Missing or truncated output is an incomplete result; do not infer success from a parsed last available frame. Output atom order is the POSCAR order; the manifest's `input_to_poscar_atom` permutation can restore original order. Raw forces are not the NEB projected forces. Read band/optimizer convergence evidence from final OUTCAR/stdout records for the actual engine, and electronic convergence for every internal image. The helper does not implement a universal convergence parser.

Endpoints need separate results with the same POTCAR choices, functional/corrections, ENCUT, sampling, charge/spin policy and energy convention. Root control files do not prove the endpoint calculations used those settings. For comparable energies `E0..E(n+1)`:

```python
maximum_index = max(range(len(energies_ev)), key=energies_ev.__getitem__)
forward_sampled_barrier_ev = energies_ev[maximum_index] - energies_ev[0]
reverse_sampled_barrier_ev = energies_ev[maximum_index] - energies_ev[-1]
reaction_energy_ev = energies_ev[-1] - energies_ev[0]
```

Label the result a sampled barrier unless convergence and image resolution justify a stronger claim. If the maximum is an endpoint, there is no resolved internal TS maximum on this sampled path. Without comparable endpoint energies, the highest internal image is only an inspection structure; convergence alone does not qualify it as a resolved maximum. Image index 0 is the initial endpoint; POSCAR atom indices are a separate indexing convention. A supported internal maximum still needs local saddle and bidirectional path/endpoint evidence. This helper performs neither single-candidate saddle refinement nor IRC.
