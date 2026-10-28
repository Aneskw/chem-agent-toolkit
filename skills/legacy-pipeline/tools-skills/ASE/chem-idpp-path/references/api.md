# IDPP Path API

Run `scripts/idpp_path.py --request request.json` or `--request -` with stdin JSON. Unknown fields are rejected. Each input file must be one-frame `.xyz` / `.extxyz` with finite coordinates and real elements.

## Request

| Field | Meaning / default |
| --- | --- |
| `initial_file`, `final_file` | Required endpoint paths. Equal atom counts, corresponding elements, cell and PBC are required. |
| `output_dir` | Required new directory; parent must exist. |
| `n_internal_images` | Integer ≥ 1; default `5`. Total files = this value + 2. |
| `final_atom_order` | Full one-based final-file permutation; default identity. Entry `i-1` gives the final atom corresponding to initial atom `i`. |
| `id_array` | Optional custom scalar atom-ID array name. IDs must be unique positive integers or nonempty strings. Ordered IDs must match after final permutation. |
| `mic` | Boolean; default `false`. Apply minimum-image conventions to linear initialization, IDPP distances and diagnostics. |
| `fixed_atoms` | Distinct one-based indices in initial order; default `[]`. Cartesian positions must match within `1e-8` Å in endpoints and seeds. |
| `seed_files` | Optional ordered list of exactly `n_internal_images` intermediate-file paths. Seeds already use initial atom order, matching cells/PBC and requested IDs; the final permutation is not applied to seeds. |
| `fmax` | Positive finite artificial NEB-force convergence threshold; default `0.1`. |
| `max_steps` | Integer ≥ 0; default `200`. Zero evaluates the seed without relaxation. |
| `dt` | Positive finite MDMin time-step parameter; default `0.1`. |

For initial order C,H,O and final order O,C,H, known mapping is `final_atom_order:[2,3,1]`. This reorders the output final image, without changing its geometry or the input file. Same-element correspondence cannot be established from elements alone.

Cells/PBC must match even with `mic:false`. No cell interpolation, global alignment, mapping inference or endpoint optimization occurs. Stored ASE constraints are rejected; only explicit `fixed_atoms` are applied. Metadata/calculators are not carried into the generated path.

## Initialization and relaxation

Without seeds, use linear Cartesian interpolation (minimum-image endpoint displacement when `mic:true`). With seeds, use their positions directly. IDPP targets for image `i` are `(1-t)*D_initial + t*D_final`, with `t=i/(n_internal_images+1)` and endpoint pair-distance matrices `D`.

ASE `IDPP` calculators drive an `aseneb` band with climbing disabled and `MDMin`; automatic rotation/translation removal is disabled. Endpoints remain fixed. No physical calculator is attached. `fmax` / `max_force` use ASE's artificial IDPP/NEB optimizer convention, not physical atomic forces or an electronic-structure accuracy threshold.

Input/seed separation ≤ `1e-8` Å is rejected before optimization. Identical endpoints or adjacent seed images under the selected displacement convention are rejected. Singular/nonfinite relaxation is an error. There is no random perturbation or automatic alternative-mechanism search.

## Output and interpretation

`status:"success"` / exit 0 includes converged and finite unconverged paths:

- `image_files`: ordered absolute paths `image-000.extxyz` through `image-N.extxyz`; first and last are endpoints. These are separate single-frame files.
- `idpp`: `converged`, `steps_used`, `max_steps`, `fmax`, `max_force`, optimizer settings and force convention. An unconverged path carries `IDPP_NOT_CONVERGED` in `warnings`.
- `final_atom_order`, `stable_ids_checked`, `fixed_atoms`, `mic`, `initialization`: correspondence and conventions used.
- `endpoints_preserved`, `fixed_atoms_preserved`: verified before serialization; saved coordinates match generated coordinates within `1e-7` Å.
- `image_diagnostics`: minimum pair distance and its one-based atom pair for every image; null for one-atom structures. These include bonded pairs and are not chemical quality scores.
- `adjacent_spacing`: RMS and maximum per-atom displacement between neighboring images, using the requested MIC convention. Uneven spacing warrants inspection, not automatic physical rejection.
- `physical_validation_performed:false`: no energies, barrier, frequency analysis or reaction-path verification.

Diagnostics describe generated positions before XYZ rounding. Files retain elements, positions, cell/PBC and the requested ID array only. Constraints and stale energy/force metadata are omitted. Requested endpoints retain positions to serialization precision; the final image uses the reported atom permutation.

`status:"error"` contains `error.code` / `error.message`; exit 2 means request/file/path failure, exit 3 missing ASE/NumPy. Failed writes remove newly created partial output. Existing output paths are never reused. Files are written only after finite-path checks; nonconvergence alone does not discard a finite path.
