# VASP TS Validation API

## Inspect

Required `calculation_dir`; optional `operation:"inspect"`, `imaginary_threshold_cm1` (default 10), `force_tolerance_ev_per_angstrom` (default 0.05), `stationary_outcar`, `reaction_bonds`, `reaction_atom_order`, `input_to_poscar_atom`, and `mode_motion_tolerance` (default 1e-6).

```json
{"calculation_dir":"vib-01","imaginary_threshold_cm1":10,"force_tolerance_ev_per_angstrom":0.03,"reaction_bonds":[{"atoms":[1,2],"change":"forming"},{"atoms":[2,3],"change":"breaking"}]}
```

Pairs default to **one-based POSCAR order**. To keep original-input pairs, declare `reaction_atom_order:"input"` and supply a complete one-based permutation: `input_to_poscar_atom[i-1]` is input atom i's POSCAR index. Supplying a mapping without this declaration is an error. The array must contain every index exactly once; the tool does not infer atom correspondence.

Three-atom mapping illustration (use the full actual permutation for your candidate):

```json
{"calculation_dir":"vib-01","reaction_atom_order":"input","input_to_poscar_atom":[3,1,2],"reaction_bonds":[{"atoms":[1,2],"change":"forming"}]}
```

Here input pair `[1,2]` resolves to POSCAR pair `[3,1]`. Output `atom_indexing.resolved_reaction_bonds` records requested pairs, resolved POSCAR pairs and elements; check these before interpreting motion. This mapping applies to reaction pairs only, never reorders coordinates and does not change preparation's `fixed_atoms` convention. No other skill or manifest format is required.

Checks:

- Completion footer in the last detected VASP run; concatenated earlier runs are excluded when standard headers identify them.
- Explicit electronic loop exits. Every observed exit must say EDIFF was reached; known SCF failures invalidate the evidence. Unsupported exit formats are unknown. This is a supported-record check, not a generic certificate for all VASP builds.
- `IBRION=5/6` and partial-constraint compatibility; one distinct sequential mode per active degree of freedom. Full spectrum expects 3N modes. Partial spectrum expects unfrozen Cartesian degrees of freedom. Missing POSCAR or unsupported spectrum dimensions remains unknown.
- One significant imaginary mode after applying the same cm^-1 magnitude threshold to **every** imaginary mode. Parsed meV values use 1 cm^-1 = 0.1239841984 meV. Weak modes remain visible in the report.
- Candidate-coordinate residual force table. For the frequency OUTCAR, use the first matching unperturbed table; with an explicit `stationary_outcar`, use the last matching table. Coordinates must agree within 1e-5 Å, allowing the supplied cell's periodic equivalence; fixed components are excluded. The caller must supply the same physical model/cell for an external source.

The local verdict is null unless calculation, spectrum, SCF and force evidence are usable. With complete evidence, large active forces or a significant imaginary count other than one yields false. Requested mode compatibility affects `requested_checks_passed`; local saddle support remains separate, including when weak motion makes the requested verdict null.

For key reaction pairs, the tool normalizes the significant mode's maximum atom-vector magnitude to one and computes dimensionless bond-distance derivatives. `mode_motion_tolerance` filters near-zero derivatives; it is a numerical diagnostic tolerance, not a physical rate threshold. Both global mode signs are considered.

| `reaction_mode_check.assessment` | `compatible` | Interpretation |
|---|---|---|
| `compatible` | true | All requested pairs have clear expected motion in one orientation |
| `conflicting_motion` | false | Clear pair motions cannot satisfy the requested changes in either orientation |
| `insufficient_motion` | null | No clear conflict, but at least one requested pair has weak/zero motion |

Each pair reports `motion_status`: `expected`, `opposite` or `unresolved`, in the selected orientation. Missing usable vectors leave `reaction_mode_check` null. A single moving pair establishes participation only, because the global sign is arbitrary. Choose key bonds relevant to this local step; do not require every net reaction change to occur visibly in one mode. These diagnostics never establish or reject target IRC endpoints.

`target_reaction_validated:null` and `coverage.irc:"not_performed"` are intentional. The tool does not ingest a user-supplied success label as evidence.

## Prepare a frequency calculation

```json
{"operation":"prepare_frequency","source_dir":"neb-01","structure_file":"neb-01/02/CONTCAR","output_dir":"vib-check-01"}
```

