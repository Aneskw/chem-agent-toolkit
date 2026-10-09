# API

## Environment

Use a Linux/WSL virtual environment on the Linux filesystem:

```bash
python3 -m venv ~/.venvs/ts-validation
~/.venvs/ts-validation/bin/python -m pip install pysisyphus==1.0.0 tblite==0.7.0 rdkit==2026.3.6
~/.venvs/ts-validation/bin/python <skill-dir>/scripts/validate_ts.py --check-environment
```

The packages and their scientific dependencies are installed separately. This
adapter calls existing Pysisyphus algorithms and TBLite's GFN2-xTB calculator;
it does not require ORCA, VASP, ASE, or a standalone xTB executable.
On Windows, run these commands inside WSL and use Linux paths such as
`/mnt/d/project/candidate.xyz`.

## Request

Required fields: `guess_file` (one XYZ frame, angstrom), `reactant_smiles`,
`product_smiles`, integer `charge`, `multiplicity` (1), and `output_dir` (new directory).
Both SMILES must match the XYZ's element counts, including hydrogens, and total charge.
Disconnected SMILES are accepted, but bond perception can be ambiguous for fragments.
Relative file paths resolve against the request file's directory.

Optional settings:

| Field | Default | Allowed range / meaning |
|---|---:|---|
| `threads` | 2 | 1–16; numerical-Hessian force evaluations are serial |
| `timeout_seconds` | 300 | 1–3600; wall-time limit for the whole calculation |
| `ts_max_cycles` | 200 | 1–500 |
| `irc_max_cycles` | 100 | 1–500, per direction |
| `endpoint_max_cycles` | 200 | 1–500, per endpoint |
| `imaginary_threshold_cm1` | 0 | 0–100; count frequencies strictly below minus this value |
| `hessian_step_bohr` | 0.005 | 0.001–0.02; central finite-difference displacement |

Use the default zero threshold to count all negative projected vibrational
frequencies. A positive threshold excludes weak negative modes and changes the
criterion; the report records both the threshold and excluded modes.
Units: XYZ in angstrom, energies in hartree, forces in hartree/bohr, frequencies
in cm⁻¹. Negative signed frequencies represent imaginary modes.

## Calculations

1. Pysisyphus restricted-step partitioned rational-function TS optimization
   (`RSPRFOptimizer`, lowest Hessian root). Initial numerical Hessian; recalculate
   every five optimization cycles; Bofill updates between recalculations.
2. Fresh central numerical Hessian, mass weighting, translation/rotation projection,
   and vibrational eigenanalysis at the refined stationary structure.
3. Bidirectional Euler predictor-corrector IRC (`EulerPC`), starting along the single
   imaginary mode, with Hessian recalculation every five cycles.
4. Independent endpoint rational-function optimization (`RFOptimizer`) with an
   initial numerical Hessian, recalculation every five cycles, and fresh-force checks.
5. RDKit `DetermineBonds` at each endpoint with the supplied total charge, followed
   by canonical, hydrogen-normalized, map-free, nonstereochemical SMILES comparison.

TS and endpoint optimizations use `gau_tight` convergence. Additional fresh-force
limits are maximum 1.5×10⁻⁵ and RMS 1×10⁻⁵ hartree/bohr. Both endpoints must be at
least 10⁻⁸ hartree below the TS. IRC convergence uses the library's gradient or
energy-plateau checks; the report records each branch's reason, and endpoint
optimization is required even after an IRC energy plateau.

## Results and inspection

`report.json` includes `environment`, resolved `settings`, stage results, numerical
values, endpoint pairs, `failure_stage`, `failure_kind`, and artifact hashes.
`imaginary_mode.json` gives normalized Cartesian atomic motion; its overall sign
is arbitrary. Endpoint sections also report TS-minus-endpoint electronic energies
in kJ/mol, without zero-point, thermal, or solvent corrections. Endpoint frequencies
are not calculated; these are tightly relaxed structures, not independent Hessian
certifications of every endpoint minimum.

| Result | `passed` | `target_reaction_validated` | Interpretation |
|---|---|---|---|
| `passed` | true | true | All checks passed on the stated surface |
| `failed`, `not_first_order_saddle` | false | null | Refined stationary structure has the wrong mode count |
| `failed`, `wrong_endpoints` | false | false | Complete tracing connected a different molecular pair |
| `inconclusive` | null | null | Nonconvergence, timeout, numerical error, or ambiguous bonding |

`--inspect OUTPUT_DIR` performs no physical calculation. It checks the stored
artifact hashes and returns the saved diagnosis. Changed/missing artifacts clear
the verdict to `inconclusive`; hashes check local consistency, not authenticity.
`worker.stdout.log` and `worker.stderr.log` contain calculation diagnostics.

Exit codes: 0 = report produced (including chemical failure or insufficient
evidence); 2 = invalid request/file; 3 = environment unavailable. Missing native
libraries can instead appear as an initialization error in the report.
Requests never overwrite an existing output directory. A timeout terminates the
worker process group and preserves files from completed stages.
