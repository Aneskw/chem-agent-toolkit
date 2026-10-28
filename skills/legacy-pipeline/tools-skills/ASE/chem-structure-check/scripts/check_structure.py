#!/usr/bin/env python3
"""Read-only XYZ structure checks with explicit geometric expectations."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

try:
    import ase
    import numpy as np
    from ase.data import atomic_numbers, covalent_radii, vdw_radii
    from ase.io import read
except ImportError as exc:
    DEPENDENCY_ERROR = str(exc)
else:
    DEPENDENCY_ERROR = None

KINDS = {"distance": 2, "angle": 3, "dihedral": 4}
FIELDS = {"structure_file", "reference_file", "expected_elements", "id_array", "mic",
          "preserve_atoms", "preserve_tolerance_angstrom", "geometry_checks", "contact_options", "rigid_groups"}


class CheckError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(condition, message, code="INVALID_REQUEST"):
    if not condition:
        raise CheckError(code, message)


def number(value, name, minimum=None):
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{name} must be a number.")
    try:
        value = float(value)
    except OverflowError as exc:
        raise CheckError("INVALID_REQUEST", f"{name} exceeds floating-point range.") from exc
    require(math.isfinite(value), f"{name} must be finite.")
    require(minimum is None or value >= minimum, f"{name} must be >= {minimum}.")
    return value


def indices(value, count, name, length=None):
    require(isinstance(value, list) and (length is None or len(value) == length), f"Invalid {name} length.")
    require(all(type(i) is int and 1 <= i <= count for i in value), f"{name} requires indices in 1..{count}.")
    require(len(set(value)) == len(value), f"{name} contains duplicate indices.")
    return [i - 1 for i in value]


def pairs(value, count, name):
    require(isinstance(value, list), f"{name} must be a pair list.")
    result = [tuple(sorted(indices(pair, count, name, 2))) for pair in value]
    require(len(set(result)) == len(result), f"{name} contains duplicate pairs.")
    return set(result)


def resolve(value, base, name):
    require(isinstance(value, str) and bool(value.strip()), f"{name} requires a path string.")
    path = (base / value).resolve()
    require(path.is_file(), f"File not found: {path}", "INPUT_NOT_FOUND")
    return path


def load(path):
    require(path.suffix.lower() in {".xyz", ".extxyz"}, "Use single-frame XYZ or extended XYZ.", "UNSUPPORTED_FORMAT")
    try:
        frames = read(str(path), index=":", format="extxyz")
    except Exception as exc:
        raise CheckError("INVALID_STRUCTURE_FILE", f"Cannot parse XYZ: {exc}") from exc
    require(len(frames) == 1, "Select exactly one frame before checking.", "MULTIPLE_FRAMES")
    return frames[0]


def metric(atoms, kind, chosen, mic):
    function = {"distance": atoms.get_distance, "angle": atoms.get_angle, "dihedral": atoms.get_dihedral}[kind]
    value = float(function(*chosen, mic=mic))
    if not math.isfinite(value):
        raise ValueError("Nonfinite geometric result.")
    return value


def delta(value, reference, kind):
    difference = value - reference
    return (difference + 180) % 360 - 180 if kind == "dihedral" else difference


def valid_ids(atoms, name):
    if name not in atoms.arrays:
        return None
    array = atoms.arrays[name]
    if array.ndim != 1 or len(array) != len(atoms):
        return None
    values = array.tolist()
    valid = all((type(v) is int and v > 0) or (isinstance(v, str) and bool(v.strip())) for v in values)
    return values if valid and len(set(values)) == len(values) else None


def execute(request, base_dir=None):
    if DEPENDENCY_ERROR:
        raise CheckError("MISSING_DEPENDENCY", DEPENDENCY_ERROR)
    require(isinstance(request, dict), "Request must be a JSON object.")
    require(not set(request) - FIELDS, f"Unknown fields: {sorted(set(request) - FIELDS)}")
    base = Path(base_dir or Path.cwd()).resolve()
    source = resolve(request.get("structure_file"), base, "structure_file")
    atoms = load(source)
    mic = request.get("mic", False)
    require(type(mic) is bool, "mic must be a boolean.")
    preserved = indices(request.get("preserve_atoms", []), len(atoms), "preserve_atoms")
    preserve_tolerance = number(request.get("preserve_tolerance_angstrom", 1e-6), "preserve_tolerance_angstrom", 0)
    require(not preserved or "reference_file" in request, "preserve_atoms requires reference_file.")
    id_name = request.get("id_array")
    require(id_name is None or (isinstance(id_name, str) and bool(id_name.strip())), "id_array must be a nonempty name.")
    expected = request.get("expected_elements")
    if expected is not None:
        require(isinstance(expected, list) and len(expected) > 0
                and all(isinstance(x, str) and x in atomic_numbers and x != "X" for x in expected),
                "expected_elements must be a nonempty ordered element list.")
    options = request.get("contact_options", {})
    require(isinstance(options, dict) and not set(options) - {
        "absolute_cutoff_angstrom", "radius_type", "scale", "excluded_pairs", "reactive_pairs"},
        "Unknown contact_options fields.")
    cutoff = number(options.get("absolute_cutoff_angstrom", 0.6), "absolute_cutoff_angstrom", 0)
    radius_type = options.get("radius_type", "covalent")
    require(isinstance(radius_type, str) and radius_type in {"covalent", "vdw"}, "radius_type must be covalent or vdw.")
    scale = number(options.get("scale", 0.8 if radius_type == "covalent" else 0.75), "scale", 0)
    excluded = pairs(options.get("excluded_pairs", []), len(atoms), "excluded_pairs")
    reactive = pairs(options.get("reactive_pairs", []), len(atoms), "reactive_pairs")
    specs = request.get("geometry_checks", [])
    require(isinstance(specs, list), "geometry_checks must be an array.")
    prepared = []
    for spec in specs:
        require(isinstance(spec, dict) and {"kind", "atoms"} <= set(spec) and not set(spec) - {
            "kind", "atoms", "min", "max", "target", "tolerance", "max_delta"}, "Invalid geometry check fields.")
        kind = spec["kind"]
        require(isinstance(kind, str) and kind in KINDS, "Unknown geometry kind.")
        chosen = indices(spec["atoms"], len(atoms), "atoms", KINDS[kind])
        checked = {key: number(spec[key], key, 0 if key in {"tolerance", "max_delta"} else None)
                   for key in {"min", "max", "target", "tolerance", "max_delta"} if key in spec}
        require("min" not in checked or "max" not in checked or checked["min"] <= checked["max"], "min exceeds max.")
        require("tolerance" not in checked or "target" in checked, "tolerance requires target.")
        require("max_delta" not in checked or "reference_file" in request, "max_delta requires reference_file.")
        prepared.append((kind, chosen, checked))
    groups = request.get("rigid_groups", [])
    require(isinstance(groups, list), "rigid_groups must be an array.")
    prepared_groups = []
    for group in groups:
        require(isinstance(group, dict) and "atoms" in group and not set(group) - {"atoms", "tolerance_angstrom"},
                "Invalid rigid group fields.")
        chosen = indices(group["atoms"], len(atoms), "rigid group atoms")
        require(len(chosen) >= 2, "Rigid groups require at least two atoms.")
        require("reference_file" in request, "rigid_groups requires reference_file.")
        prepared_groups.append((chosen, number(group.get("tolerance_angstrom", 1e-5), "tolerance_angstrom", 0)))
    response = {"schema_version": "1.1", "status": "success", "structure_file": str(source),
                "ase_version": ase.__version__, "atom_index_base": 1, "atom_count": len(atoms),
                "physical_validation_performed": False, "findings": [], "geometry_checks": [],
                "checks_performed": [], "checks_skipped": [], "rigid_groups": []}

    def coverage(name, performed, reason):
        if performed:
            response["checks_performed"].append(name)
        else:
            response["checks_skipped"].append({"check": name, "reason": reason})

    def finding(severity, code, message, **details):
        response["findings"].append({"severity": severity, "code": code, "message": message, **details})

    def basic(structure, role):
        okay = True
        if len(structure) == 0:
            finding("error", "EMPTY_STRUCTURE", f"{role} has no atoms.")
            okay = False
        invalid = np.where(~np.isfinite(structure.positions).all(axis=1))[0]
        if len(invalid):
            finding("error", "NONFINITE_COORDINATES", f"{role} contains nonfinite coordinates.",
                    atoms=(invalid + 1).tolist())
            okay = False
        dummy = np.where(structure.numbers <= 0)[0]
        if len(dummy):
            finding("error", "DUMMY_ATOMS", f"{role} contains unsupported dummy atoms.", atoms=(dummy + 1).tolist())
            okay = False
        if not np.isfinite(structure.cell.array).all():
            finding("error", "INVALID_CELL", f"{role} has a nonfinite cell.")
            okay = False
        elif structure.pbc.any() and np.linalg.matrix_rank(structure.cell.array[structure.pbc]) != int(structure.pbc.sum()):
            finding("error", "INVALID_CELL", f"{role} periodic cell directions are not independent.")
            okay = False
        return okay

    source_usable = basic(atoms, "Structure")
    coverage("basic_structure", True, "")
    coverage("expected_elements", expected is not None, "No expected_elements supplied.")
    coverage("stable_atom_ids", id_name is not None, "No id_array supplied; identical-element swaps are not checked.")
    if expected is not None and list(atoms.symbols) != expected:
        finding("error", "ELEMENT_ORDER_MISMATCH", "Structure does not match expected_elements.")
    source_ids = valid_ids(atoms, id_name) if id_name else None
    if id_name and source_ids is None:
        finding("error", "INVALID_ATOM_IDS", "Requested ID array is missing, nonunique or invalid.")
    reference, reference_usable = None, False
    if "reference_file" in request:
        reference_path = resolve(request["reference_file"], base, "reference_file")
        reference = load(reference_path)
        response["reference_file"] = str(reference_path)
        reference_usable = basic(reference, "Reference")
        if not np.array_equal(atoms.numbers, reference.numbers):
            finding("error", "REFERENCE_MISMATCH", "Reference atom count or element order differs.")
            reference_usable = False
        if id_name:
            reference_ids = valid_ids(reference, id_name)
            if source_ids is None or reference_ids is None or source_ids != reference_ids:
                finding("error", "ATOM_ID_MISMATCH", "Stable atom IDs do not correspond in input order.")
                reference_usable = False
        if mic and (not np.array_equal(atoms.pbc, reference.pbc)
                    or not np.allclose(atoms.cell.array, reference.cell.array, atol=1e-7, rtol=0)):
            finding("error", "REFERENCE_CELL_MISMATCH", "MIC comparison requires matching cell and pbc.")
            reference_usable = False
        response["reference_comparison"] = {"usable": bool(reference_usable and source_usable),
                                             "stable_ids_checked": id_name is not None}
    coverage("reference_correspondence", reference is not None, "No reference_file supplied.")
    usable_reference = source_usable and reference_usable
    coverage("contacts", source_usable, "Input geometry is unusable.")
    coverage("cartesian_preservation", bool(preserved) and usable_reference,
             "Reference comparison is unusable." if preserved else "No preserve_atoms supplied.")
    coverage("rigid_group_distances", bool(prepared_groups) and usable_reference,
             "Reference comparison is unusable." if prepared_groups else "No rigid_groups supplied.")
    coverage("geometry_measurements", bool(prepared) and source_usable,
             "Input geometry is unusable." if prepared else "No geometry_checks supplied.")
    coverage("geometry_expectations", any(c for _, _, c in prepared) and source_usable,
             "Input geometry is unusable." if prepared and not source_usable else "No explicit geometry constraints supplied.")
    if source_usable and prepared_groups and not reference_usable:
        finding("error", "RIGID_GROUP_REFERENCE_UNAVAILABLE", "Cannot check group distances without usable reference correspondence.")
    if source_usable:
        table = covalent_radii if radius_type == "covalent" else vdw_radii
        radii = [float(table[n]) if n < len(table) else float("nan") for n in atoms.numbers]
        missing = [i + 1 for i, r in enumerate(radii) if not math.isfinite(r) or r <= 0]
        if missing:
            finding("warning", "MISSING_RADII", "Only absolute-distance checks apply to atoms without radius data.", atoms=missing)
        for a in range(len(atoms) - 1):
            for b in range(a + 1, len(atoms)):
                distance = atoms.get_distance(a, b, mic=mic)
                if not np.isfinite(distance):
                    finding("error", "DISTANCE_OVERFLOW", "Pair distance cannot be represented.", atoms=[a + 1, b + 1])
                    continue
                radius_sum = radii[a] + radii[b]
                ratio = float(distance / radius_sum) if math.isfinite(radius_sum) and radius_sum > 0 else None
                absolute = distance < cutoff
                compressed = (a, b) not in (excluded | reactive) and ratio is not None and ratio < scale
                if distance <= 1e-8 or absolute or compressed:
                    details = {"atoms": [a + 1, b + 1], "distance_angstrom": float(distance),
                               "radius_ratio": ratio, "reactive_pair": (a, b) in reactive}
                    criteria = [label for flag, label in [(absolute, "absolute_cutoff"), (compressed, "radius_screen")] if flag]
                    if reference_usable:
                        ref_distance = reference.get_distance(a, b, mic=mic)
                        if np.isfinite(ref_distance):
                            details["reference_distance_angstrom"] = float(ref_distance)
                        else:
                            finding("error", "DISTANCE_OVERFLOW", "Reference pair distance cannot be represented.", atoms=[a + 1, b + 1])
                    finding("error" if distance <= 1e-8 else "warning",
                            "COINCIDENT_ATOMS" if distance <= 1e-8 else "CLOSE_CONTACT",
                            "Coincident atoms." if distance <= 1e-8 else "Review close contact in reaction context.",
                            criteria=criteria, **details)
        if reference_usable and preserved:
            from ase.geometry import find_mic
            displacement = atoms.positions[preserved] - reference.positions[preserved]
            if mic:
                displacement, _ = find_mic(displacement, atoms.cell, atoms.pbc)
            distances = np.linalg.norm(displacement, axis=1)
            response["preserved_atoms"] = [{"atom": a + 1, "displacement_angstrom": float(d) if np.isfinite(d) else None} for a, d in zip(preserved, distances)]
            for a, distance in zip(preserved, distances):
                if not np.isfinite(distance):
                    finding("error", "DISTANCE_OVERFLOW", "Preserved-atom displacement cannot be represented.", atoms=[a + 1])
                elif distance > preserve_tolerance:
                    finding("error", "PRESERVED_ATOM_MOVED", "Atom exceeds the requested preservation tolerance.",
                            atoms=[a + 1], displacement_angstrom=float(distance))
        if reference_usable:
            for chosen, tolerance in prepared_groups:
                entry = {"atoms": [i + 1 for i in chosen], "tolerance_angstrom": tolerance,
                         "pair_count": len(chosen) * (len(chosen) - 1) // 2}
                response["rigid_groups"].append(entry)
                maximum, worst = -1.0, None
                try:
                    for offset, a in enumerate(chosen[:-1]):
                        for b in chosen[offset + 1:]:
                            current = metric(atoms, "distance", [a, b], mic)
                            initial = metric(reference, "distance", [a, b], mic)
                            change = current - initial
                            if abs(change) > maximum:
                                maximum = abs(change)
                                worst = {"atoms": [a + 1, b + 1], "distance_angstrom": current,
                                         "reference_distance_angstrom": initial, "delta_angstrom": change}
                except (ValueError, ZeroDivisionError, FloatingPointError) as exc:
                    entry["passed"] = False
                    finding("error", "UNDEFINED_GEOMETRY", str(exc), atoms=entry["atoms"], kind="rigid_group_distances")
                    continue
                entry.update(max_distance_change_angstrom=maximum, worst_pair=worst, passed=maximum <= tolerance)
                if not entry["passed"]:
                    finding("error", "RIGID_GROUP_DISTORTED", "Group internal distances exceed the requested tolerance.",
                            atoms=entry["atoms"], max_distance_change_angstrom=maximum, worst_pair=worst)
        for kind, chosen, constraints in prepared:
            entry = {"kind": kind, "atoms": [i + 1 for i in chosen],
                     "unit": "angstrom" if kind == "distance" else "degree", "constraints": constraints}
            response["geometry_checks"].append(entry)
            try:
                value = metric(atoms, kind, chosen, mic)
                entry["value"] = value
                if reference_usable:
                    entry["reference_value"] = metric(reference, kind, chosen, mic)
                    entry["delta"] = delta(value, entry["reference_value"], kind)
            except (ValueError, ZeroDivisionError, FloatingPointError) as exc:
                entry["passed"] = False
                finding("error", "UNDEFINED_GEOMETRY", str(exc), atoms=entry["atoms"], kind=kind)
                continue
            violations = []
            if "min" in constraints and value < constraints["min"]:
                violations.append("min")
            if "max" in constraints and value > constraints["max"]:
                violations.append("max")
            if "target" in constraints and abs(delta(value, constraints["target"], kind)) > constraints.get("tolerance", 1e-5):
                violations.append("target")
            if "max_delta" in constraints:
                if "delta" not in entry:
                    violations.append("reference_unavailable")
                elif abs(entry["delta"]) > constraints["max_delta"]:
                    violations.append("max_delta")
            entry["passed"] = not violations
            if violations:
                finding("error", "GEOMETRY_EXPECTATION_FAILED", "Geometry violates user-specified bounds.",
                        atoms=entry["atoms"], kind=kind, violations=violations)
    else:
        response["geometry_skipped"] = "Input coordinates, atoms or cell are unusable."
    response["mic"] = mic
    response["contact_settings"] = {"absolute_cutoff_angstrom": cutoff, "radius_type": radius_type, "scale": scale}
    response["error_count"] = sum(f["severity"] == "error" for f in response["findings"])
    response["warning_count"] = sum(f["severity"] == "warning" for f in response["findings"])
    response["passed"] = response["error_count"] == 0
    return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, help="JSON request file, or - for stdin.")
    args = parser.parse_args()
    try:
        if args.request == "-":
            request, base = json.load(sys.stdin), Path.cwd()
        else:
            path = Path(args.request).resolve()
            request, base = json.loads(path.read_text(encoding="utf-8-sig")), path.parent
        response = execute(request, base)
        code = 0
    except CheckError as exc:
        response = {"status": "error", "error": {"code": exc.code, "message": str(exc)}}
        code = 3 if exc.code == "MISSING_DEPENDENCY" else 2
    except (OSError, ValueError, TypeError, KeyError, ArithmeticError, RuntimeError) as exc:
        response = {"status": "error", "error": {"code": "IO_OR_REQUEST_ERROR", "message": str(exc)}}
        code = 2
    print(json.dumps(response, ensure_ascii=True, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
