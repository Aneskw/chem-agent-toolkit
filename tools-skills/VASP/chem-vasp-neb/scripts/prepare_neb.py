"""Prepare native VASP NEB inputs from ordered images; never execute VASP."""
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
    from ase.io import read, write

    allowed = {"image_files", "output_dir", "parameters", "engine", "climb", "fixed_atoms"}
    if not isinstance(request, dict) or set(request) - allowed:
        raise ValueError("Unknown request fields; see references/api.md")
    engine = request.get("engine", "stock")
    climb = request.get("climb", False)
    if engine not in ("stock", "vtst") or type(climb) is not bool:
        raise ValueError("engine must be stock/vtst and climb must be boolean")
    if climb and engine != "vtst":
        raise ValueError("Native climbing image requires a verified VTST build")
    paths = request["image_files"]
    if not isinstance(paths, list) or not 3 <= len(paths) <= 100:
        raise ValueError("Provide endpoints and 1..98 internal images in order")
    sources = [(base / p).resolve() for p in paths]
    output = (base / request["output_dir"]).resolve()
    if output.exists() or not output.parent.is_dir():
        raise ValueError("output_dir must be new, with an existing parent")
    images = []
    fixed_sets = []
    for source in sources:
        frames = read(str(source), index=":")
        if len(frames) != 1:
            raise ValueError("Every image must be single-frame")
        atoms = frames[0]
        if (not len(atoms) or not np.isfinite(atoms.positions).all() or
                not np.isfinite(atoms.cell.array).all() or
                abs(np.linalg.det(atoms.cell.array)) < 1e-10 or not atoms.pbc.all()):
            raise ValueError("Every image needs finite coordinates and a full-rank 3D periodic cell")
        frozen = set()
        for constraint in atoms.constraints:
            if not isinstance(constraint, FixAtoms):
                raise ValueError("Helper supports FixAtoms only")
            frozen.update(int(i) for i in constraint.get_indices())
        images.append(atoms)
        fixed_sets.append(frozen)
    initial = images[0]
    extra = request.get("fixed_atoms", [])
    if (not isinstance(extra, list) or len(extra) != len(set(extra)) or
            any(type(i) is not int or i < 1 or i > len(initial) for i in extra)):
        raise ValueError("fixed_atoms must contain unique one-based indices")
    for frozen in fixed_sets:
        frozen.update(i - 1 for i in extra)
    fixed = fixed_sets[0]
    if len(fixed) == len(initial):
        raise ValueError("No movable atoms")
    for image, frozen in zip(images, fixed_sets):
        if image.get_chemical_symbols() != initial.get_chemical_symbols():
            raise ValueError("Images must have identical element order and supplied atom correspondence")
        if not np.allclose(image.cell.array, initial.cell.array, rtol=0, atol=1e-8):
            raise ValueError("Variable-cell paths are unsupported")
        if frozen != fixed:
            raise ValueError("All images must have the same fixed-atom mask")
        if fixed and not np.allclose(image.positions[sorted(fixed)], initial.positions[sorted(fixed)], rtol=0, atol=1e-8):
            raise ValueError("Fixed coordinates must match in every image")
        if not np.allclose(image.get_initial_magnetic_moments(), initial.get_initial_magnetic_moments(), rtol=0, atol=1e-8):
            raise ValueError("Use consistent initial magnetic moments across images")
        image.set_constraint(FixAtoms(indices=sorted(fixed)) if fixed else [])
    raw = request["parameters"]
    if not isinstance(raw, dict) or any(not isinstance(k, str) for k in raw):
        raise ValueError("parameters must be an ASE Vasp keyword object")
    params = {k.lower(): v for k, v in raw.items()}
    if len(params) != len(raw):
        raise ValueError("Duplicate parameter names after lowercasing")
    reserved = {"atoms", "directory", "label", "command", "txt", "restart",
                "ignore_bad_restart_file", "ignore_constraints", "custom", "kspacing",
                "lnebcell", "ltangentold", "ldneb", "ldneborg"}
    if set(params) & reserved:
        raise ValueError("Execution, custom tags, kspacing and advanced chain options are unsupported")
    for key in ("xc", "encut", "ediff", "ispin", "kpts", "nsw", "ediffg"):
        if key not in params:
            raise ValueError(f"Supply {key} explicitly")
    for key in ("encut", "ediff"):
        v = params[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError(f"{key} must be finite and positive")
    if not isinstance(params["xc"], str) or not params["xc"].strip():
        raise ValueError("xc must name an ASE functional recipe")
    if type(params["ispin"]) is not int or params["ispin"] not in (1, 2):
        raise ValueError("ispin must be 1 or 2")
    if type(params["nsw"]) is not int or params["nsw"] < 1:
        raise ValueError("nsw must be a positive ionic-step budget")
    if not isinstance(params["ediffg"], (int, float)) or not math.isfinite(params["ediffg"]) or params["ediffg"] >= 0:
        raise ValueError("ediffg must be negative (force criterion)")
    mesh = params["kpts"]
    if not isinstance(mesh, list) or len(mesh) != 3 or any(type(i) is not int or i < 1 for i in mesh):
        raise ValueError("Helper requires a positive three-integer kpts mesh")
    if "setups" in params and isinstance(params["setups"], dict):
        if any(str(k).isdigit() for k in params["setups"]):
            raise ValueError("Indexed setups unsupported; use per-element setups")
    mode = {"images": len(images) - 2, "isif": 2}
    if engine == "stock":
        if set(params) & {"iopt", "ichain", "lclimb", "maxmove"}:
            raise ValueError("VTST tags cannot be used with stock VASP")
        ib = params.get("ibrion", 1)
        if ib not in (1, 3):
            raise ValueError("Stock NEB supports ibrion 1 or 3 in this helper")
        step = params.get("potim", 0.1)
        if not isinstance(step, (int, float)) or not math.isfinite(step) or step <= 0:
            raise ValueError("Stock NEB needs positive potim; zero disables ionic motion")
        params.setdefault("ibrion", 1)
        params.setdefault("potim", 0.1)
        if ib == 1:
            params.setdefault("nfree", 2)
    else:
        mode.update({"ibrion": 3, "potim": 0.0, "ichain": 0, "lclimb": climb})
        iopt = params.get("iopt", 3)
        if type(iopt) is not int or iopt not in (1, 2, 3, 4, 7):
            raise ValueError("VTST iopt must be 1, 2, 3, 4 or 7")
        params.setdefault("iopt", 3)
    spring = params.get("spring", -5.0)
    if not isinstance(spring, (int, float)) or not math.isfinite(spring) or spring >= 0:
        raise ValueError("spring must be finite and negative to activate NEB")
    params.setdefault("spring", -5.0)
    for key, value in mode.items():
        if key in params and params[key] != value:
            raise ValueError(f"Requested mode requires {key}={value}")
        params[key] = value
    calc = Vasp(**params)
    with tempfile.TemporaryDirectory(prefix=".neb-prepare-", dir=output.parent) as tmp:
        staging = Path(tmp) / "job"
        staging.mkdir()
        calc.directory = str(staging)
        calc.write_input(initial)
        common = ("INCAR", "KPOINTS", "POTCAR")
        for name in common:
            if not (staging / name).is_file() or (staging / name).stat().st_size == 0:
                raise ValueError(f"Missing or empty generated {name}")
        # Use the SAME ASE permutation and POTCAR species blocks for EVERY image.
        for index, image in enumerate(images):
            target = staging / f"{index:02d}"
            target.mkdir()
            write(str(target / "POSCAR"), image[calc.sort], format="vasp",
                  symbol_count=calc.symbol_count, vasp5=True)
            (target / "ase-sort.dat").write_bytes((staging / "ase-sort.dat").read_bytes())
            saved = read(str(target / "POSCAR"))
            if saved.get_chemical_symbols() != image[calc.sort].get_chemical_symbols() or not np.allclose(saved.positions, image.positions[calc.sort], rtol=0, atol=1e-8):
                raise ValueError("Saved image coordinates/order changed")
            if not np.allclose(saved.cell.array, image.cell.array, rtol=0, atol=1e-8):
                raise ValueError("Saved image cell changed")
            saved_fixed = sorted(i for c in saved.constraints for i in c.get_indices())
            if saved_fixed != sorted(pos for pos, original in enumerate(calc.sort) if original in fixed):
                raise ValueError("Saved fixed-atom mask changed")
        (staging / "POSCAR").unlink()
        (staging / "ase-sort.dat").unlink()
        manifest = {"status": "success", "stage": "inputs_prepared", "vasp_executed": False,
                    "ase_version": ase.__version__, "engine": engine, "climb": climb,
                    "engine_capability_verified": False, "n_internal_images": len(images) - 2,
                    "source_files": [str(p) for p in sources], "output_dir": str(output),
                    "parameters": params, "fixed_atoms": [i + 1 for i in sorted(fixed)],
                    "poscar_to_input_atom": [int(i) + 1 for i in calc.sort],
                    "input_to_poscar_atom": [int(i) + 1 for i in calc.resort],
                    "potcar_sha256": hashlib.sha256((staging / "POTCAR").read_bytes()).hexdigest(),
                    "image_files": [str(output / f"{i:02d}" / "POSCAR") for i in range(len(images))],
                    "warnings": ["Atom identity is supplied; identical elements do not prove correspondence",
                                 "Endpoints must be optimized independently with comparable settings"]}
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
