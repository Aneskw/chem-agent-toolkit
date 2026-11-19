---
name: multiwfn-project-molecular-surface-distances
description: Generate molecular surface-distance projection images and numeric maps with Multiwfn from oriented molecular structures to examine steric accessibility and compare exposed or buried regions.
---

# Molecular surface-distance projection with Multiwfn

Map the first surface encountered along decreasing Z onto the XY plane. The result is signed surface depth relative to a chosen starting Z layer; it supports geometric comparisons, not reaction-barrier or stereoselectivity predictions.

## Prepare

Use **Multiwfn 2026.11.10, Windows 64-bit GUI distribution** from the [official download page](http://sobereva.com/multiwfn/download.html) ([versioned archive](http://sobereva.com/multiwfn/misc/Multiwfn_2026.11.10_bin_Win64.7z)). Extract the complete package, retaining its DLL, settings.ini and examples. The [2026.11.3 manual](http://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf), sections 3.300.8 and 4.300.8, describes this analysis. The instructions below use the release source's module-specific plotting menu.

Supply a prepared, deliberately oriented structure, such as XYZ or Gaussian GJF; PDB and MOL2 are also supported for this analysis. Put the desired viewing direction along Z, looking toward decreasing Z. Rotate and save coordinates in a molecular editor before loading if needed. Geometry-only input is sufficient for promolecular-density and atomic-sphere surfaces. Actual electron-density surfaces additionally require a supported wavefunction file with Gaussian-type basis information.

Use a separate writable results directory per structure. Record orientation, coordinate frame, surface definition, grid and scan bounds for comparisons. Match those choices and the color scale across related structures; independently chosen default Z references are not a common physical reference.

## Launch and calculate

From the results directory, adapt these PowerShell paths to the extracted distribution and your external input:

```powershell
& 'C:\Tools\Multiwfn_2026.11.10\Multiwfn.exe' 'D:\structures\catalyst-oriented.xyz' -set 'C:\Tools\Multiwfn_2026.11.10\settings.ini'
```

The executable's directory and current results directory can differ. The explicit `-set` selects the distribution's settings file. For a supplied demonstration input, replace the XYZ path with the distribution's `examples\excit\Ru(bpy3)2+.gjf`; this structure is already oriented to examine ligand burial of Ru.

Enter `300`, then `8`. Inspect and, where needed, change these settings **before** calculating:

| Setup option | Meaning and material defaults |
| --- | --- |
| 1 | Surface definition: 1 = promolecular density; 2 = wavefunction electron density, offered when basis information is loaded; 3 = scaled Bondi atomic vdW spheres. Density choices prompt for an isovalue in a.u.; spheres prompt for a dimensionless radius scale. Default is promolecular density at 0.05 a.u. |
| 2, 3 | X and Y lower/upper limits, entered in Å, e.g. `-8,8`. Automatic bounds cover the structure. |
| 4, 5 | Numbers of X and Y grid points; default 300 each. More points increase resolution and cost. |
| 6 | Positive Z scan step in Å; default 0.05. Smaller steps improve depth resolution at greater cost. |
| 7, 8 | Starting and ending Z in Å. Scan proceeds downward: start must exceed end. Normally defaults are maximum and minimum atomic Z; for an almost planar structure the start is raised by 2 Å. |

The default 0.05 a.u. surface emphasizes the molecular outline. For a more extended steric envelope, the manual suggests 0.001 or 0.002 a.u.; these are choices to document, not universal cutoffs. Atomic spheres are faster but less smooth.

For an explicit version of the manual's default-surface example, enter these values one per line after reaching the setup menu:

```text
1
1
0.05
```

Then inspect options 2–8. Set Z start above the relevant surface and Z end sufficiently below the region of interest. Atomic extrema need not enclose a density isosurface: starting inside the surface clips the depth to zero. After checking bounds, enter `0` to calculate. In the resulting **plotting menu**, enter `0` to display the map. Close the graph to return to that menu.

## Save and inspect

In this module's plotting menu:

- `1` saves a graphical file in the current directory with a `dislin` prefix. Default format is PNG; `graphformat` and `graph2Dsize` in settings.ini control format and size.
- `-2` exports `distmap.txt` in the current directory, replacing any existing file of that name. It writes three numeric columns without a header, with X index outermost and Y index varying fastest.
- `8` adjusts color-scale limits; `10` adjusts contours. `-4` multiplies the underlying data, so export before using it unless scaling is intentional.
- `-1` returns to the calculation setup for changes and recalculation.

Preserve the image, numeric file and recorded settings before another run. The numeric third column is signed depth in Å: `Zhit - Zstart`. More negative values mean the first surface lies farther below the reference layer. A zero can mean the scan began inside the surface. A value of `Zend - Zstart` can mean **no surface was encountered** before the scan ended; it is not proof of a deeply buried surface. Recheck orientation, density threshold and scan bounds when a map is flat, clipped or saturated.

**Coordinate handling in this release:** the exporter forms its first two columns from stored plane-origin variables, while this module passes X/Y bounds separately to plotting. Check exported endpoints against the recorded bounds before overlaying atoms or comparing coordinates. Recover the actual sampling coordinates from row order if they differ: for zero-based row `r`, let `i = floor(r / ny)` and `j = r mod ny`; then
`x = xmin + i*(xmax-xmin)/(nx-1)` and
`y = ymin + j*(ymax-ymin)/(ny-1)`, using bounds in Å. Keep the third-column values unchanged. There should be `nx*ny` rows.

Interpret exposed and buried regions together with atom positions and the chosen viewing direction. A projection records only the first encountered surface and cannot resolve hidden surfaces behind it.
