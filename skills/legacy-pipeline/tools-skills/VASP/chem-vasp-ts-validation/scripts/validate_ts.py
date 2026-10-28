"""Prepare, run or inspect VASP frequency evidence for a supplied TS candidate."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile

NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[EeDd][-+]?\d+)?"
MEV_PER_CM1 = 0.12398419843320026


def number(value):
    result = float(value.replace("D", "E").replace("d", "e"))
    if not math.isfinite(result):
        raise ValueError("Nonfinite numeric output")
    return result


def text(path):
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def last_run(content):
    headers = list(re.finditer(r"(?m)^\s*vasp\.\d", content))
    return content[headers[-1].start():] if headers else content


def incar(content):
    tags = {}
    for line in content.splitlines():
        for field in line.split("!", 1)[0].split("#", 1)[0].split(";"):
            match = re.match(r"\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", field)
            if match:
                tags[match[1].upper()] = match[2]
    return tags


def scf_evidence(content):
    exits = re.findall(r"(?im)^.*aborting loop.*$", content)
    failures = re.search(r"EDIFF was not reached|BRMIX:\s*very serious|ZHEGV.*failed|EDDDAV.*failed", content, re.I)
    if failures or any("because ediff is reached" not in line.lower() for line in exits):
        return False
    return True if exits else None


def coordinate_rows(lines, start, n, width):
    rows = []
    for line in lines[start:]:
        fields = line.split()
        if not rows and (not fields or set(line.strip()) <= {"-"} or fields[0] in ("X", "x")):
            continue
        if len(fields) < width:
            break
        try:
            row = [number(v) for v in fields[:width]]
        except ValueError:
            break
        rows.append(row)
        if len(rows) == n:
            return rows
    return None


def mask_for(atoms):
    import numpy as np
    from ase.constraints import FixAtoms, FixScaled
    mask = np.zeros((len(atoms), 3), dtype=bool)
    for constraint in atoms.constraints:
        if isinstance(constraint, FixAtoms):
            mask[constraint.get_indices()] = True
        elif isinstance(constraint, FixScaled):
            mask[constraint.get_indices()] |= constraint.mask
        else:
            raise ValueError("Only POSCAR-compatible FixAtoms/FixScaled constraints are supported")
    return mask


def reaction_pairs(request, atoms):
    order = request.get("reaction_atom_order", "poscar")
    mapping = request.get("input_to_poscar_atom")
    bonds = request.get("reaction_bonds", [])
    if order not in ("poscar", "input") or not isinstance(bonds, list):
        raise ValueError("reaction_atom_order must be poscar/input; reaction_bonds must be a list")
    if order == "input" and mapping is None:
        raise ValueError("Input-order reaction pairs require input_to_poscar_atom")
    if mapping is not None:
        if order != "input" or atoms is None:
            raise ValueError("Supply reaction_atom_order:input and POSCAR with an atom mapping")
        if (not isinstance(mapping, list) or len(mapping) != len(atoms) or
                any(type(i) is not int for i in mapping) or set(mapping) != set(range(1, len(atoms) + 1))):
            raise ValueError("input_to_poscar_atom must be a complete one-based permutation")
    if bonds and atoms is None:
        raise ValueError("reaction_bonds requires POSCAR")
    resolved = []
    for bond in bonds:
        if not isinstance(bond, dict) or set(bond) != {"atoms", "change"} or bond["change"] not in ("forming", "breaking"):
            raise ValueError("reaction_bonds entries need atoms:[i,j] and change:forming/breaking")
        pair = bond["atoms"]
        if not isinstance(pair, list) or len(pair) != 2 or pair[0] == pair[1] or any(type(v) is not int or not 1 <= v <= len(atoms) for v in pair):
            raise ValueError("Reaction pairs use distinct one-based atom indices")
        converted = [mapping[i - 1] for i in pair] if order == "input" else list(pair)
        resolved.append({"atoms": converted, "requested_atoms": list(pair),
                         "elements": [atoms[i - 1].symbol for i in converted], "change": bond["change"]})
    return {"reaction_atom_order": order, "input_to_poscar_atom": mapping,
            "resolved_reaction_bonds": resolved}


def inspect(request, base):
    import numpy as np
    from ase.io import read
    from ase.geometry import find_mic

    directory = (base / request["calculation_dir"]).resolve()
    content = last_run(text(directory / "OUTCAR"))
    tags = incar(text(directory / "INCAR"))
    threshold = request.get("imaginary_threshold_cm1", 10.0)
    force_limit = request.get("force_tolerance_ev_per_angstrom", 0.05)
    motion_limit = request.get("mode_motion_tolerance", 1e-6)
    for value in (threshold, force_limit, motion_limit):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError("Thresholds must be finite and positive")
    findings, next_actions = [], []
    complete = bool(re.search(r"General timing and accounting informations|Elapsed time\s*\(", content))
    electronic = scf_evidence(content)
    poscar = directory / "POSCAR"
    atoms = read(poscar) if poscar.is_file() else None
    expected = None
    partial = None
    if atoms is not None:
        if not len(atoms) or not np.isfinite(atoms.positions).all():
            raise ValueError("Invalid candidate POSCAR")
        mask = mask_for(atoms)
        partial = bool(mask.any())
        expected = int((~mask).sum())
    atom_indexing = reaction_pairs(request, atoms)
    ib = tags.get("IBRION", "")
    frequency_mode = ib in ("5", "6")
    constraint_mode_valid = (not partial or ib == "5") if atoms is not None else None
    modes = []
    lines = content.splitlines()
    # A repeated spectrum is not a complete single calculation: use its last block.
    headers = [i for i, line in enumerate(lines) if "Eigenvectors and eigenvalues of the dynamical matrix" in line]
    if headers:
        lines = lines[headers[-1] + 1:]
    for i, line in enumerate(lines):
        match = re.match(r"\s*(\d+)\s+(f/i|f)\s*=.*?([+-]?(?:\d+\.?\d*|\.\d+)(?:[EeDd][+-]?\d+)?)\s+meV\b", line)
        if not match:
            continue
        magnitude = abs(number(match[3]))
        mode = {"index": int(match[1]), "imaginary": match[2] == "f/i",
                "magnitude_mev": magnitude, "magnitude_cm1": magnitude / MEV_PER_CM1}
        if atoms is not None:
            rows = coordinate_rows(lines, i + 1, len(atoms), 6)
            if rows:
                positions = np.array(rows)[:, :3]
                delta, _ = find_mic(positions - atoms.positions, atoms.cell, pbc=atoms.pbc)
                if np.max(np.abs(delta)) <= 1e-5:
                    mode["vectors"] = np.array(rows)[:, 3:].tolist()
        modes.append(mode)
    observed_ids = [mode["index"] for mode in modes]
    spectrum_complete = (observed_ids == list(range(1, expected + 1))) if expected is not None and expected > 0 else None
    imaginary = [mode for mode in modes if mode["imaginary"]]
    significant = [mode for mode in imaginary if mode["magnitude_cm1"] >= threshold]
    force_source = (base / request["stationary_outcar"]).resolve() if "stationary_outcar" in request else directory / "OUTCAR"
    force_content = last_run(text(force_source))
    force_lines = force_content.splitlines()
    matching = []
    if atoms is not None:
        for i, line in enumerate(force_lines):
            if "TOTAL-FORCE" not in line:
                continue
            rows = coordinate_rows(force_lines, i + 1, len(atoms), 6)
            if rows:
                rows = np.array(rows)
                delta, _ = find_mic(rows[:, :3] - atoms.positions, atoms.cell, pbc=atoms.pbc)
                if np.max(np.abs(delta)) <= 1e-5:
                    forces = rows[:, 3:].copy()
                    forces[mask_for(atoms)] = 0
                    matching.append(float(np.linalg.norm(forces, axis=1).max()))
    # The initial unperturbed force table is appropriate for a frequency run;
    # an explicitly supplied stationary source uses its last matching table.
    max_force = (matching[-1] if "stationary_outcar" in request else matching[0]) if matching else None
    stationary = max_force <= force_limit if max_force is not None else None
    force_scf = scf_evidence(force_content) if "stationary_outcar" in request else electronic
    checks = {"run_completed": complete, "frequency_mode": frequency_mode if tags else None,
              "constraints_respected_by_frequency_mode": constraint_mode_valid,
              "electronic_convergence_explicit": electronic, "spectrum_complete": spectrum_complete,
              "stationary_force_source_scf": force_scf, "stationary_forces_small": stationary,
              "one_significant_imaginary_mode": len(significant) == 1 if spectrum_complete else None}
    evidence_keys = ("run_completed", "frequency_mode", "constraints_respected_by_frequency_mode",
                     "electronic_convergence_explicit", "spectrum_complete", "stationary_force_source_scf")
    # Failed/incomplete calculations are missing physical evidence, not proof of
    # a wrong chemical mechanism. Only complete evidence supports a local verdict.
    local = (bool(stationary and len(significant) == 1) if
             all(checks[key] is True for key in evidence_keys) and stationary is not None else None)
    reaction_checks = None
    bonds = atom_indexing["resolved_reaction_bonds"]
    if bonds:
        if len(significant) == 1 and "vectors" in significant[0]:
            vectors = np.array(significant[0]["vectors"])
            scale = float(np.linalg.norm(vectors, axis=1).max())
            rates = []
            if scale > 0:
                vectors /= scale
            for bond in bonds:
                a, b = [i - 1 for i in bond["atoms"]]
                displacement, _ = find_mic(atoms.positions[b] - atoms.positions[a], atoms.cell, pbc=atoms.pbc)
                length = float(np.linalg.norm(displacement))
                if length < 1e-8:
                    raise ValueError("Coincident reaction pair")
                derivative = float(np.dot(displacement / length, vectors[b] - vectors[a]))
                rates.append({**bond, "distance_derivative": derivative})
            signed = [(-1 if bond["change"] == "forming" else 1) * rate["distance_derivative"]
                      for bond, rate in zip(bonds, rates)]
            strong = [value for value in signed if abs(value) > motion_limit]
            conflicting = any(v > 0 for v in strong) and any(v < 0 for v in strong)
            orientation = max((1, -1), key=lambda sign: min((v * sign for v in strong), default=0))
            compatible = False if conflicting else (True if len(strong) == len(signed) else None)
            for rate, value in zip(rates, signed):
                rate["motion_status"] = ("unresolved" if abs(value) <= motion_limit else
                                         "expected" if value * orientation > 0 else "opposite")
            reaction_checks = {"compatible": compatible,
                               "assessment": "conflicting_motion" if conflicting else "compatible" if compatible else "insufficient_motion",
                               "orientation": orientation, "mode_motion_tolerance": motion_limit,
                               "bond_derivatives": rates,
                               "interpretation": "Qualitative local mode motion; weak/zero motion is inconclusive, not proof of a wrong mechanism"}
    if not content:
        findings.append("MISSING_FREQUENCY_OUTPUT")
        next_actions.append("If frequency evidence is required, prepare it at the supplied candidate using the same physical model")
    elif not complete:
        findings.append("FREQUENCY_RUN_INCOMPLETE")
        next_actions.append("Inspect runtime logs; complete the calculation before interpreting frequencies")
    if electronic is not True:
        findings.append("SCF_NOT_CONVERGED" if electronic is False else "SCF_EVIDENCE_UNAVAILABLE")
        next_actions.append("Check SCF exit records for displaced geometries; unsupported output remains unknown")
    if spectrum_complete is not True:
        findings.append("SPECTRUM_INCOMPLETE_OR_SCOPE_UNKNOWN")
    elif len(significant) != 1:
        findings.append("NO_SIGNIFICANT_IMAGINARY_MODE" if not significant else "MULTIPLE_SIGNIFICANT_IMAGINARY_MODES")
        next_actions.append("Review threshold sensitivity and the candidate/path; no significant imaginary mode does not support a saddle" if not significant else
                            "Inspect extra unstable modes and numerical sensitivity; clear additional instabilities can require conformational or saddle refinement")
    if stationary is not True:
        findings.append("RESIDUAL_FORCES_TOO_LARGE" if stationary is False else "UNPERTURBED_FORCES_UNAVAILABLE")
        next_actions.append("Use force evidence at the exact candidate; large forces require a saddle optimizer or suitable path refinement, not ordinary minimum relaxation")
    if constraint_mode_valid is False:
        findings.append("PARTIAL_HESSIAN_CONSTRAINT_MODE_UNSUPPORTED")
    if partial:
        findings.append("PARTIAL_HESSIAN_ONLY")
    if reaction_checks is not None and reaction_checks["compatible"] is False:
        findings.append("MODE_INCONSISTENT_WITH_REQUESTED_BOND_CHANGES")
        next_actions.append("Check atom mapping and the selected key bonds, then review the competing local motion; this diagnostic alone does not reject the mechanism")
    if reaction_checks is not None and reaction_checks["compatible"] is None:
        findings.append("REACTION_MODE_MOTION_INCONCLUSIVE")
        next_actions.append("Weak bond-length motion may reflect bending or asynchronous motion; inspect the mode/path before changing the mechanism")
    if bonds and reaction_checks is None:
        findings.append("REACTION_MODE_VECTORS_UNAVAILABLE")
    requested_pass = local
    if bonds and local is True:
        requested_pass = reaction_checks["compatible"] if reaction_checks is not None else None
    return {"status": "success", "operation": "inspect", "calculation_dir": str(directory),
            "first_order_saddle_supported_in_checked_subspace": local,
            "requested_checks_passed": requested_pass,
            "checks": checks, "imaginary_threshold_cm1": threshold,
            "n_significant_imaginary": len(significant), "n_weak_imaginary": len(imaginary) - len(significant),
            "expected_modes": expected, "observed_modes": len(modes),
            "modes": [{k: v for k, v in mode.items() if k != "vectors"} for mode in modes],
            "force_tolerance_ev_per_angstrom": force_limit, "max_unperturbed_active_force": max_force,
            "force_source": str(force_source), "partial_hessian": partial,
            "atom_indexing": atom_indexing,
            "reaction_mode_check": reaction_checks, "target_reaction_validated": None,
            "coverage": {"local_saddle": "checked", "reaction_mode": "requested" if bonds else "not_requested",
                         "irc": "not_performed", "endpoint_identity": "not_checked"},
            "findings": findings, "next_actions": list(dict.fromkeys(next_actions))}


def prepare_frequency(request, base):
    import numpy as np
    from ase.io import read, write
    from ase.constraints import FixAtoms

    source = (base / request["source_dir"]).resolve()
    structure = (base / request["structure_file"]).resolve()
    output = (base / request["output_dir"]).resolve()
    if output.exists() or not output.parent.is_dir():
        raise ValueError("output_dir must be new with an existing parent")
    for filename in ("INCAR", "KPOINTS", "POTCAR"):
        if not (source / filename).is_file() or not (source / filename).stat().st_size:
            raise ValueError(f"source_dir needs nonempty {filename}")
    frames = read(structure, index=":")
    if len(frames) != 1:
        raise ValueError("Candidate file must contain exactly one structure")
    atoms = frames[0]
    if not len(atoms) or not np.isfinite(atoms.positions).all() or not np.isfinite(atoms.cell.array).all() or abs(np.linalg.det(atoms.cell.array)) < 1e-10:
        raise ValueError("Candidate needs finite coordinates and a full-rank cell")
    atoms.pbc = True  # VASP is three-dimensionally periodic; retain the supplied cell.
    mask = mask_for(atoms)
    fixed = request.get("fixed_atoms", [])
    if not isinstance(fixed, list) or any(type(i) is not int or not 1 <= i <= len(atoms) for i in fixed):
        raise ValueError("fixed_atoms uses one-based candidate-file indices")
    if fixed:
        atoms.set_constraint([*atoms.constraints, FixAtoms(indices=[i - 1 for i in fixed])])
        mask = mask_for(atoms)
    if mask.all():
        raise ValueError("No active degrees of freedom")
    symbols = atoms.get_chemical_symbols()
    blocks = [symbol for i, symbol in enumerate(symbols) if i == 0 or symbol != symbols[i - 1]]
    potentials = re.findall(r"(?m)^\s*VRHFIN\s*=\s*([A-Za-z]+)\s*:", text(source / "POTCAR"))
    if blocks != potentials:
        raise ValueError("Candidate species blocks must match source POTCAR VRHFIN order; restore VASP order explicitly")
    original_text = text(source / "INCAR")
    if re.search(r"[\\&]\s*$", original_text, re.M):
        raise ValueError("Multiline INCAR continuations are unsupported; normalize controls before preparation")
    original = incar(original_text)
    if "ENCUT" not in original or original.get("ISPIN", "1") not in ("1", "2"):
        raise ValueError("Source needs explicit ENCUT and a supported ISPIN")
    ediff = request.get("ediff", 1e-7)
    potim = request.get("potim", 0.015)
    nfree = request.get("nfree", 2)
    if not isinstance(ediff, (int, float)) or not math.isfinite(ediff) or not 0 < ediff <= 1e-6:
        raise ValueError("ediff must be positive and <=1e-6")
    if not isinstance(potim, (int, float)) or not math.isfinite(potim) or potim <= 0 or nfree not in (2, 4):
        raise ValueError("Use positive potim and nfree 2/4")
    remove = {"IBRION", "NSW", "ISIF", "POTIM", "NFREE", "EDIFF", "EDIFFG", "ISTART", "ICHARG",
              "IMAGES", "SPRING", "LCLIMB", "IOPT", "ICHAIN", "MAXMOVE", "LNEBCELL", "LTANGENTOLD",
              "LDNEB", "LDNEBORG", "TIMESTEP", "LGLOBAL", "LLINEOPT", "LAUTOSCALE", "INVCURV",
              "ILBFGSMEM", "FDSTEP", "SDALPHA", "FTIMEMAX", "FTIMEDEC", "FTIMEINC", "FALPHA", "FNMIN"}
    retained = {key: value for key, value in original.items() if key not in remove}
    retained.update({"IBRION": "5" if mask.any() else "6", "NSW": "1", "ISIF": "2",
                     "POTIM": str(potim), "NFREE": str(nfree), "EDIFF": str(ediff), "ISTART": "0", "ICHARG": "2"})
    # Preserve physical tags, magnetization order, licensed POTCAR and k-point file.
    with tempfile.TemporaryDirectory(prefix=".ts-frequency-", dir=output.parent) as temporary:
        staging = Path(temporary) / "job"
        staging.mkdir()
        write(staging / "POSCAR", atoms, format="vasp", sort=False, vasp5=True)
        saved = read(staging / "POSCAR")
        if saved.get_chemical_symbols() != symbols or not np.allclose(saved.positions, atoms.positions, rtol=0, atol=1e-8) or not np.allclose(saved.cell.array, atoms.cell.array, rtol=0, atol=1e-8) or not np.array_equal(mask_for(saved), mask):
            raise ValueError("Serialized candidate coordinates/order/constraints changed")
        for filename in ("KPOINTS", "POTCAR"):
            shutil.copyfile(source / filename, staging / filename)
        (staging / "INCAR").write_text("\n".join(f"{key} = {value}" for key, value in retained.items()) + "\n", encoding="utf-8")
        (staging / "ase-sort.dat").write_text("".join(f"{i} {i}\n" for i in range(len(atoms))), encoding="ascii")
        hashes = {name: hashlib.sha256((staging / name).read_bytes()).hexdigest() for name in ("INCAR", "POSCAR", "KPOINTS", "POTCAR")}
        manifest = {"tool": "chem-vasp-ts-validation", "source_dir": str(source), "structure_file": str(structure),
                    "output_dir": str(output), "input_sha256": hashes, "partial_hessian": bool(mask.any()),
                    "physical_tags_preserved": sorted(key for key in original if key not in remove),
                    "removed_control_tags": sorted(set(original) & remove), "expected_modes": int((~mask).sum())}
        (staging / "validation-input.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        staging.rename(output)
    return {"status": "success", "operation": "prepare_frequency", "stage": "inputs_prepared",
            "vasp_executed": False, "calculation_dir": str(output), "manifest": manifest}


def run_frequency(request, base):
    directory = (base / request["calculation_dir"]).resolve()
    manifest = json.loads((directory / "validation-input.json").read_text(encoding="utf-8"))
    if manifest.get("tool") != "chem-vasp-ts-validation":
        raise ValueError("run_frequency requires this tool's prepared directory")
    for name, digest in manifest["input_sha256"].items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Prepared inputs changed; prepare a new calculation or run with the site tool")
    command = request["command"]
    timeout = request["timeout_seconds"]
    if not isinstance(command, list) or not command or any(not isinstance(v, str) or not v for v in command):
        raise ValueError("command must be an explicit argument list; no shell syntax")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Supply a finite positive timeout_seconds budget")
    if (directory / "OUTCAR").exists() or (directory / "validation.stdout").exists():
        raise ValueError("Existing execution output; inspect it rather than rerunning automatically")
    with (directory / "validation.stdout").open("w") as stdout, (directory / "validation.stderr").open("w") as stderr:
        process = subprocess.Popen(command, cwd=directory, stdout=stdout, stderr=stderr,
                                   start_new_session=os.name != "nt")
        timed_out = False
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
                process.kill() if process.poll() is None else None
            else:
                os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
    result = inspect(request, base)
    result["operation"] = "run_frequency"
    result["execution"] = {"command": command, "return_code": code, "timed_out": timed_out,
                           "stdout": str(directory / "validation.stdout"), "stderr": str(directory / "validation.stderr")}
    if timed_out or code != 0:
        result["first_order_saddle_supported_in_checked_subspace"] = None
        result["requested_checks_passed"] = None
        result["findings"].insert(0, "EXECUTION_TIMEOUT" if timed_out else "EXECUTION_FAILED")
    return result


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
        operation = request.get("operation", "inspect")
        common = {"operation"}
        inspection = {"calculation_dir", "imaginary_threshold_cm1", "force_tolerance_ev_per_angstrom", "stationary_outcar", "reaction_bonds", "reaction_atom_order", "input_to_poscar_atom", "mode_motion_tolerance"}
        fields = {"inspect": inspection,
                  "prepare_frequency": {"source_dir", "structure_file", "output_dir", "fixed_atoms", "ediff", "potim", "nfree"},
                  "run_frequency": inspection | {"command", "timeout_seconds"}}
        if operation not in fields or set(request) - (common | fields[operation]):
            raise ValueError("Unsupported operation or unknown request fields")
        result = {"inspect": inspect, "prepare_frequency": prepare_frequency, "run_frequency": run_frequency}[operation](request, base)
        print(json.dumps(result, allow_nan=False))
        return 0
    except ImportError as exc:
        result, code = {"status": "error", "error": "MISSING_DEPENDENCY", "message": str(exc)}, 3
    except Exception as exc:
        result, code = {"status": "error", "error": "REQUEST_OR_PARSING_ERROR", "message": str(exc)}, 2
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    sys.exit(main())
