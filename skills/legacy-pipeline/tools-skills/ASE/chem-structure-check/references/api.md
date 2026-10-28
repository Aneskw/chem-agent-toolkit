# Structure Check API

Run `scripts/check_structure.py --request request.json`, or use `--request -` with JSON on stdin. Only single-frame `.xyz` / `.extxyz` files are accepted. Unknown fields are rejected. All atom lists use distinct one-based indices.

## Request

| Field | Meaning / default |
| --- | --- |
| `structure_file` | Required input path. |
| `reference_file` | Optional reference with identical atom count and ordered elements. |
| `expected_elements` | Optional ordered symbol list, e.g. `["C","H","H"]`. |
| `id_array` | Optional extended-XYZ per-atom array name, e.g. `atom_id`. IDs must be unique positive integers or nonempty strings. With a reference, ordered IDs must match. |
| `mic` | Boolean; default `false`. Apply minimum-image conventions to distances, angles, dihedrals and preservation. |
| `preserve_atoms` | Indices whose positions must match the reference; default `[]`. Requires `reference_file`. No alignment is performed. |
| `preserve_tolerance_angstrom` | Nonnegative maximum preserved-atom displacement; default `1e-6`. |
| `geometry_checks` | Array of measurement/constraint objects; default `[]`. |
| `rigid_groups` | Array of `{ "atoms":[...], "tolerance_angstrom":... }`; at least two atoms per group, requires reference; tolerance defaults to `1e-5` Å. |
| `contact_options` | Contact screening settings below; default `{}`. |

Each geometry check has `kind` (`distance`, `angle`, `dihedral`) and `atoms` (2, 3, 4 indices respectively). Optional constraints can be combined:

| Constraint | Meaning |
| --- | --- |
| `min`, `max` | Inclusive bounds on the reported value. Dihedrals use `[0,360)`; bounds do not wrap. |
| `target`, `tolerance` | Absolute target and allowed deviation; tolerance defaults to `1e-5` Å/degrees and requires a target. Dihedral target deviations wrap. |
| `max_delta` | Nonnegative maximum absolute change from the reference; requires `reference_file`. Dihedral changes wrap to `[-180,180)`. |

Without constraints, a check reports a measurement. Coincident angle points and collinear dihedral arms may make a measurement undefined. Geometry failures produce error findings.

Each rigid group checks every internal atom-pair distance against the reference. Overall translation/rotation is allowed; maximum absolute distance change must not exceed the tolerance. Results include `pair_count`, `max_distance_change_angstrom` and `worst_pair` with current/reference distances and signed change. A failure reports `RIGID_GROUP_DISTORTED`; unavailable reference correspondence reports `RIGID_GROUP_REFERENCE_UNAVAILABLE`. Reflections retain pair distances, so this is not a chirality check. With MIC, distances follow the periodic convention rather than unwrapped fragment geometry.

## Contact options

| Field | Meaning / default |
| --- | --- |
| `absolute_cutoff_angstrom` | Warn for distance below this nonnegative cutoff; default `0.6`. |
| `radius_type` | `covalent` (default) or `vdw`; ASE tabulated element radii. |
| `scale` | Warn when distance / sum of radii is below this nonnegative value; default `0.8` for covalent, `0.75` for vdw. |
| `excluded_pairs` | Known pairs exempt from radius screening; default `[]`. |
| `reactive_pairs` | Reaction-center pairs exempt from radius screening and labelled in contact findings; default `[]`. |

Neither exception suppresses absolute-cutoff warnings or coincident-atom errors. Coincidence is distance ≤ `1e-8` Å. Missing radius data produces a warning and leaves absolute screening active. A vdw screen also flags many ordinary bonds unless excluded. These criteria do not determine bonding.

## Output

`status:"success"` / exit 0 indicates execution, including structures with failed checks. Read:

- `passed`: true iff `error_count` is zero; warnings do not change it.
- `checks_performed`: categories attempted, including failed checks. `checks_skipped`: categories not attempted and why. A basic-only pass does not imply that unrequested geometric expectations or preservation were checked.
- `findings`: severity (`error` / `warning`), code, message and relevant indices/values.
- `geometry_checks`: value, units, constraints, optional `reference_value`/`delta`, and per-check `passed`.
- `reference_comparison`: `usable` and `stable_ids_checked`, when a reference was supplied. Requested IDs are also validated without a reference.
- `preserved_atoms`: measured displacement for each requested atom, when reference comparison is usable.
- `rigid_groups`: internal pair-distance comparison results for requested groups, when comparison is usable.
- `mic`, `contact_settings`, `ase_version`: conventions used. `physical_validation_performed` is always false.

Invalid coordinates/cells skip geometric checks; reference mismatches disable reference comparisons. Element/ID mismatch and failed explicit bounds are errors. `CLOSE_CONTACT` and `MISSING_RADII` are warnings. An unavailable reference cannot satisfy `max_delta`.

Coverage categories are `basic_structure`, `expected_elements`, `stable_atom_ids`, `reference_correspondence`, `contacts`, `cartesian_preservation`, `rigid_group_distances`, `geometry_measurements` and `geometry_expectations`. Reference correspondence without stable IDs checks count/ordered elements only. Measurement-only requests skip `geometry_expectations`; failed/undefined measurements remain visible in per-check results. Physical validation is outside this coverage.

`status:"error"` reports an `error.code` and `error.message`; exit 2 means request/file failure, exit 3 missing ASE/NumPy. Check execution status before reading `passed`. No output structure is written.
