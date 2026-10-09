---
name: chem-vasp-neb-validation
description: >-
  Inspect existing native VASP/VTST NEB output for band convergence, internal
  inspection structures and comparable sampled barriers. Distinguish a highest
  internal image from a resolved internal maximum; no calculation is launched
  and no frequency or target-reaction verdict is inferred.
license: MIT
compatibility: Python 3.10+ with ASE 3.26.0; existing VASP NEB output and optional endpoint calculation directories; no executable or potential-library installation required for inspection
allowed-tools: Read, Bash, exec_command
---

# VASP NEB Result Validation

## Applicability

Use `scripts/check_neb.py` to read a native VASP/VTST NEB directory and diagnose whether the band's output supports candidate selection and energy comparison. Supply separate optimized endpoint directories when a qualified barrier is required.

This is read-only. It does not launch VASP, initialize a path, verify frequencies or establish IRC endpoint identity. Atom correspondence is supplied, not inferred.

## Credibility

- **High confidence**: extracted markers/energies, hashes and input comparisons in supported formats. Missing or unsupported records remain unknown.
- **Medium confidence**: band convergence is supported by completion, explicit SCF evidence and the optimizer's own reported convergence under a negative EDIFFG. The tool does not recompute projected forces.
- **Medium confidence**: a reported barrier is a sampled result for consistent endpoint/NEB settings, not a vibrationally or mechanistically validated TS barrier.

Unknown evidence remains null; an absent energy is not replaced by a numeric sentinel. Input-setting consistency does not prove that files were never edited after a run.

## Reference

- [API and diagnostics](references/api.md): consult endpoint requirements and findings only when needed. Basic inspection is self-contained below.
- [VASP NEB](https://vasp.at/wiki/index.php/Nudged_elastic_bands) and [VTST NEB](https://vtstools.readthedocs.io/en/latest/neb.html): native band and convergence context.

## Input & Output

Save as `request.json`:

```json
{"neb_dir":"neb-01"}
```

```text
python <skill-dir>/scripts/check_neb.py --request request.json
```

Paths resolve from the request file, or the current directory for `--request -`. The root `INCAR` supplies IMAGES; expected numbered directories include endpoints. Only moving images require NEB output. Optional `endpoint_dirs` is `[reactant_dir, product_dir]`.

Inspection needs Python/ASE and existing files, with no VASP executable or potential library. Energy comparison additionally needs original control files and POTCAR files for hashing.

JSON returns per-image evidence, `neb_convergence_supported`, highest internal image/file, `candidate_status`, optional `sampled_barrier`, findings and next actions. A highest internal image is an inspection structure. Its `candidate_is_provisional` stays true until convergence, usable geometry and comparable endpoints support a resolved internal maximum. Energies use **energy(sigma->0)** in eV; image index 0 is the initial endpoint.

## Procedure Guidance

1. Inspect the existing band directly. Read convergence checks and findings before using its maximum-energy internal image. Missing or unsupported records remain unverified.
2. For a barrier question, provide separate converged endpoint directories. The tool checks physical input tags, POTCAR hashes, KPOINTS, cells and endpoint coordinates before reporting a barrier. It does not rerun endpoints automatically.
3. Use `candidate_status` before transferring an inspection structure. An endpoint maximum or unresolved energy difference does not support an internal TS maximum. Missing endpoint evidence can remain unknown if the question only asks for band diagnostics.
4. Incomplete output needs runtime recovery; an unconverged usable band may need continuation from its final images. Inspect structures around internal dips before considering separate reaction steps; a dip alone establishes neither an intermediate nor a wrong mechanism.

## Success Criteria

Exit 0 / `status:"success"` means diagnosis completed. `neb_convergence_supported:true` concerns band convergence only. `candidate_status:"sampled_internal_maximum"` supports an internal maximum on the sampled band, still requiring local saddle and endpoint-identity evidence. `sampled_barrier` requires convergence and comparable optimized endpoints. `target_reaction_validated` stays null.

## Matters & Troubleshooting

- Completion footer, scheduler success or raw force magnitude alone does not verify NEB convergence. The tool uses the reported optimizer criterion, not an assumed raw-force threshold.
- Explicit VASP SCF loop exits are required for positive support; older formats may need separate review. Missing evidence is not automatically an incorrect reaction mechanism.
- Input-tag comparisons are conservative: equivalent defaults or different textual settings can need manual reconciliation. Use intact original control files and comparable energy conventions.
- A maximum at an endpoint means no resolved internal TS maximum on this sampled path. A selected internal candidate still needs saddle/connectivity evidence.
- Exit 2 = request/parsing error; 3 = missing dependency. Install `ase==3.26.0` if needed. No files are changed and no other skill is required.
