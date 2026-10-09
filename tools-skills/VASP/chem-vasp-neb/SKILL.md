---
name: chem-vasp-neb
description: >-
  Prepare native VASP NEB or VTST climbing-image inputs for an existing ordered
  reaction path, and guide execution/continuation through a configured launcher.
  Preserve common atom order, cells and constraints; output preparation does not
  establish path convergence or validate a target TS.
license: MIT
compatibility: Python 3.10+ and ASE 3.26.0; licensed VASP potentials for preparation; MPI VASP runtime for native NEB; verified VTST-patched VASP for native climbing image
allowed-tools: Read, Write, Bash, exec_command
---

# VASP NEB and Climbing-Image NEB

## Applicability

Use VASP to optimize a supplied fixed-cell reaction path. The helper prepares native directories from ordered images including endpoints, preserving a common ASE species permutation, coordinates and fixed masks.

Path and atom correspondence must be known. No products, mapping, alignment or intermediates are inferred. This uses native VASP NEB. Native climbing image requires a verified VTST executable and different optimizer settings from stock VASP.

## Credibility

- **High confidence**: cell/order/mask consistency and saved coordinates are checked. Element order alone does not establish identity among repeated atoms.
- **Medium confidence**: a converged path supports a barrier for the electronic model and supplied channel, subject to endpoint quality, image resolution and convergence.

The highest internal image is an inspection structure. A resolved internal maximum on a converged path can support a TS candidate, still requiring frequency and reaction-connectivity evidence. An endpoint maximum does not resolve an internal TS on the sampled path.

## Reference

- [API, continuation and results](references/api.md): consult only the relevant section; the preparation example below is complete.
- [VASP NEB](https://vasp.at/wiki/index.php/Nudged_elastic_bands), [VTST NEB](https://vtstools.readthedocs.io/en/latest/neb.html) and [VTST optimizers](https://vtstools.readthedocs.io/en/latest/optimizers.html): engine-specific controls.

## Input & Output

Save as `request.json`; the example supplies three images total, hence **one internal image**. Physical settings and image resolution are illustrative and must fit the task.

```json
{"image_files":["initial.extxyz","middle.extxyz","final.extxyz"],"output_dir":"neb-01","engine":"stock","parameters":{"xc":"PBE","encut":500,"ediff":1e-6,"ispin":1,"kpts":[1,1,1],"nsw":100,"ediffg":-0.05}}
```

```text
python <skill-dir>/scripts/prepare_neb.py --request request.json
```

Preparation needs Python/ASE and licensed potentials via `VASP_PP_PATH`. Execution needs the site MPI launcher/allocation and licensed binary; `climb:true` additionally needs a verified VTST build. Inspecting existing output needs no executable or new job. Paths resolve from the request file, or the current directory for `--request -`. Use a new output directory with an existing parent. `fixed_atoms` uses **one-based original image indices**; directories start at **00**.

Output: root `INCAR`, `KPOINTS`, `POTCAR`, manifest/stdout JSON, and numbered `POSCAR`/`ase-sort.dat` files. `IMAGES = total images - 2`. The manifest records parameters, permutation and declared engine. `engine_capability_verified:false` means no binary inspection; no energies or convergence verdict are generated.

## Procedure Guidance

1. With known correspondence and images, call directly. Require the same full-rank 3D periodic cell, element order and active degrees of freedom; fixed coordinates must match. Endpoints should be appropriate minima with comparable settings before interpreting a barrier.
2. Select `engine:"stock"` for ordinary VASP; `engine:"vtst"` only for a known VTST binary, with `climb:true` for CI-NEB. Ordinary NEB can precede climbing image; continue its optimized path rather than regenerating it.
3. Execute the existing VASP/site command from the **NEB root**, once for the whole band. Use appropriate MPI/image parallelization; do not independently relax internal images.
4. Read only the needed output. For a sampled barrier or internal-maximum claim, compare qualified endpoint energies and review resolution. Preserve atom mapping when transferring a structure or fixed indices. A usable unconverged band may need continuation; an internal dip needs geometry inspection before splitting the path.

## Success Criteria

Helper exit 0 / `status:"success"` means prepared inputs; `vasp_executed` is false. Calculation success requires completion, electronic convergence and the internal images' **NEB projected-force** criterion. Scheduler completion, files or raw forces alone do not establish band convergence. A sampled barrier is not automatically a validated TS barrier.

## Matters & Troubleshooting

- Stock VASP cannot use this VTST `LCLIMB`/`IOPT` recipe. `POTIM=0` needs an active VTST optimizer; it disables stock ionic motion. Verify the build.
- Resolve swaps, overlap and unsuitable paths from the task's chemistry; independently sorting/remapping each image can corrupt the path.
- Continue from all usable internal `CONTCAR` files plus unchanged endpoints in a new directory. Keep count and correspondence; missing outputs do not justify silently interpolating again.
- Native NEB does not calculate endpoint energies. Supply separate comparable results or report the barrier unavailable.
- Helper scope: fixed cells, mesh k-points, per-element setups, `FixAtoms`. No binaries/potentials are bundled. Exit 2 = preparation error; 3 = missing dependency; install `ase==3.26.0` if needed.
