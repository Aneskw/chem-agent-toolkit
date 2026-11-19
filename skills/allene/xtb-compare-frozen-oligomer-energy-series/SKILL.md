---
name: xtb-compare-frozen-oligomer-energy-series
description: Optimize a prepared supramolecular oligomer with GFN2-xTB and collect frozen-fragment electronic energies from a common parent geometry for oligomer-size comparisons.
---

# GFN2-xTB energies from a common oligomer geometry

Use this workflow for a noncovalent stack with known atom membership for each building block. It produces an optimized parent, unchanged-coordinate central fragments and an electronic-energy table. Starting structures and the molecular model must already be supplied.

## Software and inputs

Use **xTB 6.8.0** throughout the series. Obtain the platform archive and matching checksum from the [official release](https://github.com/grimme-lab/xtb/releases/tag/v6.8.0). Extract it, retain its parameter files, and make the executable available as `xtb` on PATH. Set `XTBPATH` to the installation's `share/xtb` directory for parameter/configuration lookup. See the [official setup guide](https://xtb-docs.readthedocs.io/en/latest/setup.html) for platform environment and OpenMP stack/thread settings; large oligomers can require substantial memory per thread. Confirm the resolved binary with `xtb --version`.

Supply:

| Input | Required meaning |
| --- | --- |
| `parent.xyz` | Chemically valid 16-building-block stack in standard XYZ: atom count, comment line, then element and Cartesian coordinates in angstroms. Include hydrogens. |
| Atom membership | Map each coordinate row to a whole monomer; label monomers 1–16 along the stack. Do not assume atoms are contiguous by monomer. |
| Electronic state | Total charge and number of unpaired electrons for parent and fragments. `--uhf` takes unpaired electrons, not spin multiplicity. |
| Model choices | Fixed chemical substitutions, solvent treatment and computational settings for the series. |

The example below uses neutral closed-shell fragments, normal optimization, accuracy 1.0 and electronic temperature 300 K, with no implicit solvent. Electronic temperature is an SCC occupation setting, not a solution-temperature model. Adapt charge/spin to each actual fragment. Changes to solvent or chemical truncation define a different calculation series and must be recorded.

Use fresh directories for each calculation: xTB writes fixed output names and reads local state/configuration. Check for unintended settings in local `xcontrol` or global configuration under `XTBPATH`. Retain the original inputs separately.

## Optimize the parent

Create `series/parent-opt`, place the supplied `parent.xyz` there, and run these PowerShell commands from the directory containing `series`:

```powershell
Set-Location series/parent-opt
xtb parent.xyz --gfn 2 --opt normal --acc 1.0 --etemp 300 --chrg 0 --uhf 0 > optimization.out 2>&1
```

Inspect `optimization.out` for `GEOMETRY OPTIMIZATION CONVERGED` and the final summary. Reject a failed SCC calculation or `ANCopt failed to converge the optimization`; an output geometry can still be written after optimization failure. A zero exit status or an existing XYZ alone does not establish convergence.

Keep `xtbopt.xyz` as the common optimized parent. `parent.xyz` is not overwritten; `xtbopt.log` is the optimization trajectory. Verify that the supplied atom-membership map still identifies the intended building blocks in the optimized geometry.

## Extract central fragments

Create each fragment directly from the converged `xtbopt.xyz`, retaining these parent monomer IDs:

| Size n | Retained monomers | Removed from each end |
| --- | --- | --- |
| 16 | 1–16 | 0 |
| 12 | 3–14 | 2 |
| 10 | 4–13 | 3 |
| 8 | 5–12 | 4 |
| 6 | 6–11 | 5 |
| 4 | 7–10 | 6 |
| 2 | 8–9 | 7 |

Copy only the retained monomers' complete atom records into each fragment XYZ. Preserve every retained coordinate and atom order, update the first-line atom count, and replace the comment with the parent identifier and retained monomer IDs. Use the membership map to remove atoms; do not split the file into equal line blocks unless the map establishes that layout. Check atom count, composition and membership against the retained monomers.

Delete whole noncovalently associated molecules, without cutting covalent bonds, adding caps or optimizing the fragments. If a different chemical model is needed, prepare it before parent optimization. Save each size as `series/sp-N/fragment.xyz`, including a copy of the full optimized parent in `series/sp-16/fragment.xyz`.

## Calculate and collect energies

Run a single point for every size, including n=16, with the same settings. For example, from `series/sp-12`:

```powershell
xtb fragment.xyz --gfn 2 --sp --acc 1.0 --etemp 300 --chrg 0 --uhf 0 > singlepoint.out 2>&1
Select-String -Path singlepoint.out -Pattern 'TOTAL ENERGY' | Select-Object -Last 1
```

Repeat in the other `sp-N` directories. Use only `--sp` as the run type: xTB honors only the first run type supplied. An optimization would relax the frozen fragments. These runs use the native GFN2 implementation without `--tblite`. Separate directories keep restart files and fixed-name outputs from colliding.

Read the final `TOTAL ENERGY` summary in **Eh (Hartree)** after inspecting each run's warnings and completion. Severe errors produce a nonzero exit status and diagnostics; incomplete or failed runs have no usable energy entry. The `energy` file is another energy output, in TURBOMOLE format. Use the final summary energy, not an intermediate SCC iteration value.

Write `series/energies.csv` with one row per successful size, using columns `n,retained_parent_monomers,atom_count,charge,unpaired_electrons,energy_Eh,xyz_path,output_path`. Retain the parent XYZ, membership map, version banner and exact commands with this table. Keep failed sizes in a separate failure record rather than filling missing energies with zero.

## Interpret the series

The result is a set of electronic energies evaluated on geometries inherited from one optimized parent. Raw total energies at different atom counts are not directly a binding or cooperativity measure. Binding energies require an explicitly chosen reference composition, reference geometry and normalization, evaluated with compatible settings. This workflow does not infer those choices or fit thermodynamic parameters.

Use the table as input to a separately specified energy analysis. Keep electronic energies distinct from free energies, experimental aggregation parameters and evidence of a global minimum. Recalculate a complete series when changing xTB version: release 6.8.0 includes numerical changes, so mixing releases can affect energy differences.

For option and file-format lookup, use the [versioned xTB 6.8.0 manpage](https://github.com/grimme-lab/xtb/blob/v6.8.0/man/xtb.1.adoc) and the [optimization guide](https://xtb-docs.readthedocs.io/en/latest/optimization.html).
