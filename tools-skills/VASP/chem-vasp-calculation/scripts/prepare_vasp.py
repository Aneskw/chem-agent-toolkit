"""Prepare single-structure inputs through ASE; never execute VASP."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile


def prepare(request, base):
    import numpy as np
    import ase
    from ase.calculators.vasp import Vasp
    from ase.constraints import FixAtoms
    from ase.io import read

    allowed = {"task", "structure_file", "output_dir", "parameters", "fixed_atoms"}
    if not isinstance(request, dict) or set(request) - allowed:
        raise ValueError("Unknown request fields; see references/api.md")
    task = request.get("task")
    if task not in {"singlepoint", "relax", "vibrations"}:
        raise ValueError("task must be singlepoint, relax or vibrations")
    source = (base / request["structure_file"]).resolve()
    output = (base / request["output_dir"]).resolve()
    if output.exists() or not output.parent.is_dir():
        raise ValueError("output_dir must be new, with an existing parent")
    frames = read(str(source), index=":")
    if len(frames) != 1:
        raise ValueError("Expected exactly one structure")
    atoms = frames[0]
    if not len(atoms) or not np.isfinite(atoms.positions).all():
        raise ValueError("Empty structure or nonfinite coordinates")
    if (not np.isfinite(atoms.cell.array).all() or
            abs(np.linalg.det(atoms.cell.array)) < 1e-10 or not atoms.pbc.all()):
        raise ValueError("VASP needs a finite full-rank cell and PBC in all three directions")
    fixed = set()
    for constraint in atoms.constraints:
        if not isinstance(constraint, FixAtoms):
            raise ValueError("Helper supports FixAtoms only; use ASE directly for other constraints")
        fixed.update(int(i) for i in constraint.get_indices())
    extra = request.get("fixed_atoms", [])
    if (not isinstance(extra, list) or len(extra) != len(set(extra)) or
            any(type(i) is not int or i < 1 or i > len(atoms) for i in extra)):
        raise ValueError("fixed_atoms must contain unique one-based indices")
    fixed.update(i - 1 for i in extra)
    if task != "singlepoint" and len(fixed) == len(atoms):
        raise ValueError("No movable atoms")
    atoms.set_constraint(FixAtoms(indices=sorted(fixed)) if fixed else [])
    raw = request["parameters"]
    if not isinstance(raw, dict) or any(not isinstance(k, str) for k in raw):
        raise ValueError("parameters must be an ASE Vasp keyword object")
    params = {k.lower(): v for k, v in raw.items()}
    if len(params) != len(raw):
        raise ValueError("Duplicate parameter names after lowercasing")
    reserved = {"atoms", "directory", "label", "command", "txt", "restart",
                "ignore_bad_restart_file", "ignore_constraints", "custom",
                "images", "lclimb", "iopt", "ichain", "kspacing"}
    if set(params) & reserved:
        raise ValueError("Execution, custom tags, NEB and kspacing parameters are unsupported")
    for key in ("xc", "encut", "ediff", "ispin", "kpts"):
        if key not in params:
            raise ValueError(f"Supply {key} explicitly; physical settings are not inferred")
    for key in ("encut", "ediff"):
        value = params[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key} must be finite and positive")
    if not isinstance(params["xc"], str) or not params["xc"].strip():
        raise ValueError("xc must name an ASE functional recipe")
    if type(params["ispin"]) is not int or params["ispin"] not in (1, 2):
        raise ValueError("ispin must be 1 or 2; supply magnetic moments when needed")
    mesh = params["kpts"]
    if not isinstance(mesh, list) or len(mesh) != 3 or any(type(i) is not int or i < 1 for i in mesh):
        raise ValueError("Helper requires kpts:[nx,ny,nz] with positive integers")
    if "setups" in params and isinstance(params["setups"], dict):
        if any(str(k).isdigit() for k in params["setups"]):
            raise ValueError("Indexed setups are unsupported; use per-element setups or ASE directly")
    if task == "singlepoint":
        mode = {"ibrion": -1, "nsw": 0}
    elif task == "relax":
        if type(params.get("nsw")) is not int or params["nsw"] < 1:
            raise ValueError("relax requires a positive nsw budget")
        if not isinstance(params.get("ediffg"), (int, float)) or not math.isfinite(params["ediffg"]) or params["ediffg"] >= 0:
            raise ValueError("relax requires negative ediffg (force criterion)")
        if params.get("ibrion", 2) not in (1, 2):
            raise ValueError("relax supports ibrion 1 or 2")
        mode = {"isif": 2, "ibrion": params.get("ibrion", 2)}
    else:
        ib = params.get("ibrion", 5 if fixed else 6)
        if ib not in (5, 6) or (fixed and ib != 5):
            raise ValueError("vibrations supports 5/6; selective dynamics requires 5")
        if params["ediff"] > 1e-6:
            raise ValueError("Use ediff <= 1e-6 for this finite-difference helper")
        if params.get("nfree", 2) not in (2, 4):
            raise ValueError("vibrations supports nfree 2 or 4")
        step = params.get("potim", 0.015)
        if not isinstance(step, (int, float)) or not math.isfinite(step) or step <= 0:
            raise ValueError("Finite-difference potim must be positive")
        mode = {"ibrion": ib, "nsw": 1, "isif": 2}
        params.setdefault("nfree", 2)
        params.setdefault("potim", 0.015)
    for key, value in mode.items():
        if key in params and params[key] != value:
            raise ValueError(f"{task} requires {key}={value}")
        params[key] = value
    calc = Vasp(**params)
    warnings = []
    if fixed and task == "vibrations":
        warnings.append("Partial Hessian: only unfrozen degrees of freedom are probed")
    if task == "vibrations":
        warnings.append("Frequency generation is not a TS or reaction-connectivity verdict")
    with tempfile.TemporaryDirectory(prefix=".vasp-prepare-", dir=output.parent) as tmp:
        staging = Path(tmp) / "job"
        staging.mkdir()
        calc.directory = str(staging)
        calc.write_input(atoms)
        required = ("INCAR", "POSCAR", "KPOINTS", "POTCAR", "ase-sort.dat")
        for name in required:
            if not (staging / name).is_file() or (staging / name).stat().st_size == 0:
                raise ValueError(f"Missing or empty generated {name}")
        saved = read(str(staging / "POSCAR"))
        if saved.get_chemical_symbols() != atoms[calc.sort].get_chemical_symbols() or not np.allclose(saved.positions, atoms.positions[calc.sort], rtol=0, atol=1e-8):
            raise ValueError("Saved POSCAR does not preserve coordinates/order")
        if not np.allclose(saved.cell.array, atoms.cell.array, rtol=0, atol=1e-8):
            raise ValueError("Saved POSCAR does not preserve the cell")
        saved_fixed = sorted(i for c in saved.constraints for i in c.get_indices())
        expected_fixed = sorted(pos for pos, original in enumerate(calc.sort) if original in fixed)
        if saved_fixed != expected_fixed:
            raise ValueError("Saved selective dynamics does not preserve fixed atoms")
        manifest = {"status": "success", "stage": "inputs_prepared", "task": task,
                    "vasp_executed": False, "ase_version": ase.__version__,
                    "source_file": str(source), "output_dir": str(output),
                    "parameters": params, "fixed_atoms": [i + 1 for i in sorted(fixed)],
                    "poscar_to_input_atom": [int(i) + 1 for i in calc.sort],
                    "input_to_poscar_atom": [int(i) + 1 for i in calc.resort],
                    "potcar_sha256": hashlib.sha256((staging / "POTCAR").read_bytes()).hexdigest(),
                    "files": [str(output / name) for name in required], "warnings": warnings}
        (staging / "input-manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
        staging.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    args = parser.parse_args()
    try:
        if args.request == "-":
            request, base = json.load(sys.stdin), Path.cwd()
        else:
            path = Path(args.request).resolve()
            request, base = json.loads(path.read_text(encoding="utf-8-sig")), path.parent
        result = prepare(request, base)
    except ImportError as exc:
        print(json.dumps({"status": "error", "error": "MISSING_DEPENDENCY", "message": str(exc)}))
        return 3
    except Exception as exc:
        print(json.dumps({"status": "error", "error": "PREPARATION_FAILED", "message": str(exc)}))
        return 2
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
