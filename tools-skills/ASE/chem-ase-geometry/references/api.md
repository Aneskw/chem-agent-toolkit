# Geometry Tool API

Invoke `python <skill-dir>/scripts/geometry.py --request request.json`. Python callers may use `execute(request, base_dir)`; failures raise `GeometryError` with a code. Relative paths resolve from the JSON file's directory, or from the working directory for stdin requests.

## Operations

Every request requires `operation` and `structure_file`; edits also require a new `output_file`. Input is single-frame XYZ / extended XYZ. Indices are one-based, coordinates/distances use Å, and angles use degrees. Numbers must be finite and indices distinct; unknown fields are rejected.

| Operation | Specific fields | Behavior |
|---|---|---|
| inspect | None | Return atom table, cell and pbc |
| select_fragment | fragment | Preview selection as selected_atoms; no edit |
| measure | measurements; optional reference_file, mic | Query internal coordinates and optionally compare a reference; mic defaults to false |
| set_distance | atoms:[a,b], value | Fix a; translate b or its fragment along a-to-b; value > 0 |
| set_angle | atoms:[a,b,c], value; optional plane_atoms | Fix a,b; rotate c or its fragment about b; 0 <= value <= 180 |
| set_dihedral | atoms:[a,b,c,d], value | Fix a; rotate d or its fragment about b-to-c; target modulo 360 degrees |
| translate | vector_angstrom:[dx,dy,dz] | Translate the selected group |
| rotate | angle_degrees; axis_atoms or axis/origin_angstrom | Rotate the selected group about the specified axis using the right-hand rule |

## Query and Comparison

Each measurement specifies kind = distance/angle/dihedral and atoms containing 2/3/4 indices respectively. A reference_file requires the same atom count, element order and actual atom correspondence; swaps of same-element atoms cannot be detected. MIC comparisons also require matching cell and pbc.

```json
{"operation":"measure","structure_file":"candidate.extxyz","reference_file":"reactant.xyz","measurements":[{"kind":"distance","atoms":[1,3]},{"kind":"angle","atoms":[2,1,3]}]}
```

Each result includes value and unit; reference comparisons add reference_value and delta (current minus reference). Dihedral delta uses the shortest periodic difference in [-180,180). These are geometric changes, not chemical quality scores.

## Selection

Use task-supplied connectivity for `fragment`. If no trustworthy graph is available, use explicit `moving_atoms`; XYZ distance hints alone do not establish connectivity.

Editing selectors are mutually exclusive:

- `moving_atoms:[...]`: an explicit, nonempty atom group.
- `fragment:{"bonds":[[a,b],...],"seed_atom":b}`: the seed's connected component, suitable for moving an entire reactant. Supply explicit connectivity; omitted bonds are not inferred.
- An optional `cut_bond:[a,b]` in fragment selects the seed-side component after removing that edge from the selection graph. Use for internal torsion; this does not modify chemical connectivity.
- Without a selector, set_* moves only its last atom. translate/rotate require a selector.

For set_distance, fragment seed=b and an optional cut must be [a,b]. For set_angle, seed=c and cut=[b,c]. For set_dihedral, seed=c and cut=[b,c], and d must belong to the selected component. Cut endpoint order is unrestricted. translate/rotate/select_fragment may choose any seed; with a cut, the seed must be a cut endpoint. A ring that remains connected after cutting returns RING_FRAGMENT; explicit selections require a separate judgment about ring distortion.

The terminal atom of set_* must be selected. Do not select a for distance edits, a,b for angle edits, or a for dihedral edits. Dihedral axis atoms b/c may belong to the selected group. Optional frozen_atoms defaults to empty and cannot overlap the selection.

Preview and rotate a group, replacing connectivity with the actual structure's graph:

```json
{"operation":"select_fragment","structure_file":"chain.xyz","fragment":{"bonds":[[1,2],[2,3],[3,4]],"cut_bond":[2,3],"seed_atom":3}}
```

```json
{"operation":"rotate","structure_file":"chain.xyz","moving_atoms":[3,4],"axis_atoms":[2,3],"angle_degrees":30,"output_file":"rotated.extxyz"}
```

## Axis and Linear Angles

