#!/usr/bin/env python3
"""Bounded molecular TS validation using Pysisyphus, TBLite and RDKit."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

BOHR_TO_ANG = 0.529177210903
SUPPORTED = {'H', 'B', 'C', 'N', 'O', 'F', 'Si', 'P', 'S', 'Cl', 'Br', 'I'}
PACKAGES = {'pysisyphus': 'pysisyphus', 'tblite': 'tblite', 'rdkit': 'rdkit'}
DEFAULTS = dict(threads=2, timeout_seconds=300, ts_max_cycles=200,
                irc_max_cycles=100, endpoint_max_cycles=200,
                imaginary_threshold_cm1=0.0, hessian_step_bohr=0.005)


def write_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def environment():
    versions, missing = {}, []
    for package, module in PACKAGES.items():
        try:
            versions[package] = metadata.version(package)
            if importlib.util.find_spec(module) is None:
                missing.append(package)
        except (metadata.PackageNotFoundError, ImportError):
            missing.append(package)
    return {'ready': not missing and os.name == 'posix', 'versions': versions,
            'missing': missing, 'platform': sys.platform, 'python': sys.version.split()[0],
            'backend': 'GFN2-xTB via TBLite', 'requires': 'Linux or WSL; Python 3.10+'}


def canonical(smiles):
    from rdkit import Chem
    if not isinstance(smiles, str) or not smiles.strip():
        raise ValueError('Target SMILES must be nonempty strings.')
    mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0:
        raise ValueError('Invalid or empty target SMILES.')
    if any(atom.GetNumRadicalElectrons() for atom in mol.GetAtoms()):
        raise ValueError('Radical targets are outside the closed-shell scope.')
    if any(atom.GetIsotope() for atom in mol.GetAtoms()):
        raise ValueError('Isotope-specific targets cannot be represented by the plain XYZ input.')
    for atom in mol.GetAtoms():
        atom.SetAtomMapNum(0)
    Chem.RemoveStereochemistry(mol)
    normalized = Chem.MolToSmiles(Chem.RemoveHs(mol), isomericSmiles=False)
    inventory = Counter(atom.GetSymbol() for atom in Chem.AddHs(mol).GetAtoms())
    charge = sum(atom.GetFormalCharge() for atom in mol.GetAtoms())
    return normalized, inventory, charge


def read_xyz(path):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    count = int(lines[0])
    if not 2 <= count <= 60 or len(lines) < count + 2 or any(s.strip() for s in lines[count+2:]):
        raise ValueError('Provide one nonperiodic XYZ frame containing 2–60 atoms.')
    atoms, coords = [], []
    for line in lines[2:count+2]:
        fields = line.split()
        if len(fields) != 4 or fields[0] not in SUPPORTED:
            raise ValueError('XYZ requires supported element symbols and three coordinates per atom.')
        point = [float(s) for s in fields[1:]]
        if not all(math.isfinite(x) for x in point):
            raise ValueError('XYZ coordinates must be finite.')
        atoms.append(fields[0])
        coords.extend(point)
    if 'Lattice=' in lines[1]:
        raise ValueError('Periodic structures are outside the molecular scope.')
    return atoms, coords


def xyz_text(atoms, coords_ang, comment=''):
    return f'{len(atoms)}\n{comment}\n' + ''.join(
        f'{symbol:2s} {coords_ang[3*i]: .12f} {coords_ang[3*i+1]: .12f} {coords_ang[3*i+2]: .12f}\n'
        for i, symbol in enumerate(atoms))


def prepare_request(raw, request_path):
    allowed = set(DEFAULTS) | {'guess_file', 'reactant_smiles', 'product_smiles', 'charge',
                               'multiplicity', 'output_dir'}
    if set(raw) - allowed:
        raise ValueError(f'Unknown request fields: {sorted(set(raw) - allowed)}')
    for key in ('guess_file', 'reactant_smiles', 'product_smiles', 'charge', 'multiplicity', 'output_dir'):
        if key not in raw:
            raise ValueError(f'Missing field: {key}')
    req = {**DEFAULTS, **raw}
    if type(req['charge']) is not int or type(req['multiplicity']) is not int or req['multiplicity'] != 1:
        raise ValueError('Charge must be an integer; this tool supports closed-shell multiplicity 1.')
    for key, low, high in [('threads', 1, 16), ('timeout_seconds', 1, 3600),
                           ('ts_max_cycles', 1, 500), ('irc_max_cycles', 1, 500),
                           ('endpoint_max_cycles', 1, 500)]:
        if type(req[key]) is not int or not low <= req[key] <= high:
            raise ValueError(f'{key} must be an integer in [{low}, {high}].')
    for key, low, high in [('imaginary_threshold_cm1', 0, 100), ('hessian_step_bohr', .001, .02)]:
        if type(req[key]) not in (int, float) or not math.isfinite(req[key]) or not low <= req[key] <= high:
            raise ValueError(f'{key} must be finite in [{low}, {high}].')
    for key in ('guess_file', 'output_dir'):
        path = Path(req[key]).expanduser()
        req[key] = str((request_path.parent / path).resolve() if not path.is_absolute() else path.resolve())
    atoms, coords = read_xyz(Path(req['guess_file']))
    targets = [canonical(req[key]) for key in ('reactant_smiles', 'product_smiles')]
    if any(t[1] != Counter(atoms) or t[2] != req['charge'] for t in targets):
        raise ValueError('Both target SMILES must match the XYZ atom inventory and total charge.')
    from rdkit import Chem
    electrons = sum(Chem.GetPeriodicTable().GetAtomicNumber(a) for a in atoms) - req['charge']
    if electrons <= 0 or electrons % 2:
        raise ValueError('Electron count is incompatible with a closed-shell singlet.')
    req['target_pair'] = sorted(t[0] for t in targets)
    return req, atoms, coords


def endpoint_smiles(atoms, coords_ang, charge):
    from rdkit import Chem
    from rdkit.Chem import rdDetermineBonds
    mol = Chem.MolFromXYZBlock(xyz_text(atoms, coords_ang))
    rdDetermineBonds.DetermineBonds(mol, charge=charge, allowChargedFragments=True,
                                    embedChiral=False)
    for atom in mol.GetAtoms():
        atom.SetAtomMapNum(0)
    Chem.RemoveStereochemistry(mol)
    if any(atom.GetNumRadicalElectrons() for atom in mol.GetAtoms()):
        raise ValueError('Endpoint bond perception produced an unsupported radical.')
    return Chem.MolToSmiles(Chem.RemoveHs(mol), isomericSmiles=False)


def inventory_artifacts(out):
    selected = ['input.xyz', 'resolved_request.json', 'ts.xyz', 'ts_hessian.h5',
                'frequencies.json', 'imaginary_mode.json', 'irc/finished_irc.trj', 'endpoint_1.xyz', 'endpoint_2.xyz']
    return {name: hashlib.sha256((out/name).read_bytes()).hexdigest()
            for name in selected if (out/name).is_file()}


def save_report(out, report):
    report['elapsed_seconds'] = round(time.monotonic() - report['_start'], 3)
    report['artifacts_sha256'] = inventory_artifacts(out)
    write_json(out/'report.json', {k: v for k, v in report.items() if not k.startswith('_')})


def worker(out):
    req = json.loads((out/'resolved_request.json').read_text(encoding='utf-8'))
    report = dict(schema_version=1, status='running', passed=None, target_reaction_validated=None,
                  failure_stage=None, failure_kind=None, stage='initialization',
                  environment=environment(), settings=req, stages={}, findings=[],
                  scope='Nonperiodic closed-shell molecule; gas-phase GFN2-xTB; stereo ignored.',
                  _start=time.monotonic())
    save_report(out, report)
    try:
        import numpy as np
        from pysisyphus.Geometry import Geometry
        from pysisyphus.calculators.TBLite import TBLite
        from pysisyphus.tsoptimizers.RSPRFOptimizer import RSPRFOptimizer
        from pysisyphus.optimizers.RFOptimizer import RFOptimizer
        from pysisyphus.irc.EulerPC import EulerPC
        from pysisyphus.io.hessian import save_hessian

        atoms, coords = read_xyz(out/'input.xyz')

        def calculator():
            return TBLite(gfn=2, charge=req['charge'], mult=1, acc=0.1, verbosity=0,
                          pal=1, num_hess_kwargs={'step_size': req['hessian_step_bohr'], 'acc': 2},
                          out_dir=str(out))

        def geometry(coords_bohr):
            geom = Geometry(atoms, np.asarray(coords_bohr).reshape(-1), coord_type='cart')
            geom.set_calculator(calculator())
            return geom

        def stage(name):
            report['stage'] = name
            save_report(out, report)
            folder = out/name
            folder.mkdir(exist_ok=True)
            return folder

        def force_metrics(geom):
            result = geom.calculator.get_forces(geom.atoms, geom.cart_coords)
            forces = np.asarray(result['forces'])
            if not np.all(np.isfinite(forces)) or not math.isfinite(float(result['energy'])):
                raise ValueError('Nonfinite energy or forces.')
            return {'energy_hartree': float(result['energy']),
                    'max_force_hartree_per_bohr': float(np.abs(forces).max()),
                    'rms_force_hartree_per_bohr': float(np.sqrt(np.mean(forces**2)))}

        def stationary(metrics):
            return metrics['max_force_hartree_per_bohr'] <= 1.5e-5 and metrics['rms_force_hartree_per_bohr'] <= 1e-5

        def finish(status, kind, message, passed=None):
            report.update(status=status, passed=passed, failure_kind=kind,
                          failure_stage=report['stage'] if status != 'passed' else None)
            report['findings'].append(message)
            save_report(out, report)

        geom = geometry(np.array(coords) / BOHR_TO_ANG)
        folder = stage('ts_optimization')
        opt = RSPRFOptimizer(geom, root=0, hessian_init='calc', hessian_recalc=5,
                            assert_neg_eigval=False, max_cycles=req['ts_max_cycles'],
                            thresh='gau_tight', out_dir=folder, dump=True)
        opt.run()
        (out/'ts.xyz').write_text(xyz_text(atoms, geom.cart_coords * BOHR_TO_ANG), encoding='utf-8')
        metrics = force_metrics(geom)
        report['stages']['ts_optimization'] = {**metrics, 'converged': bool(opt.is_converged),
                                                'cycles': int(opt.cur_cycle)+1}
        if not opt.is_converged or not stationary(metrics):
            finish('inconclusive', 'not_converged', 'TS refinement did not satisfy tight convergence and fresh-force checks.')
            return

        stage('frequency_analysis')
        hessian = np.asarray(geom.calculator.get_hessian(geom.atoms, geom.cart_coords)['hessian'])
        if hessian.shape != (3*len(atoms), 3*len(atoms)) or not np.all(np.isfinite(hessian)):
            raise ValueError('Invalid numerical Hessian.')
        hessian = (hessian + hessian.T) / 2
        nus, eigvals, mw_modes, cart_modes = geom.get_normal_modes(cart_hessian=hessian)
        nus = np.asarray(nus)
        if not np.all(np.isfinite(nus)):
            raise ValueError('Nonfinite vibrational frequencies.')
        negative = np.where(nus < -req['imaginary_threshold_cm1'])[0]
        freq = {'frequencies_cm1': nus.tolist(), 'imaginary_count': int(len(negative)),
                'threshold_cm1': req['imaginary_threshold_cm1'],
                'excluded_weak_negative_cm1': nus[(nus < 0) & (nus >= -req['imaginary_threshold_cm1'])].tolist(),
                'method': 'Central numerical Hessian; mass weighting; translations and rotations projected out.'}
        report['stages']['frequency_analysis'] = freq
        write_json(out/'frequencies.json', freq)
        save_hessian(out/'ts_hessian.h5', geom, cart_hessian=hessian,
                     energy=metrics['energy_hartree'], charge=req['charge'], mult=1)
        if len(negative) != 1:
            finish('failed', 'not_first_order_saddle', 'Refined stationary structure does not have exactly one imaginary vibrational mode.', False)
            return
        mode_index = int(negative[0])
        write_json(out/'imaginary_mode.json', {
            'frequency_cm1': float(nus[mode_index]), 'atom_order': atoms,
            'normalized_cartesian_displacements': np.asarray(cart_modes[:, mode_index]).reshape(-1, 3).tolist(),
            'meaning': 'Relative atomic motion; normalized full vector; global sign is arbitrary.'})

        folder = stage('irc')
        irc = EulerPC(geom, root=int(negative[0]), forward=True, backward=True,
                      max_cycles=req['irc_max_cycles'], step_length=0.1,
                      hessian_init=str(out/'ts_hessian.h5'), hessian_recalc=5,
                      rms_grad_thresh=1e-3, energy_thresh=1e-6,
                      out_dir=folder, dump_every=1)
        irc.run()
        branches = {direction: {'converged': bool(getattr(irc, direction+'_is_converged')),
                                'energy_plateau': bool(getattr(irc, direction+'_energy_converged')),
                                'energy_increased': bool(getattr(irc, direction+'_energy_increased')),
                                'cycles': int(getattr(irc, direction+'_cycle'))+1}
                    for direction in ('forward', 'backward')}
        report['stages']['irc'] = {'branches': branches, 'trajectory': 'irc/finished_irc.trj'}
        if not all(b['converged'] for b in branches.values()):
            finish('inconclusive', 'not_converged', 'Both IRC directions must converge before endpoint comparison.')
            return
        end_coords = [np.asarray(irc.all_coords[0]), np.asarray(irc.all_coords[-1])]
        ts_coords = np.asarray(read_xyz(out/'ts.xyz')[1]) / BOHR_TO_ANG
        if any(not np.all(np.isfinite(c)) or np.linalg.norm(c-ts_coords) < 1e-4 for c in end_coords):
            finish('inconclusive', 'degenerate_path', 'IRC did not produce two displaced endpoints.')
            return
        ts_energy = metrics['energy_hartree']
        observed = []
        for i, coords_bohr in enumerate(end_coords, 1):
            folder = stage(f'endpoint_{i}_optimization')
            end = geometry(coords_bohr)
            end_opt = RFOptimizer(end, hessian_init='calc', hessian_recalc=5,
                                  max_cycles=req['endpoint_max_cycles'], thresh='gau_tight',
                                  out_dir=folder, dump=True)
            end_opt.run()
            (out/f'endpoint_{i}.xyz').write_text(xyz_text(atoms, end.cart_coords*BOHR_TO_ANG), encoding='utf-8')
            end_metrics = force_metrics(end)
            report['stages'][f'endpoint_{i}_optimization'] = {
                **end_metrics, 'converged': bool(end_opt.is_converged), 'cycles': int(end_opt.cur_cycle)+1,
                'below_ts': bool(end_metrics['energy_hartree'] < ts_energy-1e-8),
                'electronic_barrier_from_endpoint_kj_per_mol':
                    (ts_energy-end_metrics['energy_hartree'])*2625.4996394799}
            if not end_opt.is_converged or not stationary(end_metrics):
                finish('inconclusive', 'not_converged', f'Endpoint {i} did not satisfy tight convergence and fresh-force checks.')
                return
            if not end_metrics['energy_hartree'] < ts_energy-1e-8:
                finish('inconclusive', 'path_energy_check', f'Endpoint {i} is not demonstrably lower in energy than the TS.')
                return
            observed.append((atoms, end.cart_coords*BOHR_TO_ANG))

        stage('endpoint_matching')
        try:
            pair = sorted(endpoint_smiles(a, c, req['charge']) for a, c in observed)
        except Exception as error:
            finish('inconclusive', 'bond_perception', f'Endpoint connectivity could not be assigned: {error}')
            return
        matches = pair == req['target_pair']
        report['stages']['endpoint_matching'] = {'observed_pair': pair, 'target_pair': req['target_pair'],
                                                 'matches': matches, 'stereochemistry_ignored': True}
        report['target_reaction_validated'] = matches
        finish('passed' if matches else 'failed', None if matches else 'wrong_endpoints',
               'One imaginary mode and both optimized IRC endpoints match the target pair.' if matches else
               'A first-order saddle was found, but its optimized IRC endpoints do not match the target pair.', matches)
    except Exception as error:
        traceback.print_exc()
        report.update(status='inconclusive', passed=None, failure_stage=report['stage'], failure_kind='execution_error')
        report['findings'].append(f'{type(error).__name__}: {error}; see worker.stderr.log.')
        save_report(out, report)


def inspect_report(out):
    report = json.loads((out/'report.json').read_text(encoding='utf-8'))
    problems = []
    for name, digest in report.get('artifacts_sha256', {}).items():
        path = (out/name).resolve()
        if not path.is_relative_to(out.resolve()) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            problems.append(name)
    report['integrity_check'] = {'consistent': not problems, 'changed_or_missing': problems,
                                 'meaning': 'Local artifact consistency, not independent authenticity.'}
    if problems:
        report.update(status='inconclusive', passed=None, target_reaction_validated=None,
                      failure_kind='artifact_integrity')
    return report


def run(request_path):
    env_info = environment()
    if not env_info['ready']:
        print(json.dumps({'status': 'environment_unavailable', **env_info}, indent=2))
        return 3
    raw = json.loads(request_path.read_text(encoding='utf-8'))
    req, atoms, coords = prepare_request(raw, request_path)
    out = Path(req['output_dir'])
    out.mkdir(parents=True, exist_ok=False)
    (out/'input.xyz').write_text(xyz_text(atoms, coords), encoding='utf-8')
    write_json(out/'resolved_request.json', req)
    env = dict(os.environ)
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        env[name] = str(req['threads'])
    started = time.monotonic()
    with (out/'worker.stdout.log').open('w', encoding='utf-8') as stdout, (out/'worker.stderr.log').open('w', encoding='utf-8') as stderr:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker', str(out)],
                                   cwd=out, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        timeout = False
        try:
            process.wait(timeout=req['timeout_seconds'])
        except subprocess.TimeoutExpired:
            timeout = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    report_path = out/'report.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {
        'schema_version': 1, 'settings': req, 'environment': env_info, 'stage': 'initialization', 'stages': {}, 'findings': []}
    if timeout or process.returncode != 0:
        report.update(status='inconclusive', passed=None, target_reaction_validated=None,
                      failure_stage=report.get('stage'), failure_kind='timeout' if timeout else 'worker_crash',
                      elapsed_seconds=round(time.monotonic()-started, 3), artifacts_sha256=inventory_artifacts(out))
        report['findings'].append('Calculation budget exhausted.' if timeout else 'Worker exited unexpectedly; inspect logs.')
        write_json(report_path, report)
    print(json.dumps(inspect_report(out), indent=2, allow_nan=False))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--request', type=Path)
    actions.add_argument('--inspect', type=Path, metavar='OUTPUT_DIR')
    actions.add_argument('--check-environment', action='store_true')
    actions.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.worker:
            worker(args.worker.resolve())
        elif args.check_environment:
            info = environment()
            print(json.dumps(info, indent=2))
            return 0 if info['ready'] else 3
        elif args.inspect:
            print(json.dumps(inspect_report(args.inspect.resolve()), indent=2, allow_nan=False))
        else:
            return run(args.request.resolve())
        return 0
    except (ValueError, OSError, KeyError, TypeError, IndexError) as error:
        print(json.dumps({'status': 'input_error', 'error': str(error)}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
