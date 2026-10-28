# VASP NEB Validation API

## Request and files

```json
{"neb_dir":"neb-01","endpoint_dirs":["reactant-go","product-go"]}
```

Required `neb_dir` with root `INCAR` containing `IMAGES` in 1..98 and numbered image POSCARs `00..(IMAGES+1)`. Internal images need OUTCAR for positive support. Endpoint OUTCAR files inside the band are optional and do not substitute for explicitly supplied comparable endpoint results when qualifying a barrier.

Optional `endpoint_dirs` contains reactant and product directories in that order. Each should contain its original `INCAR`, `KPOINTS`, `POTCAR`, final `CONTCAR` and `OUTCAR`. The tool requires completion, explicit electronic convergence and reported ionic convergence for these optimized endpoints. Static endpoint calculations with separately certified optimization need manual review; this interface does not accept a user-declared convergence flag.

## Checks and interpretation

`neb_convergence_supported:true` requires all moving images to have a finish footer and `reached required accuracy` marker, explicit observed electronic loop exits reaching EDIFF, consistent finite image cells/element order, and a negative root EDIFFG. This reports the optimizer's convergence evidence; it does not independently calculate band-projected forces or verify binary feature support.

The parser uses the last identifiable VASP run for concatenated outputs and reads the last `energy(sigma->0)` with finite numeric values, including exponent notation. Missing energies remain null. Every observed SCF exit is checked conservatively; alternative formats without explicit exits remain unknown.

Energy consistency compares POTCAR SHA-256, KPOINTS content excluding its title, cell, and physical INCAR tags after excluding calculation-mode, convergence-budget, restart and output/parallel controls. Numeric scalar representations are normalized; implicit defaults, vector notation and equivalent-but-different k-point files are not resolved automatically. The compared source controls must be the originals for the results. The check does not independently reconstruct all runtime physics from OUTCAR, compare VASP versions or prove the same converged electronic state.

The endpoint CONTCAR must match its band endpoint element order and coordinates within 1e-5 Å, allowing periodic equivalence in the band cell. Atomic identity beyond supplied order is not inferred. Identical geometry/order is not a chemical graph or stereochemistry comparison.

## Outputs

- `images`: per-image paths, completion, electronic evidence, optimizer-reported convergence and energy. Endpoint rows include explicitly supplied external results when present.
- `highest_energy_internal_image_index` / `highest_energy_internal_geometry_file`: an inspection structure at the maximum known internal energy; index is null if any internal energy is missing. A usable file requires a readable single-frame CONTCAR with finite coordinates and matching cell/element order. It is not a frequency or reaction verdict.
- `candidate_image_index` / `candidate_geometry_file`: aliases for that inspection structure, accompanied by `candidate_status` below. `candidate_is_provisional` is false only for `sampled_internal_maximum`; this still does not certify a TS.
- `sampled_barrier`: only when convergence, settings and optimized endpoint geometry checks pass. Includes forward/reverse barriers, reaction energy and maximum index using one energy convention. No frequency or IRC claim is attached.
- `internal_minimum_indices`: strict local energy minima beyond a 1e-4 eV numerical comparison tolerance. This threshold is for flagging profile features, not claiming a physical intermediate.
- `coverage`, `findings`, `next_actions`: what was checked and a concise diagnostic route. No automatic computation, cropping or mechanism change occurs.

| `candidate_status` | Meaning |
|---|---|
| `unavailable` | Internal energies do not support selection |
| `geometry_unavailable` | A highest internal image is known but its final geometry is unusable |
| `unverified_band` | Band convergence evidence is insufficient |
| `endpoint_comparison_unavailable` | Band evidence is supported; comparable optimized endpoints are still missing/unusable |
| `no_resolved_internal_maximum` | The internal maximum does not clearly exceed both qualified endpoints |
| `sampled_internal_maximum` | Converged band, usable geometry and qualified endpoints support an internal sampled maximum |

`checks.internal_maximum_above_endpoints` is true/false/null. Comparison requires compatible settings and optimized endpoint geometries matching the band. A 1e-4 eV comparison tolerance prevents labelling an unresolved difference as a clear internal maximum; it is not a barrier accuracy guarantee. Endpoint maxima retain an inspection structure with a provisional label. A qualified sampled barrier may be zero in one direction; that does not establish an internal TS. Path resolution, frequencies and target identity remain separate evidence.

## Common findings

| Finding | Next decision |
|---|---|
| `NEB_RUN_INCOMPLETE` | Recover missing output/job state before judging the mechanism |
| `NEB_OPTIMIZER_CONVERGENCE_NOT_REPORTED` | Inspect the last band/projected forces; continue usable final images if appropriate |
| `SCF_NOT_CONVERGED` / `SCF_EVIDENCE_UNAVAILABLE` | Repair or verify electronic evidence |
| `ENERGY_SETTINGS_MISMATCH` | Reconcile physical settings/potentials/cells before energy comparison |
| `COMPARABLE_ENDPOINT_RESULTS_NOT_SUPPLIED` | Supply separate endpoint results only if needed for the question |
| `ENDPOINT_RESULT_UNCONVERGED_OR_GEOMETRY_MISMATCH` | Check endpoint optimization and correspondence |
| `ENERGY_MAXIMUM_IS_AN_ENDPOINT` | No resolved internal energy maximum; review path/resolution |
| `NO_RESOLVED_INTERNAL_MAXIMUM` | Keep the structure provisional; inspect endpoint quality and image resolution |
| `INTERNAL_ENERGY_MINIMA` | Inspect nearby geometries before deciding whether intermediate states justify separate path segments |

If the band is suitable, select its candidate for subsequent physical saddle/connectivity assessment. This tool does not perform that assessment and does not require a particular external skill.
