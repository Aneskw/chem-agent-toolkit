---
name: multiwfn-export-wavefunction-nci-grids
description: Use Multiwfn to generate wavefunction-based NCI signed-density and RDG grids, inspect their scatter plot, and export paired cube files for molecular interaction visualization.
---

# Wavefunction-based NCI analysis with Multiwfn

## Prepare the program and input

Use **Multiwfn 2026.11.3, Windows 64-bit GUI binary** from the [official download page](http://sobereva.com/multiwfn/download.html) ([versioned archive](http://sobereva.com/multiwfn/misc/Multiwfn_2026.11.3_bin_Win64.7z)). Extract the complete archive, retaining its runtime DLL, `settings.ini`, and `examples` directory. The noGUI build cannot display the scatter plot. Consult the [matching manual](http://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf), sections 2.1–2.5 for setup and 3.23.1 for NCI details. Follow the download terms and bundled `How to cite Multiwfn.pdf` when publishing results.

Supply an already prepared molecular wavefunction, for example `complex.fch`, `.fchk`, `.wfn`, or `.wfx`, containing orbitals, occupations and Gaussian-type-function expansion information. Geometry-only `.xyz`/`.pdb` files do not support this wavefunction-based path. Wavefunction generation is an upstream task. A formatted checkpoint avoids needing Gaussian's `formchk` to open a binary `.chk` file. Gaussian itself is not required for this analysis of a prepared supported file.

Run in a separate analysis directory: exported files go to the **process working directory**, not automatically beside the input. Preserve earlier results before exporting another system under the same fixed filenames. Keep the input geometry and electronic-structure method with the results.

## Calculate and inspect

Example PowerShell invocation; replace the executable path with the extracted installation and put the supplied `complex.fch` in the current analysis directory:

```powershell
& 'C:\Tools\Multiwfn_2026.11.3_bin_Win64\Multiwfn.exe' '.\complex.fch' -set 'C:\Tools\Multiwfn_2026.11.3_bin_Win64\settings.ini'
```

At the interactive prompts, enter these values individually:

```text
20
1
3
```

These select **Visual study of weak interaction → NCI analysis → High-quality grid**. Option 3 at this stage chooses approximately 1,728,000 grid points over the molecular box and its extension. This is a representative starting choice for a small or medium system, not a convergence guarantee. Wait for the grid calculation to finish, then use the post-processing menu:

| Option | Action |
| --- | --- |
| `-1` | Display the scatter plot: x = sign(λ₂)ρ, y = RDG. Close it with RETURN if present, otherwise right-click the graph. |
| `1` | Save the scatter graph in the current directory; the image format follows `graphformat` in `settings.ini`. Use the filename reported by the program. |
| `2` | Optionally export scatter-point data to `output.txt` in the current directory. |
| `3` | Export both `func1.cub` (sign(λ₂)ρ) and `func2.cub` (RDG) in the current directory. |

The two occurrences of `3` act in different menus. Export after calculation, retaining the paired grids from the same run. Record the box, grid dimensions/spacing and relevant settings with the output.

### Choose the spatial grid

The preset quality names refer to roughly fixed total point counts. A large molecule spreads these points over a wider box and may be poorly resolved even at “high quality.” At grid selection:

- `-10` changes the extension beyond the molecular boundary, in Bohr; then choose a grid mode. Do not copy a zero buffer unless the region of interest is fully internal.
- `4` permits explicit point counts or spacings in X/Y/Z over the whole system. Follow the displayed prompts and units.
- `7` centers a local box at the midpoint of two chosen atom indices, then asks for grid counts and extension distances in X/Y/Z (Bohr). Choose indices and a box that enclose the intended interaction region.

Keep the box large enough to avoid clipping the interesting region. For a fixed box, increase the point count to check sensitivity to spacing; coarse grids can create jagged edges and holes. Calculation time scales approximately with point count.

## Read the results

Each scatter point represents a sampled spatial grid point. RDG is dimensionless; signed density uses atomic units (electron density in electrons/Bohr³). Interpret features approaching low RDG:

| Signed density | NCI interpretation |
| --- | --- |
| Negative | Attractive interaction region; more negative features can indicate stronger attraction, such as hydrogen bonding. |
| Near zero | Low-density, weak van der Waals interaction region. |
| Positive | Steric/repulsive region, often inside rings. |

These are spatial density diagnostics, not interaction energies or an automatic bond assignment. The scatter plot alone does not locate a feature on particular atoms. Relate assignments to the geometry or the downstream mapped isosurface. If an expected feature is absent, check box coverage and grid spacing before interpreting its absence. If few points are visible, post-processing options `4` and `5` reset the axis ranges; an automatically chosen range can hide low-RDG detail.

By default, `RDG_maxrho=0.05` in `settings.ini` screens high-density regions: RDG is assigned 100 where ρ ≥ 0.05 a.u., suppressing covalent-bond regions in low-RDG displays. Setting it to 0 disables screening. Preserve this setting when comparing analyses.

### Optional downstream 3D handoff

Deliver both cubes together: render an isosurface of **func2.cub**, colored by **func1.cub**. Multiwfn does not draw the color-filled isosurface itself. Its supplied `examples\RDGfill.vmd` provides a handoff to [VMD](https://www.ks.uiuc.edu/Research/vmd/); VMD setup is separate. The manual's route places both cubes and that script in the VMD installation directory, then loads the script with File → Load State or `source RDGfill.vmd` in VMD's console. Script defaults are RDG isovalue 0.5 and signed-density color range −0.035 to 0.02 a.u.; edit the script if the scientific display requires other values. With this color scale, blue denotes attraction, green weak low-density regions, and red steric regions.

Keep wavefunction-based NCI selected for this workflow. Promolecular NCI and IGM/IGMH use different constructions; substituting one changes the meaning of the result.
