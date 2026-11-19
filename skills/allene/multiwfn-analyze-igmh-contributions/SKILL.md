---
name: multiwfn-analyze-igmh-contributions
description: Use Multiwfn to calculate IGMH interfragment interaction grids and atomic-pair contributions from a prepared molecular wavefunction, for comparing contacts in molecular complexes or catalyst structures.
---

# IGMH interaction fields and contributions

Analyze contacts between specified fragments using Hirshfeld-partitioned molecular electron density. Start with a prepared wavefunction at an appropriate geometry and a scientifically meaningful fragment assignment. Geometry optimization and interaction-energy decomposition are outside this workflow.

## Setup and inputs

Use **Multiwfn 2026.11.10**, Windows 64-bit. Obtain `Multiwfn_2026.11.10_bin_Win64.7z` from the [official download page](http://sobereva.com/multiwfn/download.html) and unpack it. Keep the supplied runtime files, `settings.ini` and `examples` directory. Set `nthreads` in `settings.ini` to the physical CPU core count. Consult the [2026.11.3 manual](http://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf), sections 2.1–2.5, for setup or input-format details.

| Input | Requirement |
|---|---|
| Wavefunction | Use `.wfn`, `.wfx`, `.fch`/`.fchk`, `.mwfn` or a compatible `.molden` containing atomic coordinates and Gaussian-type orbital information. Geometry-only `.xyz`/`.pdb` files cannot supply IGMH density. |
| Fragments | Use atom indices from the loaded file. Fragments must not share atoms. They may cover only part of the system; omitted atoms are outside the selected fragment analysis. |
| Output directory | Invoke Multiwfn from a dedicated directory for each structure; its fixed-name outputs go into that directory, rather than beside the input wavefunction. |

For ordinary full-grid analysis retain the default `IGMvdwscl=0` in `settings.ini`. A positive value enables overlap-region screening and makes the resulting grids suitable only for interfragment isosurfaces; too small a value can truncate them.

## Representative calculation

This example uses the dimer wavefunction bundled with Multiwfn: fragment 1 is atoms 1–12 and fragment 2 is atoms 13–25. For your own complex, replace both the input and fragment lists; do not reuse these indices without checking the atom order.

From an existing output directory, run in PowerShell, replacing the installation path:

```powershell
$multiwfnDir = 'C:\Tools\Multiwfn_2026.11.10'
& "$multiwfnDir\Multiwfn.exe" "$multiwfnDir\examples\2-pyridoxine_2-aminopyridine.wfn" -set "$multiwfnDir\settings.ini"
```

Explicit `-set` keeps the intended configuration when running outside the installation folder. At the interactive prompts, enter these lines in order:

```text
20
11
2
1-12
13-25
2
3
```

These select visual interaction analysis → IGMH, define two fragments, choose a medium-quality field grid and export cube files. Medium quality is the manual's representative field-grid choice, not a universal convergence criterion. For larger or more diffuse contacts, adjust the grid box to enclose the region of interest and check grid sensitivity when comparing structures.

After export, choose **6** in the post-processing menu to calculate atomic and atomic-pair delta-g indices. Choose the integration-grid quality at its prompt; the manual demonstrates high quality for these indices. This integration grid is separate from the field grid selected above. With more than two fragments, option 6 asks which two to analyze. Retain `atmdg.txt`; the optional `atmdg.pdb` export is only needed for atom coloring.

## Outputs and interpretation

| Result in the invocation directory | Meaning and use |
|---|---|
| `dg_inter.cub` | Interfragment delta-g field: locates interaction regions between the defined fragments. |
| `sl2r.cub` | `sign(lambda2)*rho`, evaluated from actual molecular density; use as the coloring field on a delta-g-inter isosurface in a downstream renderer. |
| `atmdg.txt` | Sorted atomic and atomic-pair delta-g indices and percentage contributions, plus the sum of pair indices. Use atom numbers to identify prominent contacts. |
| Optional `atmdg.pdb` | Atom coloring data: `beta` is the atomic delta-g index multiplied by 10; `occupancy` is its percentage contribution. |

Option 3 also exports total and intrafragment field grids. Option 4 provides direct isosurface inspection within Multiwfn. Color-mapped external rendering is a separate handoff: preserve the paired cube files and consult manual section 4.20.11 for its rendering example.

Larger pair indices identify more prominent contributions under the chosen partition; the percentages are **not percentages of interaction energy**. For the density coloring field, negative values indicate attractive character, positive values indicate steric character, and values near zero characterize low-density contacts. Keep fragment definitions, computational inputs and display settings comparable before interpreting differences between structures. The manual's example omits zero terms from its displayed pair list; absence there is not a software failure or proof of an energy contribution being exactly zero.

If the input contains only coordinates, obtain a supported wavefunction before proceeding; selecting geometry-only IGM would change the method. If calculation crashes on a large system, the manual recommends checking OpenMP stack allocation (`ompstacksize` on Windows). Exported files establish calculation artifacts, not validated scientific conclusions.

For research use, follow the citation requirements on the download page and `How to cite Multiwfn.pdf` in the distribution. The [IGMH method paper](https://doi.org/10.1002/jcc.26812) and its [implementation erratum](https://doi.org/10.26434/chemrxiv-2022-g1m34) describe the method behind these descriptors.
