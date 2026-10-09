#!/usr/bin/env python3
"""Initialize an endpoint-preserving path with ASE IDPP, without physical energies."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

try:
    import ase
    from ase import Atoms
    from ase.constraints import FixAtoms
    from ase.geometry import find_mic
    from ase.io import read, write
    from ase.mep import NEB
    from ase.mep.neb import IDPP
    from ase.optimize import MDMin
    import numpy as np
except ImportError as exc:
    DEPENDENCY_ERROR = str(exc)
else:
    DEPENDENCY_ERROR = None

FIELDS = {"initial_file", "final_file", "output_dir", "n_internal_images", "final_atom_order",
          "id_array", "mic", "fixed_atoms", "seed_files", "fmax", "max_steps", "dt"}


class PathError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(condition, code, message):
    if not condition:
        raise PathError(code, message)


def positive(value, name):
    require(isinstance(value, (int, float)) and not isinstance(value, bool), "INVALID_REQUEST", f"{name} must be positive and finite.")
    try:
        result = float(value)
    except OverflowError as exc:
        raise PathError("INVALID_REQUEST", f"{name} exceeds numeric range.") from exc
    require(math.isfinite(result) and result > 0, "INVALID_REQUEST", f"{name} must be positive and finite.")
    return result


def indices(value, count, name):
    require(isinstance(value, list) and all(type(i) is int and 1 <= i <= count for i in value)
            and len(value) == len(set(value)), "INVALID_REQUEST", f"{name} requires distinct indices in 1..{count}.")
    return [i - 1 for i in value]


def path_value(value, base, name):
    require(isinstance(value, str) and bool(value.strip()), "INVALID_REQUEST", f"{name} requires a path.")
    return (base / value).resolve()


def load(path):
    require(path.is_file(), "INPUT_NOT_FOUND", f"File not found: {path}")
    require(path.suffix.lower() in {".xyz", ".extxyz"}, "UNSUPPORTED_FORMAT", "Use single-frame XYZ or extended XYZ.")
    try:
        frames = read(str(path), index=":", format="extxyz")
    except Exception as exc:
        raise PathError("INVALID_STRUCTURE", f"Cannot read {path}: {exc}") from exc
    require(len(frames) == 1, "MULTIPLE_FRAMES", "Each input must contain exactly one frame.")
    atoms = frames[0]
    require(len(atoms) > 0 and np.all(atoms.numbers > 0) and np.isfinite(atoms.positions).all(),
            "INVALID_STRUCTURE", "Input must have real atoms and finite coordinates.")
    require(np.isfinite(atoms.cell.array).all(), "INVALID_CELL", "Cell must be finite.")
    require(not atoms.pbc.any() or np.linalg.matrix_rank(atoms.cell.array[atoms.pbc]) == int(atoms.pbc.sum()),
            "INVALID_CELL", "Periodic cell directions must be independent.")
    require(not atoms.constraints, "CONSTRAINTS_UNSUPPORTED", "Remove stored constraints and supply fixed_atoms explicitly.")
    return atoms


def ids(atoms, name):
    array = atoms.arrays.get(name)
    require(array is not None and array.ndim == 1, "INVALID_ATOM_IDS", "Requested atom ID array is absent or not scalar.")
    values = array.tolist()
    require(all((type(v) is int and v > 0) or (isinstance(v, str) and bool(v.strip())) for v in values)
            and len(set(values)) == len(atoms), "INVALID_ATOM_IDS", "Atom IDs must be unique positive integers or nonempty strings.")
    return values


def clean(atoms, id_name):
    result = Atoms(numbers=atoms.numbers, positions=atoms.positions, cell=atoms.cell, pbc=atoms.pbc)
    if id_name:
        result.new_array(id_name, atoms.arrays[id_name].copy())
    return result


def distances(atoms, mic):
    matrix = atoms.get_all_distances(mic=mic)
    require(np.isfinite(matrix).all(), "NUMERICAL_FAILURE", "Nonfinite pair distances.")
    if len(atoms) > 1:
        require(np.min(matrix[np.triu_indices(len(atoms), 1)]) > 1e-8,
                "COINCIDENT_ATOMS", "An endpoint or intermediate image contains coincident atoms; provide a noncoincident seed path.")
    return matrix


def displacement(first, second, mic):
    vector = second.positions - first.positions
    if mic:
        vector, _ = find_mic(vector, first.cell, first.pbc)
    result = np.linalg.norm(vector, axis=1)
    require(np.isfinite(result).all(), "NUMERICAL_FAILURE", "Nonfinite inter-image displacement.")
    return result


def execute(request, base_dir=None):
    if DEPENDENCY_ERROR:
        raise PathError("MISSING_DEPENDENCY", DEPENDENCY_ERROR)
    require(isinstance(request, dict) and not set(request) - FIELDS, "INVALID_REQUEST", "Unknown request fields or non-object request.")
    base = Path(base_dir or Path.cwd()).resolve()
    initial_path = path_value(request.get("initial_file"), base, "initial_file")
    final_path = path_value(request.get("final_file"), base, "final_file")
    output = path_value(request.get("output_dir"), base, "output_dir")
    require(not output.exists(), "OUTPUT_EXISTS", "output_dir must be new; existing paths are never overwritten.")
    require(output.parent.is_dir(), "INVALID_OUTPUT", "The output parent directory must exist.")
    count = request.get("n_internal_images", 5)
    require(type(count) is int and count >= 1, "INVALID_REQUEST", "n_internal_images must be an integer >= 1.")
    steps = request.get("max_steps", 200)
    require(type(steps) is int and steps >= 0, "INVALID_REQUEST", "max_steps must be an integer >= 0.")
    fmax, dt = positive(request.get("fmax", 0.1), "fmax"), positive(request.get("dt", 0.1), "dt")
    mic = request.get("mic", False)
    require(type(mic) is bool, "INVALID_REQUEST", "mic must be a boolean.")
    id_name = request.get("id_array")
    require(id_name is None or (isinstance(id_name, str) and bool(id_name.strip()) and id_name not in {"numbers", "positions"}),
            "INVALID_REQUEST", "id_array must name a custom scalar array.")
    initial, final = load(initial_path), load(final_path)
    require(len(initial) == len(final), "ATOM_MISMATCH", "Endpoint atom counts differ.")
    order = indices(request.get("final_atom_order", list(range(1, len(final) + 1))), len(final), "final_atom_order")
    require(len(order) == len(final), "INVALID_REQUEST", "final_atom_order must be a full permutation.")
    final = final[order]
    require(np.array_equal(initial.numbers, final.numbers), "ATOM_MISMATCH", "Endpoint element order differs after permutation.")
    require(np.array_equal(initial.pbc, final.pbc) and np.allclose(initial.cell.array, final.cell.array, atol=1e-8, rtol=0),
            "CELL_MISMATCH", "Endpoints require matching cell and PBC; variable-cell paths are unsupported.")
    if id_name:
        require(ids(initial, id_name) == ids(final, id_name), "ATOM_ID_MISMATCH", "Endpoint IDs differ after permutation.")
    initial, final = clean(initial, id_name), clean(final, id_name)
    endpoint_positions = [initial.positions.copy(), final.positions.copy()]
    fixed = indices(request.get("fixed_atoms", []), len(initial), "fixed_atoms")
    require(not fixed or np.allclose(initial.positions[fixed], final.positions[fixed], atol=1e-8, rtol=0),
            "FIXED_ATOM_MISMATCH", "Fixed atoms must have matching endpoint Cartesian positions.")
    require(np.max(displacement(initial, final, mic)) > 1e-8, "NO_PATH_CHANGE", "Endpoints have no resolvable displacement under the selected convention.")
    target_initial, target_final = distances(initial, mic), distances(final, mic)
    seeds = request.get("seed_files")
    if seeds is not None:
        require(isinstance(seeds, list) and len(seeds) == count, "INVALID_REQUEST", "seed_files must contain n_internal_images paths, in path order.")
        interior = []
        for value in seeds:
            seed = load(path_value(value, base, "seed_files"))
            require(np.array_equal(seed.numbers, initial.numbers), "ATOM_MISMATCH", "Seed atom order must match initial order.")
            require(np.array_equal(seed.pbc, initial.pbc) and np.allclose(seed.cell.array, initial.cell.array, atol=1e-8, rtol=0),
                    "CELL_MISMATCH", "Seed cell/PBC differs.")
            if id_name:
                require(ids(seed, id_name) == ids(initial, id_name), "ATOM_ID_MISMATCH", "Seed IDs differ from initial order.")
            seed = clean(seed, id_name)
            require(not fixed or np.allclose(seed.positions[fixed], initial.positions[fixed], atol=1e-8, rtol=0),
                    "FIXED_ATOM_MISMATCH", "Seed moves fixed atoms.")
            interior.append(seed)
    else:
        interior = [initial.copy() for _ in range(count)]
    images = [initial] + interior + [final]
    for image in images:
        if fixed:
            image.set_constraint(FixAtoms(indices=fixed))
    # Pin method and disable alignment so endpoint coordinates remain authoritative.
    neb = NEB(images, method="aseneb", climb=False, remove_rotation_and_translation=False)
    if seeds is None:
        neb.interpolate(method="linear", mic=mic, apply_constraint=True)
    for image in images:
        distances(image, mic)
    for left, right in zip(images[:-1], images[1:]):
        require(np.max(displacement(left, right, mic)) > 1e-8, "DEGENERATE_PATH", "Adjacent seed images coincide; revise the seed path.")
    for index, image in enumerate(images):
        fraction = index / (len(images) - 1)
        image.calc = IDPP((1 - fraction) * target_initial + fraction * target_final, mic=mic)
    try:
        with MDMin(neb, dt=dt, logfile=None, trajectory=None) as optimizer:
            def validate():
                for image in images:
                    require(np.isfinite(image.positions).all(), "NUMERICAL_FAILURE", "IDPP produced nonfinite coordinates.")
                    distances(image, mic)
            optimizer.attach(validate, interval=1)
            converged = bool(optimizer.run(fmax=fmax, steps=steps))
            steps_used = optimizer.nsteps
        forces = neb.get_forces()
        require(np.isfinite(forces).all(), "NUMERICAL_FAILURE", "IDPP produced nonfinite forces.")
        max_force = float(np.max(np.linalg.norm(forces, axis=1)))
    except PathError:
        raise
    except (ValueError, ArithmeticError, RuntimeError, np.linalg.LinAlgError) as exc:
        raise PathError("NUMERICAL_FAILURE", f"IDPP failed: {exc}") from exc
    require(np.array_equal(images[0].positions, endpoint_positions[0]) and np.array_equal(images[-1].positions, endpoint_positions[1]),
            "POSTCONDITION_FAILED", "Endpoint positions changed.")
    # MDMin only optimizes internal images; verify explicit fixed positions too.
    require(not fixed or all(np.allclose(image.positions[fixed], initial.positions[fixed], atol=1e-8, rtol=0) for image in images),
            "POSTCONDITION_FAILED", "Fixed positions changed.")
    diagnostics, spacing = [], []
    for index, image in enumerate(images):
        matrix = distances(image, mic)
        if len(image) > 1:
            a, b = np.triu_indices(len(image), 1)
            closest = int(np.argmin(matrix[a, b]))
            minimum, pair = float(matrix[a[closest], b[closest]]), [int(a[closest]) + 1, int(b[closest]) + 1]
        else:
            minimum, pair = None, None
        diagnostics.append({"image_index": index, "min_distance_angstrom": minimum, "closest_atoms": pair})
        if index:
            disp = displacement(images[index - 1], image, mic)
            spacing.append({"from_image": index - 1, "to_image": index, "max_atom_displacement_angstrom": float(np.max(disp)),
                            "rms_atom_displacement_angstrom": float(np.sqrt(np.mean(disp ** 2)))})
        image.calc = None
    paths = []
    created = False
    try:
        output.mkdir(exist_ok=False)
        created = True
        for index, image in enumerate(images):
            path = output / f"image-{index:03d}.extxyz"
            paths.append(path)
            write(path, clean(image, id_name), format="extxyz", write_results=False)
            saved = load(path)
            distances(saved, mic)
            require(np.array_equal(saved.numbers, image.numbers) and np.allclose(saved.positions, image.positions, atol=1e-7, rtol=0),
                    "POSTCONDITION_FAILED", "Saved image does not preserve generated geometry.")
            if id_name:
                require(ids(saved, id_name) == ids(image, id_name), "POSTCONDITION_FAILED", "Saved IDs changed.")
    except Exception:
        if created:
            for path in paths:
                if path.is_file():
                    path.unlink()
            output.rmdir()
        raise
    return {"schema_version": "1.0", "status": "success", "ase_version": ase.__version__,
            "initial_file": str(initial_path), "final_file": str(final_path), "output_dir": str(output),
            "atom_index_base": 1, "image_index_base": 0, "atom_count": len(initial), "n_internal_images": count,
            "image_files": [str(p) for p in paths], "final_atom_order": [i + 1 for i in order],
            "stable_ids_checked": id_name is not None, "mic": mic, "fixed_atoms": [i + 1 for i in fixed],
            "endpoints_preserved": True, "fixed_atoms_preserved": True, "physical_validation_performed": False,
            "initialization": "supplied_seeds" if seeds is not None else "linear",
            "idpp": {"converged": converged, "steps_used": steps_used, "max_steps": steps, "fmax": fmax,
                     "max_force": max_force, "force_convention": "ASE artificial IDPP/NEB optimizer units; not physical forces",
                     "optimizer": "MDMin", "dt": dt, "neb_method": "aseneb"},
            "image_diagnostics": diagnostics, "adjacent_spacing": spacing,
            "warnings": [] if converged else [{"code": "IDPP_NOT_CONVERGED", "message": "Step limit reached; saved finite path requires review."}]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, help="JSON file or - for stdin.")
    args = parser.parse_args()
    try:
        if args.request == "-":
            request, base = json.load(sys.stdin), Path.cwd()
        else:
            path = Path(args.request).resolve()
            request, base = json.loads(path.read_text(encoding="utf-8-sig")), path.parent
        response, code = execute(request, base), 0
    except PathError as exc:
        response = {"status": "error", "error": {"code": exc.code, "message": str(exc)}}
        code = 3 if exc.code == "MISSING_DEPENDENCY" else 2
    except (OSError, ValueError, TypeError, ArithmeticError, RuntimeError) as exc:
        response = {"status": "error", "error": {"code": "IO_OR_REQUEST_ERROR", "message": str(exc)}}
        code = 2
    print(json.dumps(response, allow_nan=False, ensure_ascii=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