Required: `source_dir` containing nonempty `INCAR`, `KPOINTS`, licensed `POTCAR`; an ASE-readable `structure_file` already in matching VASP species-block order; new `output_dir` with an existing parent. The helper verifies candidate species blocks against POTCAR `VRHFIN` headers and does not reorder atoms. Existing `FixAtoms`/`FixScaled` flags remain in POSCAR. Optional `fixed_atoms` adds fully frozen atoms in candidate-file order.

Source physical settings, including charge/spin/corrections and atom-ordered magnetization, are retained. The source must use valid settings for this candidate, the same species grouping and an appropriate cell/k-point model. Preparation records provenance but cannot establish the intended chemistry or the authenticity/quality of potentials. It removes standard NEB/VTST optimizer controls, replaces ionic controls with `IBRION=5` for partial coordinates or 6 for full coordinates, `NSW=1`, `ISIF=2`, and starts fresh with `ISTART=0`, `ICHARG=2`. No WAVECAR/CHGCAR is reused. Source ENCUT is explicit; ISPIN follows the source.

Optional numerical settings: `ediff` default 1e-7 (positive, at most 1e-6), `potim` default 0.015 Å, `nfree` 2 or 4 (default 2). These are starting numerical settings, not verified accuracy. This helper targets ordinary VASP GO/NEB controls, not arbitrary specialized input dialects.

Output includes the four standard input files, identity `ase-sort.dat` in the already-sorted candidate order, and `validation-input.json` with hashes, inherited tags and active mode count. It does not run VASP.

## Run and diagnose

```json
{"operation":"run_frequency","calculation_dir":"vib-check-01","command":["mpirun","-np","4","vasp_std"],"timeout_seconds":1800}
```

Required explicit argument-list `command` and positive `timeout_seconds`. Choose the site's known VASP launcher, executable and resource allocation; the example is illustrative. No shell expansions or redirections are interpreted. Commands run from the calculation directory, inherit the current environment, and write `validation.stdout` / `validation.stderr`.

This operation requires a directory created by `prepare_frequency` with unchanged recorded inputs and no existing OUTCAR/run log. It executes once and immediately inspects the output. Optional inspection fields (thresholds, `stationary_outcar`, `reaction_bonds`) also apply. Timeout stops the local process group/tree where supported; scheduler/MPI remote task cleanup remains the site's responsibility. It neither polls nor resubmits queued jobs: use the established site submission tool and inspect after completion.

Launcher failure/timeout is an infrastructure diagnosis, not proof of an invalid TS. Inspect the returned exit code/log paths before retrying. A new attempt uses a new prepared directory; no repeated expensive run is automatic.

## Findings and next actions

| Finding | Suggested interpretation/action |
|---|---|
| `MISSING_FREQUENCY_OUTPUT` | Prepare evidence at the candidate with the same physical model if required |
| `FREQUENCY_RUN_INCOMPLETE` | Recover/finish the job before drawing a mechanism conclusion |
| `SCF_NOT_CONVERGED` / `SCF_EVIDENCE_UNAVAILABLE` | Resolve/check electronic evidence before physical interpretation |
| `SPECTRUM_INCOMPLETE_OR_SCOPE_UNKNOWN` | Check calculation scope, output completeness or unsupported formatting |
| `NO_SIGNIFICANT_IMAGINARY_MODE` | With complete evidence, reconsider/refine candidate; review threshold sensitivity |
| `MULTIPLE_SIGNIFICANT_IMAGINARY_MODES` | Inspect extra unstable motions; clear nonnumerical instabilities can require conformation/path refinement |
| `RESIDUAL_FORCES_TOO_LARGE` | Use an appropriate saddle optimizer or path refinement; this tool does not perform it |
| `UNPERTURBED_FORCES_UNAVAILABLE` | Supply force evidence at the exact candidate geometry |
| `PARTIAL_HESSIAN_ONLY` | Limit conclusions to active coordinates |
| `MODE_INCONSISTENT_WITH_REQUESTED_BOND_CHANGES` | Check mapping/key-bond selection and competing motion before reconsidering the coordinate |
| `REACTION_MODE_MOTION_INCONCLUSIVE` | Weak motion may reflect bending or asynchronous change; inspect the mode/path, not an automatic rejection |

After positive local evidence, target-reaction confirmation still needs bidirectional path tracing, endpoint optimization and identity comparison. Those operations are outside this tool's coverage. Frequency thresholds are configurable and must follow the actual task's rules when used for evaluation.

Diagnostic suggestions guide the model's next decision; they are not mandatory retries or permission to change the intended reaction.
