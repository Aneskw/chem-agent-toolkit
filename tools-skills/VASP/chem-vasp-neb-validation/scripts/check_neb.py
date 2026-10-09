"""Read-only validation of native VASP NEB output and energy compatibility."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[EeDd][-+]?\d+)?"


def text(path):
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def incar(content):
    tags = {}
    for line in content.splitlines():
        for field in line.split("!", 1)[0].split("#", 1)[0].split(";"):
            match = re.match(r"\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", field)
            if match:
                tags[match[1].upper()] = " ".join(match[2].upper().split())
    return tags


def number(value):
    result = float(value.replace("D", "E").replace("d", "e"))
    if not math.isfinite(result):
        raise ValueError("Nonfinite numeric output")
    return result


def scf(content):
    exits = re.findall(r"(?im)^.*aborting loop.*$", content)
    if re.search(r"EDIFF was not reached|BRMIX:\s*very serious|ZHEGV.*failed|EDDDAV.*failed", content, re.I):
        return False
    if exits:
        return all("because ediff is reached" in line.lower() for line in exits)
    return None


def output(directory):
    path = directory / "OUTCAR"
    content = text(path)
    headers = list(re.finditer(r"(?m)^\s*vasp\.\d", content))
    if headers:
        content = content[headers[-1].start():]
    energies = re.findall(r"energy\(sigma->0\)\s*=\s*(" + NUMBER + r")", content)
    return {"directory": str(directory), "outcar": str(path),
            "completed": bool(re.search(r"General timing and accounting informations|Elapsed time\s*\(", content)),
            "optimizer_reported_converged": "reached required accuracy" in content.lower(),
            "electronic_convergence_explicit": scf(content),
            "energy_sigma0_ev": number(energies[-1]) if energies else None}


def signature(directory):
    tags = incar(text(directory / "INCAR"))
    # Compare all non-control input tags, rather than just ENCUT/KPOINTS.
    controls = {"SYSTEM", "IBRION", "NSW", "ISIF", "POTIM", "NFREE", "EDIFF", "EDIFFG", "ISTART", "ICHARG",
                "IMAGES", "SPRING", "LCLIMB", "IOPT", "ICHAIN", "MAXMOVE", "NCORE", "NPAR", "KPAR",
                "LWAVE", "LCHARG", "LVTOT", "LVHAR", "NWRITE", "TIMESTEP", "LGLOBAL", "FDSTEP"}
    physical = {key: value for key, value in tags.items() if key not in controls}
    for key, value in list(physical.items()):
        # Normalize scalar numeric values so 500 and 5.0E2 compare identically.
        if re.fullmatch(NUMBER, value):
            physical[key] = number(value)
    potcar = directory / "POTCAR"
    kpoints = text(directory / "KPOINTS").splitlines()
    return {"physical_incar": physical,
            "potcar_sha256": hashlib.sha256(potcar.read_bytes()).hexdigest() if potcar.is_file() else None,
            "kpoints": [" ".join(line.upper().split()) for line in kpoints[1:] if line.strip()] if kpoints else None,
            "cell": None}


def check(request, base):
    import numpy as np
    from ase.io import read

    root = (base / request["neb_dir"]).resolve()
    tags = incar(text(root / "INCAR"))
    findings, actions = [], []
    n = int(tags["IMAGES"]) if "IMAGES" in tags else None
    if n is None or not 1 <= n <= 98:
        raise ValueError("Root INCAR needs IMAGES in 1..98")
    directories = [root / f"{i:02d}" for i in range(n + 2)]
    images = []
    structures = []
    for i, directory in enumerate(directories):
        row = output(directory)
        row["image_index"] = i
        images.append(row)
        path = directory / "POSCAR"
        structures.append(read(path) if path.is_file() else None)
    present = all(atoms is not None for atoms in structures)
    correspondence = None
    if present:
        first = structures[0]
        correspondence = all(len(atoms) > 0 and np.isfinite(atoms.positions).all() and
                             np.isfinite(atoms.cell.array).all() and abs(np.linalg.det(atoms.cell.array)) > 1e-10 and
                             atoms.get_chemical_symbols() == first.get_chemical_symbols() and
                             np.allclose(atoms.cell.array, first.cell.array, rtol=0, atol=1e-8)
                             for atoms in structures)
    internal = images[1:-1]
    complete = all(row["completed"] for row in internal)
    reported = all(row["optimizer_reported_converged"] for row in internal)
    electronic = False if any(row["electronic_convergence_explicit"] is False for row in internal) else (
        True if all(row["electronic_convergence_explicit"] is True for row in internal) else None)
    ediffg = number(tags["EDIFFG"]) if "EDIFFG" in tags else None
    force_criterion = ediffg is not None and ediffg < 0
    supported = True if complete and reported and electronic is True and correspondence is True and force_criterion else None
    if not present or correspondence is False:
        findings.append("IMAGE_INPUTS_MISSING_OR_INCONSISTENT")
        actions.append("Restore the image count, common cell and supplied atom order before continuing")
    if not complete:
        findings.append("NEB_RUN_INCOMPLETE")
        actions.append("Inspect missing internal OUTCAR/runtime logs; complete the band calculation")
    elif not reported:
        findings.append("NEB_OPTIMIZER_CONVERGENCE_NOT_REPORTED")
        actions.append("Inspect the path and projected-force convergence; continue usable CONTCAR images if appropriate")
    if electronic is not True:
        findings.append("SCF_NOT_CONVERGED" if electronic is False else "SCF_EVIDENCE_UNAVAILABLE")
        actions.append("Check electronic convergence for every moving image before using its energy")
    if not force_criterion:
        findings.append("NEGATIVE_EDIFFG_UNAVAILABLE")
    endpoint_dirs = request.get("endpoint_dirs")
    if endpoint_dirs is not None and (not isinstance(endpoint_dirs, list) or len(endpoint_dirs) != 2):
        raise ValueError("endpoint_dirs must contain reactant and product directories")
    compatibility = None
    if endpoint_dirs:
        endpoints = [(base / path).resolve() for path in endpoint_dirs]
        endpoint_rows = [output(path) for path in endpoints]
        signatures = [signature(path) for path in [root, *endpoints]]
        # Endpoint final cell must agree with the NEB cell. Energies alone carry no cell evidence.
        for signature_row, directory in zip(signatures, [root, *endpoints]):
            path = root / "00" / "POSCAR" if directory == root else directory / "CONTCAR"
            if path.is_file():
                signature_row["cell"] = read(path).cell.array.tolist()
        known = all(row["potcar_sha256"] and row["kpoints"] and "ENCUT" in row["physical_incar"] and row["cell"] is not None for row in signatures)
        compatibility = all(row == signatures[0] for row in signatures[1:]) if known else None
        endpoint_geometry_matches = []
        from ase.geometry import find_mic
        for endpoint, image_index in zip(endpoints, (0, n + 1)):
            source = endpoint / "CONTCAR"
            target = structures[image_index]
            if source.is_file() and target is not None:
                final = read(source)
                match = final.get_chemical_symbols() == target.get_chemical_symbols()
                if match:
                    delta, _ = find_mic(final.positions - target.positions, target.cell, pbc=target.pbc)
                    match = bool(np.max(np.abs(delta)) <= 1e-5)
                endpoint_geometry_matches.append(match)
            else:
                endpoint_geometry_matches.append(None)
        endpoint_usable = all(row["completed"] and row["electronic_convergence_explicit"] is True and
                              row["optimizer_reported_converged"] and row["energy_sigma0_ev"] is not None for row in endpoint_rows)
        for image_index, row in zip((0, n + 1), endpoint_rows):
            images[image_index]["energy_sigma0_ev"] = row["energy_sigma0_ev"]
            images[image_index]["external_endpoint_result"] = row
        if compatibility is not True:
            findings.append("ENERGY_SETTINGS_MISMATCH" if compatibility is False else "ENERGY_SETTINGS_EVIDENCE_INCOMPLETE")
            actions.append("Reconcile endpoint/NEB potentials, physical tags, k points and cell before reporting a barrier")
        if not endpoint_usable or not all(v is True for v in endpoint_geometry_matches):
            findings.append("ENDPOINT_RESULT_UNCONVERGED_OR_GEOMETRY_MISMATCH")
        comparison_ready = compatibility is True and endpoint_usable and all(v is True for v in endpoint_geometry_matches)
        barrier_ready = supported is True and comparison_ready
    else:
        endpoint_geometry_matches = None
        comparison_ready = False
        barrier_ready = False
        findings.append("COMPARABLE_ENDPOINT_RESULTS_NOT_SUPPLIED")
        actions.append("Supply comparable endpoint results only if a qualified barrier or resolved internal maximum is needed")
    energies = [row["energy_sigma0_ev"] for row in images]
    internal_known = all(row["energy_sigma0_ev"] is not None for row in internal)
    candidate = max(internal, key=lambda row: row["energy_sigma0_ev"]) if internal_known else None
    resolved_maximum = None
    if candidate and comparison_ready:
        endpoint_maximum = max(energies[0], energies[-1])
        resolved_maximum = candidate["energy_sigma0_ev"] > endpoint_maximum + 1e-4
        if not resolved_maximum:
            findings.append("NO_RESOLVED_INTERNAL_MAXIMUM")
            actions.append("Inspect path resolution and endpoint quality; the highest internal image is only an inspection structure")
        if endpoint_maximum >= candidate["energy_sigma0_ev"]:
            findings.append("ENERGY_MAXIMUM_IS_AN_ENDPOINT")
    barrier = None
    if barrier_ready and all(value is not None for value in energies):
        maximum = max(range(len(energies)), key=energies.__getitem__)
        barrier = {"energy_convention": "energy(sigma->0)", "maximum_image_index": maximum,
                   "forward_ev": energies[maximum] - energies[0], "reverse_ev": energies[maximum] - energies[-1],
                   "reaction_energy_ev": energies[-1] - energies[0], "interpretation": "Converged sampled band; not a frequency/IRC verdict"}
    minima = [i for i in range(1, len(energies) - 1) if all(v is not None for v in energies[i - 1:i + 2]) and energies[i] < min(energies[i - 1], energies[i + 1]) - 1e-4]
    if minima:
        findings.append("INTERNAL_ENERGY_MINIMA")
        actions.append("Inspect the geometries around each dip; a plausible intermediate may justify separate path segments, while a dip alone does not establish one")
    geometry = None
    if candidate:
        source = Path(candidate["directory"]) / "CONTCAR"
        if source.is_file() and source.stat().st_size:
            try:
                frames = read(source, index=":")
                saved = frames[0] if len(frames) == 1 else None
                original = structures[candidate["image_index"]]
                if (saved is not None and original is not None and np.isfinite(saved.positions).all() and
                        saved.get_chemical_symbols() == original.get_chemical_symbols() and
                        np.allclose(saved.cell.array, original.cell.array, rtol=0, atol=1e-8)):
                    geometry = str(source)
            except Exception:
                pass
        if geometry is None:
            findings.append("CANDIDATE_GEOMETRY_UNAVAILABLE_OR_INVALID")
            actions.append("Recover a valid final candidate structure before frequency preparation")
    candidate_status = ("unavailable" if candidate is None else
                        "geometry_unavailable" if geometry is None else
                        "unverified_band" if supported is not True else
                        "endpoint_comparison_unavailable" if not comparison_ready else
                        "no_resolved_internal_maximum" if not resolved_maximum else
                        "sampled_internal_maximum")
    return {"status": "success", "neb_dir": str(root), "n_internal_images": n,
            "neb_convergence_supported": supported, "checks": {"all_internal_completed": complete,
              "optimizer_reported_convergence": reported, "electronic_convergence_explicit": electronic,
              "image_cell_and_element_order": correspondence, "negative_ediffg": force_criterion,
              "endpoint_energy_settings_consistent": compatibility, "endpoint_geometries_match": endpoint_geometry_matches,
              "internal_maximum_above_endpoints": resolved_maximum},
            "images": images, "sampled_barrier": barrier,
            "highest_energy_internal_image_index": candidate["image_index"] if candidate else None,
            "highest_energy_internal_geometry_file": geometry,
            "candidate_image_index": candidate["image_index"] if candidate else None,
            "candidate_geometry_file": geometry, "candidate_status": candidate_status,
            "candidate_is_provisional": candidate_status != "sampled_internal_maximum",
            "internal_minimum_indices": minima, "target_reaction_validated": None,
            "coverage": {"neb_result": "checked", "frequency": "not_checked", "irc": "not_checked", "atom_identity": "supplied_not_inferred"},
            "findings": findings, "next_actions": list(dict.fromkeys(actions))}


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
        if not isinstance(request, dict) or set(request) - {"neb_dir", "endpoint_dirs"}:
            raise ValueError("Request supports neb_dir and optional endpoint_dirs only")
        print(json.dumps(check(request, base), allow_nan=False))
        return 0
    except ImportError as exc:
        result, code = {"status": "error", "error": "MISSING_DEPENDENCY", "message": str(exc)}, 3
    except Exception as exc:
        result, code = {"status": "error", "error": "REQUEST_OR_PARSING_ERROR", "message": str(exc)}, 2
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    sys.exit(main())
