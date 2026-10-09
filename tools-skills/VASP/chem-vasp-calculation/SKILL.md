---
name: chem-vasp-calculation
description: >-
  Prepare single-structure VASP inputs through ASE for energies/forces or
  fixed-cell relaxation of stable structures, including reaction endpoints.
  Also support generic frequency input preparation and reading stored results;
  use the configured VASP launcher for execution. No path or saddle search.
license: MIT
compatibility: Python 3.10+ and ASE 3.26.0; licensed VASP potentials for input preparation; licensed VASP executable and local or cluster runtime for calculations
allowed-tools: Read, Write, Bash, exec_command
---

# VASP Single-Structure Calculations

## Applicability

Use this skill for a single structure's energy/forces or stable-structure relaxation, such as optimizing reaction endpoints. Generic vibrational input preparation is also available. `scripts/prepare_vasp.py` writes inputs; actual calculation uses the installed VASP launcher.

Supply the cell, charge/spin and physical settings. Existing results can be read without another job. Ordinary `relax` seeks a minimum, so it is unsuitable for refining a candidate saddle. This tool neither searches a path nor returns a TS-validation verdict.

## Credibility

- **High confidence**: saved coordinates, cell, fixed masks and atom permutation are checked. Successful preparation establishes input consistency only.
- **Medium confidence**: energies, forces and frequencies depend on the electronic model, potentials, converged settings and sampled degrees of freedom.

Frequencies alone require residual-force, mode and spectrum interpretation. Partial vibrations probe active coordinates only; target connectivity requires additional path evidence.

## Reference

- [API and execution examples](references/api.md): read the requested mode, execution or result-reading section as needed. The preparation example below is self-contained.
- [ASE VASP interface](https://docs.ase-lib.org/ase/calculators/vasp.html) and [VASP finite differences](https://vasp.at/wiki/index.php/Phonons_from_finite_differences): authoritative interfaces and calculation limits.

## Input & Output

Save this illustrative request as `request.json`. Choose the physical parameters for the actual system; these values are not universal recommendations.

```json
{"task":"singlepoint","structure_file":"input.extxyz","output_dir":"sp-01","parameters":{"xc":"PBE","encut":500,"ediff":1e-6,"ispin":1,"kpts":[1,1,1]}}
```

```text
python <skill-dir>/scripts/prepare_vasp.py --request request.json
```

Environment: preparation needs Python/ASE and licensed potentials via `VASP_PP_PATH`; execution additionally needs the licensed binary and site launcher/allocation. Reading stored results needs existing compatible files, with no new job. Paths resolve from the request file, or the current directory for `--request -`. The output directory must be new with an existing parent.

Input is one structure with a full-rank cell and 3D PBC. Provide vacuum explicitly for molecules/slabs. `fixed_atoms` uses **one-based original-input indices** and combines with existing `FixAtoms`.

Output: `INCAR`, `POSCAR`, `KPOINTS`, `POTCAR`, `ase-sort.dat`, and a manifest/stdout JSON with parameters, fixed atoms, mappings and POTCAR hash. VASP produces `OUTCAR`, `vasprun.xml` and `CONTCAR`. Energy uses eV; forces eV/Å. ASE 3.26.0 `read_vib_freq()` returns mode energies in **meV**, with imaginary magnitudes in a separate list.

## Procedure Guidance

1. Prepare the requested mode directly with known settings. For `relax`, additionally supply `nsw` and negative `ediffg`; for `vibrations`, use `ediff <= 1e-6` and inspect the active atoms. No preliminary single-point job is required merely to use this skill.
2. For energy comparisons, match functional, potentials, ENCUT, k points, charge/spin policy and corrections. Add magnetism, charge, dispersion or dipole treatment for the actual model; no adsorption-system recipe is assumed.
3. When calculation is requested, run VASP in the generated directory through the existing launcher/batch script. Record job ID/return code and output location. Native VASP relaxation already controls ionic motion.
4. Read the outputs needed for the question; separate prepared/submitted/completed/converged. Frequency generation and TS interpretation are separate. Do not relax away a candidate saddle before its frequency calculation.

## Success Criteria

Helper exit 0 / `status:"success"`, `stage:"inputs_prepared"` means generated files; `vasp_executed:false` remains explicit. Process/scheduler completion does not establish convergence. Physical answers require usable final output and electronic convergence, plus the ionic criterion for relaxation or a complete spectrum for the stated active degrees of freedom for vibrations.

## Matters & Troubleshooting

- Missing potentials: check `VASP_PP_PATH`, library layout and `pp`/`setups`. Do not fabricate POTCAR data. ASE does not install VASP or its potentials.
- Use the manifest/`ase-sort.dat` to restore atom identity. Fixed-atom vibrations require `IBRION=5`; full calculations default to 6. The helper uses `NSW=1`; `POTIM` is displacement size here.
- Nonconvergence: inspect SCF/ionic output before changing budgets. Reaching `NSW` is not convergence. Continue from usable `CONTCAR` in a new directory; electronic restart requires compatible files and explicit tags, as described in the reference.
- Helper scope: mesh k-points, per-element setups, `FixAtoms`, fixed-cell relaxation. Use ASE directly for other workflows. Exit 2 = preparation error; 3 = missing dependency. Install with `python -m pip install ase==3.26.0` if needed.
