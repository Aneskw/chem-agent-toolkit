---
name: chem-ase-geometry
description: >-
  Query and edit molecular geometry with ASE. Use for distance, angle or torsion
  targets and rigid fragment positioning while preserving other atoms and verifying
  the saved structure.
license: MIT
compatibility: Python 3.10+ with ASE 3.26.0; CPU; offline after installation
allowed-tools: Read, Write, Bash, exec_command
---

# ASE Molecular Geometry Query and Editing

## Applicability

Use `scripts/geometry.py` to measure XYZ structures, compare reference geometry, or edit atoms and fragments with preserved atom order and saved-file verification. It handles distance, angle and dihedral targets, translation and rotation.

Queries support periodic structures; edits require contiguous, nonperiodic coordinates. Energies, geometry optimization and physical TS validation are outside this tool.

## Credibility

- **High confidence**: geometric measurements are deterministic. Edits check the requested internal-coordinate target after saving and verify unchanged coordinates of unselected atoms. Reference comparisons require correct atom correspondence.
- **Medium confidence**: contact hints are radius-based screening; fragment selection reflects the supplied connectivity, whose chemical meaning must be established separately.

A successful edit establishes geometric requirements, not a low-energy structure or a verified TS.

## Reference

- [API reference](references/api.md): read the relevant section for operations beyond the example, graph-based selection, periodic queries or contact settings. The example below needs no additional reference reading.
- [ASE Atoms](https://docs.ase-lib.org/ase/atoms.html) and [ASE I/O](https://docs.ase-lib.org/ase/io/io.html): underlying geometry and file operations.

## Input & Output

Input: JSON plus a single-frame `.xyz` / `.extxyz` file. Atom indices are **one-based**; distances use **Å**, angles **degrees**. `set_*` targets are absolute; dihedrals are returned in `[0,360)`.

Example: move the known fragment `[3,4]` to a requested distance while keeping `[1,2]` fixed. Replace the illustrative indices and target with task values. Save as `request.json`:

```json
{"operation":"set_distance","structure_file":"input.xyz","atoms":[1,3],"value":1.8,"moving_atoms":[3,4],"frozen_atoms":[1,2],"output_file":"edited.extxyz"}
```

Run with an ASE-enabled Python interpreter:

```text
python <skill-dir>/scripts/geometry.py --request request.json
```

Paths resolve from the request file's directory; `--request -` reads stdin and resolves from the working directory. Edits require a new output file and never overwrite existing files.

Stdout is JSON with `status`, measurements or edit verification, output paths and contact hints. Exit 0 = success; 2 = request/file/geometry error; 3 = missing dependency.

## Procedure Guidance

1. When indices and the moving group are known, construct the request directly. Use `inspect` only to resolve uncertain indices; use `select_fragment` when graph-based selection needs a preview.
2. For `set_distance`, `set_angle` or `set_dihedral`, supply `atoms` and `value`. Without a selector, only the last atom moves. Supply `moving_atoms` for an entire fragment, or use `fragment` with trusted connectivity; do not infer bonds from XYZ contact hints.
3. Execute the supplied script. For `set_*`, read `edit.coordinate.saved_value`; for all edits, read `edit.unselected_atoms_unchanged`. The tool already verifies these conditions, so a separate call is needed only for additional task requirements or suspicious results.
4. After successive edits, remeasure earlier targets if the later motion could disturb them. A single `measure` request can contain multiple measurements and a `reference_file`. Review contact hints when crowding matters, distinguishing known bonds and intended reaction pairs.

For graph-based editing and optional reference checks, see the [fragment example](references/api.md#fragment-edit-example).

## Success Criteria

Exit 0 and `status:"success"` indicate a completed operation. Internal-coordinate edits verify the saved target within `1e-5` Å/degrees; `edit.unselected_atoms_unchanged:true` confirms preservation of unselected atoms. Assess any additional task requirements separately. Contact hints do not change operation success.

## Matters & Troubleshooting

- `INVALID_INDICES`, `INVALID_SELECTION` or `FROZEN_ATOM`: check one-based indices, the moving side and fixed reference atoms. Frozen atoms cannot be selected. Stored ASE constraints are unsupported; use explicit `frozen_atoms`.
- `DEGENERATE_GEOMETRY`, `INVALID_PLANE` or `RING_FRAGMENT`: inspect coincident/collinear points or ring selection; consult the API's selection and plane rules.
- For periodic queries, use `mic:true` when appropriate. Periodic edits require correctly unwrapped, nonperiodic input. The tool does not align structures or map atoms.
- Choose a new output name if one exists. For `POSTCONDITION_FAILED`, inspect the request rather than loosening tolerances to hide the failure.
- Missing ASE: install in a workspace virtual environment with `python -m pip install ase==3.26.0`. Edited custom metadata is not recalculated and cannot supply new energies or forces.
