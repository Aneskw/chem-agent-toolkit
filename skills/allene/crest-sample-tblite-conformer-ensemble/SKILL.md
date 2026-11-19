---
name: crest-sample-tblite-conformer-ensemble
description: Sample GFN2 conformers with CREST's integrated tblite backend and TOML input, in gas phase or with ALPB solvent, without a separate xTB executable. Use for downstream DFT or conformer-dependent calculations.
---

# Sample a molecular conformer ensemble with CREST

Use CREST 3.0.2 to search from one prepared molecular geometry and retain unique low-energy conformers. DFT refinement, frequency verification and property calculations are subsequent handoffs.

## Environment and starting structure

Use a GNU/Linux host and the official [CREST 3.0.2 release](https://github.com/crest-lab/crest/releases/tag/v3.0.2). Its [GNU binary archive](https://github.com/crest-lab/crest/releases/download/v3.0.2/crest-gnu-12-ubuntu-latest.tar.xz) is version-pinned despite the asset filename. Unpack it, make the `crest` binary executable if necessary, and add its containing directory to `PATH`. See the [official installation guide](https://crest-lab.github.io/crest-docs/page/installation/install_basic.html) for platform/setup details; that guide was tested on Ubuntu 20.04 LTS.

The GFN2 calculation below uses integrated tblite. A separate `xtb` executable is not needed for this primary workflow. External-xtb features and additional search modes require their own prerequisites.

Supply `struc.xyz` containing one molecule with all required atoms, including hydrogens:

| Part | Required content |
| --- | --- |
| First line | Number of atoms, N |
| Second line | Comment, which may be blank |
| Next N lines | Element symbol and x, y, z coordinates in angstroms |
| Electronic state | Known net molecular charge and N-alpha minus N-beta electron count |

Prefer a geometry already optimized at the intended search level. CREST uses the starting structure as a reference for topology checks, so distorted coordinates can affect which structures survive sorting. Preparation of this geometry is an external input.

Use a fresh working directory for each molecule and parameter set. Keep the original geometry elsewhere: CREST creates intermediate files and can overwrite its working `coord` file.

## Run an iMTD-GC search

Place `struc.xyz` and the following `input.toml` together in the working directory. This example selects gas-phase GFN2, a neutral closed-shell molecule, four threads and a 6 kcal/mol ensemble window:

```toml
input = "struc.xyz"
runtype = "imtd-gc"
threads = 4

[cregen]
ewin = 6.0

[calculation]
[[calculation.level]]
method = "gfn2"
charge = 0
uhf = 0
```
Change `charge` and `uhf` to the supplied electronic state; for GFN2, `uhf` is N-alpha minus N-beta, so a singlet uses 0, not multiplicity 1. Choose `threads` for the available CPUs. `ewin` is the sorting/retention window above the lowest conformer found, in kcal/mol; it is not a guarantee of complete sampling.

For implicit-water sampling, add `alpb = "h2o"` inside the same `[[calculation.level]]` block. Keep the solvent model consistent with the intended preparation and downstream comparison. Gas phase and implicit solvent are distinct calculation choices.

From that directory, run:

```bash
crest input.toml > crest.out 2>&1
```

Relative paths resolve from the working directory. Inspect the startup settings in `crest.out` for the intended method, charge, thread count, solvent choice and window. The UHF parameter is printed only when nonzero. Unknown TOML keywords are an error in 3.0.2; correct the input rather than continuing from partial output. The [official sampling example](https://crest-lab.github.io/crest-docs/page/examples/example_1.html) illustrates the workflow; the TOML above uses the 3.0.2 interfaces.

## Inspect and hand off the ensemble

A successful run ends with `CREST terminated normally.` Check the energy/population table and the output files together:

| File or log field | Use |
| --- | --- |
| `crest_conformers.xyz` | Concatenated XYZ blocks for unique conformers; the usual input ensemble for separate DFT refinement. |
| `crest_rotamers.xyz` | Conformers plus degenerate rotamers; use when that additional degeneracy information is needed. |
| `crest.energies` | One-based conformer index and relative energy in kcal/mol, following the conformer-only ensemble order. |
| `crest_best.xyz` | Lowest-energy geometry found; retain other low-energy candidates for subsequent refinement. |
| `crest.out`, `Erel/kcal` | Relative energies at the search model, in kcal/mol. Check the reported sorting window and number of retained structures. |
| `crest.out`, weights/populations | Model-dependent population estimates; these belong to the search calculation. |

Preserve each complete XYZ block and its atom ordering when exporting individual conformers for downstream calculations. Keep the search settings and log with the ensemble. Recompute energies and populations at the downstream level when the subsequent method requires them; CREST search populations are not DFT populations or experimental measurements.

A single retained conformer can be a valid result for a rigid molecule. An empty or missing ensemble, an error message, or absent normal termination requires investigation; do not interpret partial files as evidence that no conformers exist. Successful termination and a chosen energy window do not establish exhaustive coverage or a verified global minimum.

The conformer XYZ comment contains the total search-level energy in hartree; distinguish it from the relative kcal/mol values in `crest.energies`. Rotamer and conformer-only frame numbering need not match.
