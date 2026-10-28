# VASP Calculation API

## Preparation request

| Field | Meaning |
|---|---|
| `task` | Required: `singlepoint`, `relax`, `vibrations` |
| `structure_file` | Required: one ASE-readable structure with finite full-rank cell and 3D PBC |
| `output_dir` | Required: new directory; parent must exist |
| `parameters` | Required ASE `Vasp` keywords; casing normalized; duplicate normalized names rejected |
| `fixed_atoms` | Optional unique one-based input indices, combined with existing `FixAtoms` |

Explicit common parameters: `xc`, positive `encut`, positive `ediff`, `ispin:1/2`, and `kpts:[nx,ny,nz]`. The helper does not determine their suitability. ASE recipes such as `xc:"PBE"` can set other tags; inspect the written INCAR for the final recipe. Optional `pp`, per-element `setups`, `gga`, `ismear`, `sigma`, `magmom`, `nelect`, `ivdw`, `ldipol`, `idipol`, and `dipol` follow installed ASE. `magmom` and any atom-indexed quantities refer to original input order. Include charge/spin information from the task; `ispin:1` is not appropriate for every system.

Execution-related keys, `custom`, `ignore_constraints`, NEB tags, `kspacing`, and numeric per-atom `setups` are rejected. The helper cannot establish that every arbitrary accepted VASP tag combination is physically consistent; specialized configurations should use ASE directly and authoritative documentation.

## Modes

| Task | Mode settings | Additional requirements |
|---|---|---|
| `singlepoint` | `ibrion:-1`, `nsw:0` | No geometry optimization |
| `relax` | `ibrion:2` by default; 1 also allowed; `isif:2` | Explicit positive `nsw`, negative `ediffg` in eV/Å |
| `vibrations` | `ibrion:6` for all atoms; 5 for fixed atoms; `nsw:1`, `isif:2` | `ediff <= 1e-6`; default `potim:0.015`, `nfree:2`; optional `nfree:4` |

Defaults define a calculation mode, not a tested accuracy target. Vary finite-difference displacement and SCF accuracy when results are sensitive to numerical noise. Contradictory mode tags fail instead of silently changing the requested task. `IBRION=5` selectively displaces unfrozen coordinates; it is retained for partial Hessians even though newer VASP guidance recommends 6 for full calculations.

Choose `relax` for stable structures or reaction endpoints; it is a minimum optimizer, not a saddle-refinement method. `singlepoint` leaves geometry unchanged. `vibrations` prepares frequency evidence at the supplied geometry without first relaxing it. Input preparation produces no TS acceptance verdict.

Relaxation example (illustrative settings):

```json
{"task":"relax","structure_file":"input.extxyz","output_dir":"relax-01","fixed_atoms":[1,2],"parameters":{"xc":"PBE","encut":500,"ediff":1e-6,"ispin":1,"kpts":[2,2,1],"nsw":100,"ediffg":-0.03}}
```

Vibrational calculation at the supplied candidate geometry:

```json
{"task":"vibrations","structure_file":"candidate.extxyz","output_dir":"vib-01","parameters":{"xc":"PBE","encut":500,"ediff":1e-7,"ispin":1,"kpts":[1,1,1]}}
```

## Execution

For helper-prepared directories, use the existing site launcher in that directory, for example on a configured Linux compute node:

```bash
cd sp-01
mpirun -np 4 vasp_std > vasp.stdout 2> vasp.stderr
```

The executable, rank count and launcher are examples, not portable defaults. Use the configured scheduler rather than launching compute work on a login node. A batch job must enter the calculation directory and preserve stdout/stderr. Do not copy TSAgent's partition, account, memory, modules or MPI-rank heuristics into an unrelated cluster.

For an ASE-managed single-structure run, bypass the preparation helper and use a new directory:

```python
from pathlib import Path
from ase.io import read
from ase.calculators.vasp import Vasp

atoms = read("input.extxyz")  # Preserve intended cell/PBC/constraints/moments.
directory = Path("ase-sp-01")
directory.mkdir(exist_ok=False)
atoms.calc = Vasp(directory=str(directory), xc="PBE", encut=500,
                  ediff=1e-6, ispin=1, kpts=(1, 1, 1),
                  ibrion=-1, nsw=0)
energy_ev = atoms.get_potential_energy()  # Executes configured VASP command.
forces_ev_per_angstrom = atoms.get_forces()
```

ASE reads `ASE_VASP_COMMAND` or an explicit calculator `command`. Adapt physical settings and process resources to the task. Calling a getter can execute VASP; do not use it to merely inspect files. Native `IBRION` relaxation already controls ionic motion; nesting it inside an ASE optimizer defines a different algorithm.

If the task's executable, potential library or launcher/allocation is unavailable, report the missing requirement and the prepared/stored evidence available. Do not substitute an unrequested physical model or infer execution from files alone.

## Reading existing output

With complete ASE-compatible output files, this loads stored results without a calculation:

```python
from ase.calculators.vasp import Vasp

calc = Vasp(restart=True, directory="sp-01")
energy_ev = calc.results.get("energy")
free_energy_ev = calc.results.get("free_energy")
forces_ev_per_angstrom = calc.results.get("forces")
ase_converged = calc.converged
atoms_in_original_order = calc.atoms
```

Loading can fail for partial or missing files. Report unavailable values; do not rerun just to obtain them. Keep `ase-sort.dat` with the results so forces and atom identities can be restored. Check the final electronic record and actual termination: ASE convergence flags alone are not a universal completion certificate. In finite differences, electronic convergence is needed for the displaced configurations, not just the initial geometry. Use a consistent energy convention across comparisons: ASE `energy` and `free_energy` have different smearing conventions.

For mode energies from an existing OUTCAR, no restart initialization is needed:

```python
from ase.calculators.vasp import Vasp

calc = Vasp(directory="vib-01")
real_mev, imaginary_magnitudes_mev = calc.read_vib_freq()
```

These values are **meV**, not cm^-1; preserve the imaginary flag/list. Empty lists can mean missing data, not absence of an instability. A numeric filtering threshold must specify its units and be applied to every imaginary mode consistently. When only a partial Hessian was calculated, record that scope. To inspect mode vectors, `Vasp(restart=True, directory="vib-01").get_vibrations()` reads the Hessian from complete `vasprun.xml`; account for its documented sorted atom order before comparing movement to the reaction.

## Continuation and comparison

For geometry continuation, preserve the original run, use its final usable `CONTCAR` as input and prepare a new directory with the required budget/accuracy. This is a geometry restart, not automatic wavefunction continuation. For electronic restart, match the potential ordering and relevant basis/settings, copy only compatible available `WAVECAR`/`CHGCAR`, and explicitly choose `istart`/`icharg`. ASE `restart=True` loads existing calculator state; it does not itself prove a job was submitted or continued.

For an energy difference, retain matching POTCAR hashes/species, functional/corrections, ENCUT, k-point sampling, charge/spin policy and energy convention. The same `xc` label does not prove equivalent INCAR or potentials. Changed cells can require a revised sampling policy and new convergence assessment.
