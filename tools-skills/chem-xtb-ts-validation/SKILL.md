---
name: chem-xtb-ts-validation
description: >
  Validate a molecular transition-state guess with gas-phase GFN2-xTB: refine the
  saddle, calculate vibrational frequencies, trace both IRC directions, and compare
  optimized endpoints with target SMILES. Invoke when a candidate TS needs physical
  and reaction-connectivity checks or when an unsuccessful validation needs diagnosis.
license: MIT
compatibility: Linux or WSL; Python 3.10+ with pysisyphus, tblite, and rdkit. No external xTB executable required.
allowed-tools: Bash, Read, Write
---

# Molecular TS Validation with GFN2-xTB

## Applicability

Use for a candidate XYZ and a specified reactant/product pair. The tool performs
actual energy, force, numerical Hessian, and intrinsic reaction coordinate (IRC)
calculations. It supports isolated, closed-shell singlet molecules with 2–60 atoms
of H, B, C, N, O, F, Si, P, S, Cl, Br, or I. Explicit hydrogens are required in XYZ.
It does not generate an initial mechanism or validate periodic surfaces, radicals,
spin changes, or stereochemical selectivity.

## Credibility

- **High confidence:** reported completion, numerical values, convergence checks,
  and exact canonical endpoint comparison under the recorded settings.
- **Medium confidence:** a pass establishes a first-order saddle connecting the
  target pair on the GFN2-xTB surface. It does not establish a DFT-quality barrier,
  the dominant experimental pathway, or validity at another electronic-structure level.
- **Low confidence:** endpoint bonding assignments for unusual or separated ionic
  fragments. Inspect the endpoint XYZ files before interpreting an unexpected mismatch.

## Reference

The workflow follows [TSBench, Methods 4.5](https://arxiv.org/html/2609.08503v1),
using [Pysisyphus](https://github.com/eljost/pysisyphus),
[TBLite](https://tblite.readthedocs.io/), and [RDKit](https://www.rdkit.org/docs/).
Read [the API reference](references/api.md) for installation, settings, or result details.

## Input & Output

Create a JSON request, with file paths relative to that request:

```json
{
  "guess_file": "candidate.xyz",
  "reactant_smiles": "C#N",
  "product_smiles": "[C-]#[NH+]",
  "charge": 0,
  "multiplicity": 1,
  "output_dir": "validation-01",
  "timeout_seconds": 300
}
```

Supply the actual reaction's SMILES and charge. The output directory must be new.
The tool returns JSON and saves `report.json`, refined structures, calculated
frequencies, a Hessian, IRC trajectory, and logs as stages complete.

## Procedure Guidance

1. If the task needs physical validation and a candidate exists, run:
   `python <skill-dir>/scripts/validate_ts.py --request request.json`.
   Check the environment only if dependencies are uncertain:
   `python <skill-dir>/scripts/validate_ts.py --check-environment`.
2. Read `status`, `failure_stage`, `failure_kind`, and `stages`. A negative frequency
   alone is insufficient: both IRC branches and endpoint optimizations must complete.
3. For `wrong_endpoints`, inspect the observed SMILES and endpoint geometries and
   revise the candidate mechanism. For nonconvergence, inspect the failed stage's
   logs before adjusting that stage's budget or the initial geometry.
4. Inspect existing results without rerunning calculations:
   `python <skill-dir>/scripts/validate_ts.py --inspect validation-01`.

## Success Criteria

`status="passed"` and `target_reaction_validated=true` require tight TS convergence,
exactly one imaginary vibrational mode, two converged IRC branches, two tightly
optimized lower-energy endpoints, and an unordered match to both target SMILES.
Atom maps and stereochemistry are removed for comparison.
`failed` means a completed check found a non-saddle or the wrong endpoint pair.
`inconclusive` means the calculation or interpretation lacks sufficient evidence;
`passed=null` is not a failure of the proposed chemistry. Exit code 0 means the
diagnosis was produced, not that the candidate passed.

## Matters & Troubleshooting

Default budget: 2 threads, 300 seconds, 200 TS steps, 100 IRC steps per direction,
and 200 optimization steps per endpoint. Numerical Hessians cost many force calls;
larger molecules can exhaust this budget. Partial evidence is retained on timeout.
Do not silently change charge, targets, method, or the imaginary-frequency threshold
to obtain a pass. Geometry-only interpolated paths are not validated IRC paths.
If dependencies are unavailable, use the API installation instructions; never
substitute a visual assessment for a completed calculation.
