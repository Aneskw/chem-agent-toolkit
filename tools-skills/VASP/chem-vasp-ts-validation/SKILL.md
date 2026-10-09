---
name: chem-vasp-ts-validation
description: >-
  Check local vibrational saddle evidence for an existing VASP TS candidate.
  Inspect frequencies, convergence, residual forces and optional key-bond motion;
  prepare or run missing frequency evidence with supplied VASP settings.
  Target-reaction endpoint validation is outside this tool's scope.
license: MIT
compatibility: Python 3.10+ with ASE 3.26.0; existing VASP files for inspection/preparation; licensed VASP and a configured local/compute-node launcher for execution
allowed-tools: Read, Write, Bash, exec_command
---

# VASP Local Saddle Evidence

## Applicability

Use `scripts/validate_ts.py` when the question is whether a supplied candidate has local saddle evidence. Start with existing frequency output; prepare or run new evidence only when needed. A completed diagnosis supports choosing whether to retain, refine or investigate the candidate.

The tool does not refine a saddle, run IRC or identify reaction endpoints. It reads VASP output; other engines require their own parser.

## Credibility

- **High confidence**: extracted mode counts, units, matching-coordinate forces and recorded provenance in supported formats. Missing or unsupported records remain unknown.
- **Medium confidence**: a complete, converged calculation with small unperturbed forces and one significant imaginary mode supports a local first-order saddle in the checked degrees of freedom. Thresholds and numerical settings can affect this conclusion.
- **Low confidence**: key-bond motion diagnoses local compatibility. Weak motion is inconclusive; conflicting motion warrants inspection. Neither proves or rejects the full mechanism.

`target_reaction_validated` remains null. Unknown evidence must remain unknown, even when the structure looks plausible.

## Reference

- [API](references/api.md): read preparation/execution fields only when new computation is needed, or mode fields when checking specific bond changes. Inspection needs only the example below.
- [VASP finite differences](https://vasp.at/wiki/index.php/Phonons_from_finite_differences) and [VASP IRC](https://vasp.at/wiki/index.php/IRC_calculations): calculation and connectivity criteria.

## Input & Output

Save as `request.json`:

```json
{"calculation_dir":"vib-01"}
```

```text
python <skill-dir>/scripts/validate_ts.py --request request.json
```

Default operation is `inspect`, using `OUTCAR`, `INCAR` and `POSCAR` in that directory. Paths resolve from the request file, or the current directory for `--request -`. No inspected file is modified.

| Operation | Required environment |
|---|---|
| `inspect` | Python/ASE and existing VASP files; no executable or potential library |
| `prepare_frequency` | Python/ASE, candidate, source INCAR/KPOINTS and licensed POTCAR |
| `run_frequency` | Prepared inputs, licensed executable and known launcher/resource allocation |

JSON reports `requested_checks_passed`, local saddle support, individual checks, significant/weak imaginary modes, active residual force, coverage, findings and next actions. Verdicts are **true / false / null**: supported, failed a physical check, or insufficient evidence. Tool execution status is separate.

Defaults: imaginary threshold **10 cm^-1**, active force tolerance **0.05 eV/Å**. These configurable criteria do not replace a benchmark's rules. Reaction pairs default to **one-based POSCAR order**; original-input pairs require explicit `reaction_atom_order:"input"` and a complete `input_to_poscar_atom` permutation. Resolved pairs and elements are returned.

## Procedure Guidance

1. Inspect existing output directly. Read the checks/findings before accepting a local saddle; missing/truncated output, unknown SCF evidence or incomplete spectra cannot pass.
2. If frequency evidence is missing, use `prepare_frequency` with a candidate structure and source VASP control directory. It preserves physical tags, POTCAR order and KPOINTS, removes NEB/ionic controls and writes fresh frequency inputs. No ordinary minimum relaxation is inserted before frequency analysis.
3. When the task requires calculation and the runtime is known, use `run_frequency` with the explicit command and time budget, or submit the prepared directory through the existing site scheduler. Inspect after a submitted job finishes. Execution is never an automatic side effect of `inspect` or preparation.
4. Add only the key `reaction_bonds` whose local motion matters to the question. Inspect resolved indices/elements before interpreting motion. Compatible, conflicting and insufficient motion are separate outcomes; zero or weak motion does not reject a mechanism.
5. Use findings to choose the next action: incomplete evidence needs recovery; large forces need saddle/path refinement; additional clear unstable modes need mode/conformation inspection. This tool performs no saddle refinement. Even positive local evidence requires bidirectional path and endpoint evidence for target-reaction confirmation.

## Success Criteria

Exit 0 / `status:"success"` means the requested operation completed. `first_order_saddle_supported_in_checked_subspace:true` supports local evidence only. `requested_checks_passed` also includes requested mode compatibility; insufficient motion gives null even with local support. Partial Hessians cover active coordinates only. `target_reaction_validated` stays null.

## Matters & Troubleshooting

- Residual forces come from a force table whose coordinates match the candidate, not blindly from the final displaced frequency geometry. Supply `stationary_outcar` only for the same candidate, order and physical model.
- Supported SCF evidence uses explicit VASP loop-exit messages. Older/alternative formats without these remain unknown; check their convergence records rather than calling the candidate chemically invalid.
- The tool requires the expected complete active spectrum; unusual zero-mode embedding or output formatting remains unverified. Partial selective dynamics uses `IBRION=5`; full preparation uses 6.
- Small imaginary modes require numerical sensitivity checks when consequential. Do not confuse **10 cm^-1** with **10 meV**. Mode motion alone does not distinguish all mechanisms.
- Preparation never overwrites a directory or redistributes licensed data. Execution refuses existing run output and performs no automatic retry. Use the site scheduler for queued jobs; `run_frequency` is a synchronous local/allocated-node launcher.
- Exit 2 = request/parsing/preparation error; 3 = missing dependency. Install `ase==3.26.0` if needed. No cross-skill dependency is required.
