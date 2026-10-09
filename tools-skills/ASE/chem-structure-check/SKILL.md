---
name: chem-structure-check
description: >-
  Check XYZ structures for overlaps and explicit geometry or reference requirements
  in one read-only report. Use to verify fixed atoms, fragment rigidity and targets,
  with reported findings and check coverage.
license: MIT
compatibility: Python 3.10+ with ASE 3.26.0; CPU; offline after installation
allowed-tools: Read, Bash, exec_command
---

# Molecular Structure Checks

## Applicability

Use `scripts/check_structure.py` to check single-frame XYZ / extended XYZ files without modifying them. Combine coordinate validity, contacts, atom correspondence and task-specific expectations in one request; the report identifies violations and checks not performed.

The tool can check fixed Cartesian coordinates, all pair distances within a rigid fragment, and distance/angle/dihedral requirements. Energies, valence, optimization convergence and physical TS identity are outside its scope.

## Credibility

- **High confidence**: coordinate validity, coincident atoms and violations of explicit geometric requirements are deterministic checks. Reference results require correct atom correspondence; element order alone cannot identify swaps of identical elements.
- **Medium confidence**: radius-based contact warnings are screening hints. Known bonds and forming/breaking bonds need reaction-specific interpretation.

`passed:true` means no errors under the checks performed. It can coexist with warnings and does not establish physical plausibility or a verified TS.

## Reference

- [API reference](references/api.md): read only fields needed beyond the examples, such as rigid groups, geometry bounds, stable IDs, periodic checks or contact exceptions. Both examples below are self-contained.
- [ASE Atoms](https://docs.ase-lib.org/ase/atoms.html) and [ASE I/O](https://docs.ase-lib.org/ase/io/io.html): underlying geometry and file operations.

## Input & Output

Basic screening request, saved as `request.json`:

```json
{"structure_file":"input.xyz"}
```

Run with an ASE-enabled Python interpreter:

```text
python <skill-dir>/scripts/check_structure.py --request request.json
```

Add only the requirements supplied by the task. For example, to check fixed atoms against a reference:

```json
{"structure_file":"input.xyz","reference_file":"reference.xyz","preserve_atoms":[1,2],"preserve_tolerance_angstrom":0.00001}
```

Atom indices are **one-based**; distances use **Å**, angles **degrees**. Paths resolve from the request file's directory; `--request -` reads stdin and resolves from the working directory.

Stdout is JSON. Exit 0 / `status:"success"` means the checks ran, even if the structure failed. Exit 2 = request/file error; 3 = missing dependency. Input files are never changed.

## Procedure Guidance

1. Submit the basic request for validity and contact screening. If the task supplies further requirements, include them in the same request rather than running a preliminary basic check.
2. Add `expected_elements` for known composition/order, `preserve_atoms` for fixed coordinates, `rigid_groups` for internal pair distances, and `geometry_checks` for targets, ranges or changes. Reference-based fields need `reference_file`; use `id_array` when stable IDs are available and correspondence matters. Unrequested conditions are not verified.
3. Use task-known bonded `excluded_pairs` and `reactive_pairs` when their radius warnings are uninformative. Neither exception hides coincident atoms or absolute-distance warnings.
4. Read `passed` and `findings` together with `checks_performed` / `checks_skipped`. Confirm `reference_comparison.usable:true` before relying on reference results. Report the relevant violating atoms and values; correctly finding a problem completes an inspection task.

## Success Criteria

**Inspection completed:** exit 0 and `status:"success"`, with findings interpreted under the requested coverage. `passed:false` can be the correct result for a defective structure.

**Structure accepted for the requested next step:** all required checks were performed, `passed:true`, usable reference comparisons where needed, and task-appropriate review of warnings. Measurement-only checks do not establish that a target was met. Physical TS validation requires separate calculations.

## Matters & Troubleshooting

- `INVALID_REQUEST`, `INPUT_NOT_FOUND`, `INVALID_STRUCTURE_FILE` or `MULTIPLE_FRAMES`: correct the request/path or select a single frame.
- `NONFINITE_COORDINATES`, `INVALID_CELL`, `DUMMY_ATOMS` or `COINCIDENT_ATOMS`: report the defect; dependent geometry checks may be skipped. Coincidence means separation ≤ `1e-8` Å. Repair is a separate task.
- `REFERENCE_MISMATCH` / `ATOM_ID_MISMATCH`: establish correspondence before interpreting differences. No automatic alignment or remapping occurs.
- `RIGID_GROUP_DISTORTED`: use `worst_pair` to locate internal-distance changes. Pair distances do not distinguish reflections; stereochemical requirements need appropriate dihedral checks.
- For periodic checks, use `mic:true` with valid cells; MIC reference checks require matching cells/PBC. Dihedral changes wrap to `[-180,180)`.
- Contact screening is quadratic in atom count. Stored energy/force metadata is not evaluated. Missing ASE: install with `python -m pip install ase==3.26.0` in a workspace virtual environment.