For rotate, `axis_atoms:[a,b]` uses a as an axis point and a-to-b as the direction. Reversing the indices reverses the rotation direction. Alternatively provide a nonzero axis vector and origin_angstrom coordinates; do not mix the two representations.

set_angle normally uses the plane of the two angle arms. A collinear starting geometry requires `plane_atoms:[p,q,r]`, defining the normal (q-p) cross (r-p). These points must be noncollinear, and both arm directions must lie in the plane. Noncollinear starts retain their original side. For collinear starts, the signed angle is defined as positive 0 or 180 degrees relative to the normal before rotation to the target. Swapping q/r changes the bending side.

For collinear atoms 1,2,3 and an additional atom 5 defining the plane:

```json
{"operation":"set_angle","structure_file":"linear.xyz","atoms":[1,2,3],"value":175,"plane_atoms":[2,3,5],"moving_atoms":[3,4],"output_file":"bent.extxyz"}
```

Targets of 0/180 degrees are supported but may create coincident atoms or undefined dihedrals. Collinear dihedrals return an error rather than an arbitrary direction.

## Contact Hints

By default, hints include distances below `contact_cutoff_angstrom` (default 0.6) and distances below the sum of element radii multiplied by scale. Configure contact_options with:

- radius_type: covalent (default; default scale 0.8) or vdw (default scale 0.75). Covalent screening flags substantial compression; van der Waals screening can flag nonbonded crowding when combined with known connectivity.
- excluded_pairs: known bonded or other pairs excluded from radius screening.
- reactive_pairs: reaction-center pairs excluded from radius screening to avoid treating partial bond formation as a collision.

```json
{"operation":"inspect","structure_file":"candidate.xyz","contact_options":{"radius_type":"vdw","excluded_pairs":[[1,2],[3,4]],"reactive_pairs":[[1,3]]}}
```

Exceptions still undergo the absolute-distance check, so severe overlap is not hidden. Each hint reports distance_angstrom, radius_ratio, criteria and exception flags. radius_ratio = distance / sum of element radii. Missing radii trigger absolute-distance checks only and are listed in unavailable_radius_atoms. These thresholds do not establish chemical validity.

## Results

edit returns selected_atoms, changed_atoms, max_displacement_angstrom and unselected_atoms_unchanged. Internal-coordinate edits include coordinate with before, target, after and saved_value. The last value is remeasured from the serialized structure and checked against the target. Output is extended XYZ without ASE calculator results; custom metadata is not recalculated.

status:success with exit code 0 indicates a successful geometric operation; physical_validation_performed is always false. On failure, read error.code/message: REFERENCE_MISMATCH identifies incompatible reference correspondence conditions; INVALID_PLANE identifies an incompatible rotation plane. Discard any incomplete output left by a file-write error.

## Fragment-edit example

The following values illustrate a hypothesis, not recommended TS distances. Assume trusted bonds 1–2 and 3–4, with fragment 1–2 fixed. All requests use this tool.

When the indices and connectivity are already known, submit the edit directly. Use `inspect` or `select_fragment` only to resolve uncertainty about indices or the moving side.

Save the edit request as `edit.json` and run this skill's script:

```json
{"operation":"set_distance","structure_file":"reactants.xyz","atoms":[1,3],"value":1.8,"fragment":{"bonds":[[1,2],[3,4]],"seed_atom":3},"output_file":"candidate-01.extxyz"}
```

Read the edit's saved target verification and `unselected_atoms_unchanged`. If the task also requires a reference comparison, the following optional request measures the target and the fragment distance together:

```json
{"operation":"measure","structure_file":"candidate-01.extxyz","reference_file":"reactants.xyz","measurements":[{"kind":"distance","atoms":[1,3]},{"kind":"distance","atoms":[3,4]}],"contact_options":{"excluded_pairs":[[1,2],[3,4]],"reactive_pairs":[[1,3]]}}
```

For that comparison, confirm the requested target and unchanged internal distance within task tolerances. Interpret contact hints in reaction context. After a later edit that could disturb these requirements, remeasure them against the original `reactants.xyz`.

Run each request with `python <skill-dir>/scripts/geometry.py --request <request.json>`. Keep request files beside their referenced structures, or use absolute paths.
