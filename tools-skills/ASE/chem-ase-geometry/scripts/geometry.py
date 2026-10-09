#!/usr/bin/env python3
"""Deterministic, one-based molecular geometry tools. No calculators or network."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import sys

try:
    import ase
    import numpy as np
    from ase.data import covalent_radii, vdw_radii
    from ase.io import read, write
except ImportError as exc:
    DEPENDENCY_ERROR = str(exc)
else:
    DEPENDENCY_ERROR = None

SCHEMA_VERSION = "1.1"
TOLERANCE = 1e-5
MEASUREMENTS = {"distance": 2, "angle": 3, "dihedral": 4}
EDITS = {"set_distance", "set_angle", "set_dihedral", "translate", "rotate"}
COMMON = {"operation", "structure_file", "contact_cutoff_angstrom", "contact_options"}
FIELDS = {
    "inspect": set(),
    "measure": {"measurements", "mic", "reference_file"},
    "select_fragment": {"fragment"},
    "set_distance": {"atoms", "value"},
    "set_angle": {"atoms", "value", "plane_atoms"},
    "set_dihedral": {"atoms", "value"},
    "translate": {"vector_angstrom"},
    "rotate": {"axis", "origin_angstrom", "axis_atoms", "angle_degrees"},
}


class GeometryError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(condition, code, message):
    if not condition:
        raise GeometryError(code, message)


def finite_number(value, name):
    require(isinstance(value, (int, float)) and not isinstance(value, bool),
            "INVALID_REQUEST", f"{name} must be a finite number.")
    try:
        result = float(value)
    except OverflowError as exc:
        raise GeometryError("INVALID_REQUEST", f"{name} exceeds floating-point range.") from exc
    require(math.isfinite(result), "INVALID_REQUEST", f"{name} must be finite.")
    return result


def vector(value, name):
    require(isinstance(value, list) and len(value) == 3, "INVALID_REQUEST",
            f"{name} must contain three numbers.")
    return np.array([finite_number(x, name) for x in value])


def indices(value, count, name, length=None, allow_empty=False):
    require(isinstance(value, list), "INVALID_INDICES", f"{name} must be an array.")
    require(allow_empty or len(value) > 0, "INVALID_INDICES", f"{name} is empty.")
    require(length is None or len(value) == length, "INVALID_INDICES",
            f"{name} requires {length} distinct atom indices.")
    require(all(type(x) is int and 1 <= x <= count for x in value),
            "INVALID_INDICES", f"{name} requires integers in 1..{count} (one-based).")
    require(len(set(value)) == len(value), "INVALID_INDICES", f"{name} has duplicates.")
    return [x - 1 for x in value]


def load_structure(path):
    require(path.suffix.lower() in {".xyz", ".extxyz"}, "UNSUPPORTED_FORMAT",
            "Use a single-frame XYZ or extended XYZ file.")
    try:
        frames = read(str(path), index=":", format="extxyz")
    except Exception as exc:
        raise GeometryError("INVALID_STRUCTURE", f"Could not read XYZ: {exc}") from exc
    require(len(frames) == 1, "MULTIPLE_FRAMES", "Select one frame before calling this tool.")
    atoms = frames[0]
    require(len(atoms) > 0, "INVALID_STRUCTURE", "The structure has no atoms.")
    require(np.isfinite(atoms.positions).all() and np.isfinite(atoms.cell.array).all(),
            "INVALID_STRUCTURE", "Positions and cell must be finite.")
    require(all(x > 0 for x in atoms.numbers), "INVALID_STRUCTURE", "Dummy atoms are unsupported.")
    return atoms


def measure(atoms, kind, selected, mic=False):
    try:
        if kind == "distance":
            value = atoms.get_distance(*selected, mic=mic)
        elif kind == "angle":
            value = atoms.get_angle(*selected, mic=mic)
        else:
            value = atoms.get_dihedral(*selected, mic=mic)
    except (ValueError, ZeroDivisionError, FloatingPointError) as exc:
        raise GeometryError("DEGENERATE_GEOMETRY", f"Undefined {kind}: {exc}") from exc
    require(np.isfinite(value), "DEGENERATE_GEOMETRY", f"Undefined {kind}.")
    return float(value)


def pair_set(value, count, name):
    require(isinstance(value, list), "INVALID_REQUEST", f"{name} must be an edge list.")
    pairs = set()
    for pair in value:
        chosen = tuple(sorted(indices(pair, count, name, 2)))
        require(chosen not in pairs, "INVALID_REQUEST", f"{name} has a duplicate pair.")
        pairs.add(chosen)
    return pairs


def contact_report(atoms, cutoff, options=None):
    # Radius screening is heuristic; absolute overlap is reported even for exclusions.
    options = {} if options is None else options
    require(isinstance(options, dict) and not set(options) - {
        "radius_type", "scale", "excluded_pairs", "reactive_pairs"},
        "INVALID_REQUEST", "Unknown contact_options fields.")
    radius_type = options.get("radius_type", "covalent")
    require(isinstance(radius_type, str) and radius_type in {"covalent", "vdw"},
            "INVALID_REQUEST", "radius_type must be covalent or vdw.")
    scale = finite_number(options.get("scale", 0.8 if radius_type == "covalent" else 0.75), "scale")
    require(scale > 0, "INVALID_REQUEST", "Contact radius scale must be positive.")
    excluded = pair_set(options.get("excluded_pairs", []), len(atoms), "excluded_pairs")
    reactive = pair_set(options.get("reactive_pairs", []), len(atoms), "reactive_pairs")
    radii_table = covalent_radii if radius_type == "covalent" else vdw_radii
    radii = [float(radii_table[number]) if number < len(radii_table) else float("nan")
             for number in atoms.numbers]
    contacts = []
    use_mic = bool(atoms.pbc.any())
    for a in range(len(atoms)):
        if a + 1 == len(atoms):
            continue
        distances = atoms.get_distances(a, list(range(a + 1, len(atoms))), mic=use_mic)
        for b, distance in zip(range(a + 1, len(atoms)), distances):
            radius_sum = radii[a] + radii[b]
            ratio = float(distance / radius_sum) if np.isfinite(radius_sum) and radius_sum > 0 else None
            skip_radius = (a, b) in excluded or (a, b) in reactive
            reasons = []
            if distance < cutoff:
                reasons.append("absolute_cutoff")
            if not skip_radius and ratio is not None and ratio < scale:
                reasons.append("radius_screen")
            if reasons:
                contacts.append({"atoms": [a + 1, b + 1], "distance_angstrom": float(distance),
                                 "radius_ratio": ratio, "criteria": reasons,
                                 "reactive_pair": (a, b) in reactive,
                                 "excluded_from_radius_screen": skip_radius})
    return {"cutoff_angstrom": cutoff, "mic": use_mic,
            "radius_type": radius_type, "radius_scale": scale,
            "unavailable_radius_atoms": [i + 1 for i, r in enumerate(radii) if not np.isfinite(r) or r <= 0],
            "pairs": contacts, "is_chemical_validity_verdict": False}


def fragment_selection(spec, count, expected_cut=None, expected_seed=None):
    require(isinstance(spec, dict) and {"bonds", "seed_atom"} <= set(spec)
            and not set(spec) - {"bonds", "cut_bond", "seed_atom"},
            "INVALID_SELECTION", "fragment requires bonds and seed_atom; cut_bond is optional.")
    cut = indices(spec["cut_bond"], count, "cut_bond", 2) if "cut_bond" in spec else None
    seed = indices([spec["seed_atom"]], count, "seed_atom", 1)[0]
    if cut is not None:
        require(seed in cut, "INVALID_SELECTION", "seed_atom must be one of the cut-bond endpoints.")
    if expected_cut is not None:
        require((cut is None or set(cut) == set(expected_cut)) and seed == expected_seed,
                "INVALID_SELECTION", "Fragment cut/seed must match the moving side of this internal coordinate.")
    bonds = spec["bonds"]
    require(isinstance(bonds, list), "INVALID_SELECTION", "bonds must be an explicit edge list.")
    graph = {i: set() for i in range(count)}
    edges = set()
    for pair in bonds:
        a, b = indices(pair, count, "bond", 2)
        edge = tuple(sorted((a, b)))
        require(edge not in edges, "INVALID_SELECTION", "bonds contains a duplicate edge.")
        edges.add(edge)
        graph[a].add(b)
        graph[b].add(a)
    if cut is not None:
        require(tuple(sorted(cut)) in edges, "INVALID_SELECTION", "cut_bond is not in bonds.")
        a, b = cut
        graph[a].remove(b)
        graph[b].remove(a)
    visited, pending = set(), [seed]
    while pending:
        current = pending.pop()
        if current not in visited:
            visited.add(current)
            pending.extend(graph[current] - visited)
    if cut is not None:
        other = b if seed == a else a
        require(other not in visited, "RING_FRAGMENT", "Cut bond lies in a cycle; provide explicit moving_atoms.")
    return sorted(visited)


def selection(request, atoms, coordinate=None):
    has_list, has_fragment = "moving_atoms" in request, "fragment" in request
    require(not (has_list and has_fragment), "INVALID_SELECTION",
            "Choose moving_atoms or fragment, not both.")
    if has_list:
        moving = indices(request["moving_atoms"], len(atoms), "moving_atoms")
    elif has_fragment:
        cut, seed = None, None
        if coordinate:
            cut = coordinate[:2] if len(coordinate) == 2 else coordinate[1:3]
            seed = coordinate[1] if len(coordinate) == 2 else coordinate[2]
        moving = fragment_selection(request["fragment"], len(atoms), cut, seed)
    else:
        require(coordinate is not None, "INVALID_SELECTION", "translate/rotate require a selection.")
        moving = [coordinate[-1]]
    if coordinate:
        require(coordinate[-1] in moving, "INVALID_SELECTION", "The last coordinate atom must be selected.")
        fixed = coordinate[:-1]
        # Dihedral rotates about atoms 2--3. Axis atoms may belong to the fragment.
        if len(coordinate) == 4:
            fixed = coordinate[:1]
        require(not set(fixed).intersection(moving), "INVALID_SELECTION", "Selection includes a fixed reference atom.")
    frozen = indices(request.get("frozen_atoms", []), len(atoms), "frozen_atoms", allow_empty=True)
    require(not set(moving).intersection(frozen), "FROZEN_ATOM", "Selection includes a frozen atom.")
    return moving


def set_angle_with_plane(result, coordinate, target, moving, plane_atoms=None):
    a, b, c = coordinate
    left = result.positions[a] - result.positions[b]
    right = result.positions[c] - result.positions[b]
    require(np.linalg.norm(left) > 1e-10 and np.linalg.norm(right) > 1e-10,
            "DEGENERATE_GEOMETRY", "Angle has a zero-length arm.")
    left, right = left / np.linalg.norm(left), right / np.linalg.norm(right)
    cross = np.cross(left, right)
    if plane_atoms is not None:
        p, q, r = indices(plane_atoms, len(result), "plane_atoms", 3)
        first, second = result.positions[q] - result.positions[p], result.positions[r] - result.positions[p]
        require(np.linalg.norm(first) > 1e-10 and np.linalg.norm(second) > 1e-10,
                "DEGENERATE_GEOMETRY", "plane_atoms has coincident points.")
        normal = np.cross(first / np.linalg.norm(first), second / np.linalg.norm(second))
        require(np.linalg.norm(normal) > 1e-10, "DEGENERATE_GEOMETRY", "plane_atoms is collinear.")
        normal /= np.linalg.norm(normal)
        require(abs(np.dot(normal, left)) < 1e-7 and abs(np.dot(normal, right)) < 1e-7,
                "INVALID_PLANE", "Specified rotation plane must contain both angle-arm directions.")
    else:
        require(np.linalg.norm(cross) > 1e-10, "DEGENERATE_GEOMETRY",
                "Collinear angle needs noncollinear plane_atoms to choose a rotation plane.")
        normal = cross / np.linalg.norm(cross)
    cosine = float(np.dot(left, right))
    # Ignore signed zero at a linear starting angle: plane ordering defines the side.
    signed = (180.0 if cosine < 0 else 0.0) if np.linalg.norm(cross) <= 1e-10 else math.degrees(
        math.atan2(float(np.dot(normal, cross)), cosine))
    desired = target if signed >= 0 else -target
    group = result[moving]
    group.rotate(desired - signed, normal, center=result.positions[b])
    result.positions[moving] = group.positions


def edit_geometry(request, atoms):
    require(not atoms.pbc.any(), "PERIODIC_EDIT_UNSUPPORTED",
            "Editing requires nonperiodic, contiguous coordinates; unwrap deliberately before editing.")
    require(not atoms.constraints, "CONSTRAINTS_UNSUPPORTED",
            "ASE constraints are unsupported for edits; use explicit frozen_atoms.")
    result = atoms.copy()
    result.calc = None
    op = request["operation"]
    before, after, target, unit = None, None, None, None
    coordinate = None
    if op.startswith("set_"):
        kind = op[4:]
        coordinate = indices(request.get("atoms"), len(atoms), "atoms", MEASUREMENTS[kind])
        target = finite_number(request.get("value"), "value")
        before = measure(atoms, kind, coordinate)
        if kind == "distance":
            require(target > 0, "INVALID_REQUEST", "Distance must be positive.")
            require(before > 1e-10, "DEGENERATE_GEOMETRY", "Coincident atoms do not define a direction.")
        elif kind == "angle":
            require(0 <= target <= 180, "INVALID_REQUEST", "Target angle must be between 0 and 180 degrees.")
        else:
            target %= 360
        moving = selection(request, atoms, coordinate)
        try:
            if kind == "distance":
                result.set_distance(*coordinate, target, fix=0, indices=moving)
                unit = "angstrom"
            elif kind == "angle":
                set_angle_with_plane(result, coordinate, target, moving, request.get("plane_atoms"))
                unit = "degree"
            else:
                result.set_dihedral(*coordinate, target, indices=moving)
                unit = "degree"
        except GeometryError:
            raise
        except (ValueError, ZeroDivisionError, FloatingPointError) as exc:
            raise GeometryError("DEGENERATE_GEOMETRY", str(exc)) from exc
        after = measure(result, kind, coordinate)
        error = abs(after - target)
        if kind == "dihedral":
            error = abs((after - target + 180) % 360 - 180)
        require(error <= TOLERANCE, "POSTCONDITION_FAILED", "Edited coordinate did not reach its target.")
    else:
        moving = selection(request, atoms)
        if op == "translate":
            displacement = vector(request.get("vector_angstrom"), "vector_angstrom")
            result.positions[moving] += displacement
        else:
            if "axis_atoms" in request:
                require("axis" not in request and "origin_angstrom" not in request,
                        "INVALID_REQUEST", "Use axis_atoms or axis/origin_angstrom, not both.")
                a, b = indices(request["axis_atoms"], len(atoms), "axis_atoms", 2)
                origin = atoms.positions[a].copy()
                axis = atoms.positions[b] - origin
            else:
                axis = vector(request.get("axis"), "axis")
                origin = vector(request.get("origin_angstrom"), "origin_angstrom")
            require(np.linalg.norm(axis) > 1e-10, "INVALID_REQUEST", "Rotation axis must be nonzero.")
            degrees = finite_number(request.get("angle_degrees"), "angle_degrees")
            group = result[moving]
            group.rotate(degrees, axis, center=origin)
            result.positions[moving] = group.positions
    require(np.isfinite(result.positions).all(), "POSTCONDITION_FAILED", "Edit produced nonfinite positions.")
    fixed_indices = sorted(set(range(len(atoms))) - set(moving))
    require(np.array_equal(result.positions[fixed_indices], atoms.positions[fixed_indices]),
            "POSTCONDITION_FAILED", "An unselected atom moved.")
    displacement = np.linalg.norm(result.positions - atoms.positions, axis=1)
    report = {"selected_atoms": [i + 1 for i in moving],
              "changed_atoms": [i + 1 for i, d in enumerate(displacement) if d > 1e-10],
              "max_displacement_angstrom": float(displacement.max()),
              "unselected_atoms_unchanged": True}
    if coordinate:
        report["coordinate"] = {"kind": op[4:], "atoms": request["atoms"],
                                "before": before, "target": target, "after": after, "unit": unit}
    return result, report


def resolve_file(value, base, name):
    require(isinstance(value, str) and bool(value.strip()), "INVALID_REQUEST", f"{name} must be a path string.")
    path = Path(value)
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def execute(request, base_dir=None):
    """Python adapter interface; paths resolve relative to base_dir, or cwd."""
    if DEPENDENCY_ERROR:
        raise GeometryError("MISSING_DEPENDENCY", DEPENDENCY_ERROR)
    require(isinstance(request, dict), "INVALID_REQUEST", "Request must be a JSON object.")
    op = request.get("operation")
    require(isinstance(op, str) and op in FIELDS, "INVALID_REQUEST", "Unknown operation.")
    allowed = COMMON | FIELDS[op]
    if op in EDITS:
        allowed |= {"output_file", "moving_atoms", "fragment", "frozen_atoms"}
    require(not set(request) - allowed, "INVALID_REQUEST", f"Unknown fields: {sorted(set(request) - allowed)}")
    base = Path(base_dir or Path.cwd()).resolve()
    source = resolve_file(request.get("structure_file"), base, "structure_file")
    require(source.is_file(), "INPUT_NOT_FOUND", f"Structure not found: {source}")
    cutoff = finite_number(request.get("contact_cutoff_angstrom", 0.6), "contact_cutoff_angstrom")
    require(cutoff > 0, "INVALID_REQUEST", "Contact cutoff must be positive.")
    atoms = load_structure(source)
    contacts_before = contact_report(atoms, cutoff, request.get("contact_options"))
    response = {"schema_version": SCHEMA_VERSION, "status": "success", "operation": op,
                "atom_index_base": 1, "atom_count": len(atoms), "ase_version": ase.__version__,
                "structure_file": str(source), "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "physical_validation_performed": False}
    if op == "inspect":
        response["atoms"] = [{"index": i + 1, "element": symbol, "position_angstrom": position.tolist()}
                             for i, (symbol, position) in enumerate(zip(atoms.symbols, atoms.positions))]
        response["cell_angstrom"] = atoms.cell.array.tolist()
        response["pbc"] = atoms.pbc.tolist()
    elif op == "select_fragment":
        response["selected_atoms"] = [i + 1 for i in fragment_selection(request.get("fragment"), len(atoms))]
    elif op == "measure":
        specs = request.get("measurements")
        require(isinstance(specs, list) and len(specs) > 0, "INVALID_REQUEST", "measurements must be a nonempty array.")
        mic = request.get("mic", False)
        require(type(mic) is bool, "INVALID_REQUEST", "mic must be a boolean.")
        response["mic"] = mic
        response["measurements"] = []
        reference = None
        if "reference_file" in request:
            reference_path = resolve_file(request["reference_file"], base, "reference_file")
            require(reference_path.is_file(), "INPUT_NOT_FOUND", f"Reference not found: {reference_path}")
            reference = load_structure(reference_path)
            require(np.array_equal(atoms.numbers, reference.numbers), "REFERENCE_MISMATCH",
                    "Reference requires identical atom count, elements and ordering.")
            if mic:
                require(np.array_equal(atoms.pbc, reference.pbc)
                        and np.allclose(atoms.cell.array, reference.cell.array, atol=1e-7, rtol=0),
                        "REFERENCE_MISMATCH", "MIC comparison requires matching cells and PBC.")
            response["reference_file"] = str(reference_path)
        for spec in specs:
            require(isinstance(spec, dict) and set(spec) == {"kind", "atoms"}, "INVALID_REQUEST",
                    "Each measurement requires kind and atoms only.")
            kind = spec["kind"]
            require(isinstance(kind, str) and kind in MEASUREMENTS, "INVALID_REQUEST", "Unknown measurement kind.")
            chosen = indices(spec["atoms"], len(atoms), "atoms", MEASUREMENTS[kind])
            measured = {"kind": kind, "atoms": spec["atoms"],
                        "value": measure(atoms, kind, chosen, mic),
                        "unit": "angstrom" if kind == "distance" else "degree"}
            if reference is not None:
                measured["reference_value"] = measure(reference, kind, chosen, mic)
                delta = measured["value"] - measured["reference_value"]
                measured["delta"] = (delta + 180) % 360 - 180 if kind == "dihedral" else delta
            response["measurements"].append(measured)
    else:
        destination = resolve_file(request.get("output_file"), base, "output_file")
        require(destination != source, "INPUT_OVERWRITE", "Output must differ from input.")
        require(not destination.exists(), "OUTPUT_EXISTS", "Output already exists; choose a new filename.")
        require(destination.suffix.lower() in {".xyz", ".extxyz"}, "UNSUPPORTED_FORMAT", "Output must be .xyz or .extxyz.")
        result, response["edit"] = edit_geometry(request, atoms)
        # Verify serialization before publishing an output file; exclusive creation prevents overwrite.
        buffer = io.StringIO()
        write(buffer, result, format="extxyz", write_results=False)
        content = buffer.getvalue()
        restored = read(io.StringIO(content), format="extxyz")
        require(np.array_equal(restored.numbers, atoms.numbers)
                and np.allclose(restored.positions, result.positions, atol=1e-7, rtol=0),
                "POSTCONDITION_FAILED", "Serialization changed atom order or positions.")
        if "coordinate" in response["edit"]:
            coordinate_report = response["edit"]["coordinate"]
            chosen = [i - 1 for i in coordinate_report["atoms"]]
            saved_value = measure(restored, coordinate_report["kind"], chosen)
            error = abs(saved_value - coordinate_report["target"])
            if coordinate_report["kind"] == "dihedral":
                error = abs((saved_value - coordinate_report["target"] + 180) % 360 - 180)
            require(error <= TOLERANCE, "POSTCONDITION_FAILED", "Serialized coordinate did not retain its target.")
            coordinate_report["saved_value"] = saved_value
        response["short_contacts_before"] = contacts_before
        response["short_contacts"] = contact_report(restored, cutoff, request.get("contact_options"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        response["output_file"] = str(destination)
        response["output_format"] = "extxyz"
        response["output_sha256"] = hashlib.sha256(destination.read_bytes()).hexdigest()
        return response
    response["short_contacts"] = contacts_before
    return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, help="JSON request file, or - for stdin; file-relative paths supported.")
    args = parser.parse_args()
    try:
        if args.request == "-":
            request = json.load(sys.stdin)
            base = Path.cwd()
        else:
            request_path = Path(args.request).resolve()
            request = json.loads(request_path.read_text(encoding="utf-8-sig"))
            base = request_path.parent
        response = execute(request, base)
        code = 0
    except GeometryError as exc:
        response = {"schema_version": SCHEMA_VERSION, "status": "error",
                    "error": {"code": exc.code, "message": str(exc)}}
        code = 3 if exc.code == "MISSING_DEPENDENCY" else 2
    except (OSError, ValueError, TypeError, KeyError, ArithmeticError, RuntimeError) as exc:
        response = {"schema_version": SCHEMA_VERSION, "status": "error",
                    "error": {"code": "IO_OR_REQUEST_ERROR", "message": str(exc)}}
        code = 2
    print(json.dumps(response, ensure_ascii=True, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
