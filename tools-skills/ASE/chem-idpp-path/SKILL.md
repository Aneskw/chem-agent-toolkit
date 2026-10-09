---
name: chem-idpp-path
description: >-
  Initialize reaction or NEB paths from known XYZ endpoints with ASE IDPP. Use for
  intermediate images with explicit atom mapping, fixed atoms or supplied seeds,
  and reported convergence and endpoint preservation.
license: MIT
compatibility: Python 3.10+ with ASE 3.26.0; CPU; offline after installation
allowed-tools: Read, Write, Bash, exec_command
---

# IDPP Path Initialization

## Applicability

Use `scripts/idpp_path.py` to generate intermediate structures between corresponding single-frame XYZ / extended XYZ endpoints. It handles initialization, ASE IDPP relaxation, file saving and convergence reporting while preserving endpoints and explicitly fixed atoms.

Both endpoints and atom correspondence must be known. The tool does not infer products or mapping, align endpoints, calculate physical energies or verify a TS. Variable-cell paths are unsupported.

## Credibility

- **High confidence**: endpoint/order preservation, fixed coordinates and serialized images are checked numerically. Correspondence still depends on supplied ordering or mapping; identical elements do not establish identity.
- **Medium confidence**: IDPP fits interpolated endpoint pair distances to prepare a geometric path. Convergence concerns an artificial objective, not a physical potential-energy surface.

No image is automatically a TS; the tool supplies no energy barrier or physical ranking.

## Reference

- [API reference](references/api.md): consult the relevant fields when using mapping, fixed atoms, seeds, stable IDs or periodic conventions; default initialization needs only the example below.
- [ASE NEB](https://docs.ase-lib.org/ase/neb.html) and [IDPP tutorial](https://docs.ase-lib.org/examples_generated/03-tutorials/neb_idpp.html): underlying interpolation method.

## Input & Output

Save as `request.json`; this example generates three internal images, five files including endpoints:

```json
{"initial_file":"initial.xyz","final_file":"final.xyz","n_internal_images":3,"output_dir":"path-01"}
```

Run with an ASE-enabled Python interpreter:

```text
python <skill-dir>/scripts/idpp_path.py --request request.json
```

Defaults: `fmax:0.1`, `max_steps:200`, `dt:0.1`. Change them only when the task or observed relaxation requires it. These are artificial IDPP/NEB optimizer settings, not physical accuracy thresholds.

Atom indices are **one-based**; image indices start at **0**; coordinates use **Å**. Paths resolve from the request file's directory, or the working directory for stdin (`--request -`). The output directory must be new, with an existing parent; inputs are never modified.

The directory contains numbered single-frame extended XYZ images including endpoints. Stdout JSON reports their paths, mapping, convergence, preservation and spacing diagnostics. Physical energies/forces and stale input metadata are omitted; requested stable IDs are retained.

## Procedure Guidance

1. With known corresponding endpoints in a common coordinate frame, submit the default request directly. Run the supplied script; inspecting ASE implementation is unnecessary for supported parameters.
2. Add only needed options: `final_atom_order` for a known final-file permutation; `fixed_atoms` for atoms with matching endpoint coordinates; `seed_files` for an ordered set of intermediate guesses; `mic:true` for intended shortest periodic motion. Mapping affects the final file, not the seeds.
3. Read `image_files`, `idpp.converged`, `endpoints_preserved` and `fixed_atoms_preserved`. Use returned paths for subsequent work. Inspect geometry and adjacent spacing before using the path; closest pairs include bonds and are not automatic collision verdicts.
4. Zero optimizer steps can be normal if the initial path already meets `fmax`. For `IDPP_NOT_CONVERGED`, report the finite path as unconverged; inspect initialization and settings before increasing the budget. If linear interpolation creates coincident atoms, provide noncoincident seeds rather than changing atom identity.

## Success Criteria

Exit 0 / `status:"success"` means a finite path was generated and saved with preserved endpoints/order. Require `idpp.converged:true` only to claim IDPP convergence. A finite unconverged path is returned with `IDPP_NOT_CONVERGED` and needs review. `physical_validation_performed` is always false.

## Matters & Troubleshooting

- `ATOM_MISMATCH` / `ATOM_ID_MISMATCH`: restore correspondence. `final_atom_order[i-1]` is the original final-file atom corresponding to initial atom `i`.
- `FIXED_ATOM_MISMATCH`: fixed coordinates must match in endpoints and seeds. Output files omit constraints; retain the reported fixed indices for later calculations.
- `CELL_MISMATCH` / `INVALID_CELL`: provide matching cells/PBC and valid periodic vectors. Stored ASE constraints are rejected; use explicit `fixed_atoms`.
- `COINCIDENT_ATOMS` / `DEGENERATE_PATH`: revise seeds to avoid overlapping atoms and identical adjacent images. The tool performs no random perturbation or mechanism search.
- `NUMERICAL_FAILURE`: inspect mapping, seeds and periodic conventions; a smaller `dt` may help. `OUTPUT_EXISTS`: choose a new directory. Exit 2 = request/file/numerical error; 3 = missing dependency.
- Pair distances do not encode bond order, chirality or reaction identity. Pair work is quadratic in atom count per image. Missing ASE: install with `python -m pip install ase==3.26.0` in a workspace virtual environment.
