---
name: multiwfn-visualize-wavefunction-nci
description: Generate NCI scatter plots and sign(lambda2)rho-colored RDG isosurfaces from an existing molecular wavefunction using Multiwfn and VMD; use to locate and compare noncovalent interaction regions.
---

# Wavefunction NCI maps with Multiwfn and VMD

## Prepare the tools and input

Use **Multiwfn 2026.11.10, full Linux build**, with **VMD 2.0.0 release, Linux x86_64 RHEL8+ build**, in a graphical Linux session. Obtain Multiwfn's versioned binary package, examples and manual from the [official download page](http://sobereva.com/multiwfn/download.html). Obtain VMD from its [official download page](https://www.ks.uiuc.edu/Development/Download/download.cgi?PackageName=VMD); archive access requires registration/login. Follow the archive's installation instructions so `vmd` resolves to this release.

For Multiwfn setup, follow section 2.1.2 of the [official manual](http://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf), which the current download page supplies. The full build requires Motif (`libXm.so.4`) and working graphics libraries/display. Unpack the binary, grant its `Multiwfn` executable permission, set `Multiwfnpath` to that unpacked directory, and put it on `PATH`. Use the documented shell stack settings:

```bash
export OMP_STACKSIZE=1000M
ulimit -s unlimited
```

Keep the distributed `settings.ini` and `examples/RDGfill.vmd`. Set `nthreads` in `settings.ini` for the available physical cores. The noGUI build lacks the scatter plotting used here. Follow the bundled license and citation instructions when reporting results.

Supply an existing, compatible **WFN, WFX, FCH/FCHK, MWFN or Molden wavefunction** containing Gaussian-type function/orbital information. Geometry-only XYZ/PDB files do not provide the density needed for this workflow. Electronic-structure calculation and any export/conversion to these formats are external preparation; use a formatted checkpoint rather than assuming a binary CHK is directly readable.

## Calculate and save the NCI data

Use a separate working directory per structure: exports use fixed names and replace existing files. The following assumes `Multiwfn` is on `PATH`, `Multiwfnpath` points to its unpacked package, and `/data/complex.fch` is your supplied wavefunction. Substitute your own paths.

```bash
mkdir -p nci-complex
cd nci-complex
Multiwfn /data/complex.fch -set "$Multiwfnpath/settings.ini"
```

Enter these choices interactively, waiting for calculation to finish before post-processing:

| Stage | Choice | Meaning |
|---|---|---|
| Main menu | `20` | Visual study of weak interaction |
| Analysis menu | `1` | Wavefunction-based NCI analysis |
| Grid menu | `3` | High-quality grid covering the whole molecule; about 1,728,000 points for a nonperiodic system |
| Post-processing | `-1` | Display scatter plot; close it to return |
| Post-processing | `1` | Save scatter plot image (PNG by default) in the working directory; retain the generated image |
| Post-processing | `2` | Export scatter values to `output.txt` |
| Post-processing | `3` | Export the paired `func1.cub` and `func2.cub` |

The scatter plot has **sign(lambda2)rho in atomic units on X** and **dimensionless RDG on Y**. `output.txt` contains X, Y, Z coordinates in Angstrom followed by function 1 (sign(lambda2)rho) and function 2 (RDG). The default NCI scatter display spans X = -0.05 to 0.05 and Y = 0 to 2 with the default screening setting. Post-processing options `4` and `5` change display axis ranges if needed.

| File | Role |
|---|---|
| `func1.cub` | sign(lambda2)rho color field, atomic units |
| `func2.cub` | RDG isosurface field, dimensionless |
| `RDGfill.vmd` | Distributed VMD plotting state/script; reads both cube files |

Keep the cubes from the same calculation together, without swapping names. Exit Multiwfn, copy the matching plotting script into this working directory, and launch VMD there:

```bash
cp "$Multiwfnpath/examples/RDGfill.vmd" .
vmd
```

In VMD's console run:

```tcl
source RDGfill.vmd
```

Alternatively use **File → Load state** and select `RDGfill.vmd`. Ensure VMD's working directory contains the script and both cubes; if necessary use Tcl `cd /absolute/path/to/nci-complex` before sourcing. The colored RDG surface appears in the OpenGL window. Preserve the cube pair and script alongside the scatter data/image as the reusable result.

## Inspect and compare

The distributed script uses **RDG isovalue 0.5** and **sign(lambda2)rho color range -0.035 to +0.02 a.u.** These are tool defaults, adjustable in a local copy of `RDGfill.vmd`. Negative/blue regions indicate attractive interactions; near-zero/green regions indicate low-density, weak van der Waals regions; positive/red regions indicate steric effects. Low-RDG spikes in the scatter plot help locate these regimes. Identify interactions using their spatial context as well as color; these fields do not directly measure interaction energies.

The default `RDG_maxrho=0.05` in `settings.ini` assigns RDG = 100 where density is at least 0.05 a.u., screening high-density regions. Setting it to zero disables screening and changes what appears. Keep screening, grid spacing/extent, isovalue and color scale comparable across structures, and record the settings actually used.

Jagged edges or holes suggest a coarse grid. At fixed box size, increase the number of points; for large systems use grid option `4` to specify spacing rather than trusting the high-quality preset. Truncated surfaces require a larger box; the grid menu's `-10` adjusts extension in Bohr. Enclose the region of interest without making the box unnecessarily large. Recalculate and replace both cubes together after changing the grid.

If Multiwfn reports that wavefunction information is unavailable, obtain a wavefunction-containing input; selecting promolecular NCI changes the method. If VMD cannot load the cubes, check filenames and working directory first. A blank or weak surface can reflect grid extent, screening or isovalue and is not alone proof of absent interactions. The [VMD cube plugin](https://www.ks.uiuc.edu/Research/vmd/plugins/molfile/cubeplugin.html) may rotate cube coordinates/grid vectors on loading, so verify alignment before adding a separately loaded geometry.
