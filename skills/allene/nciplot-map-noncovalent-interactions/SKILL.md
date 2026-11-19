---
name: nciplot-map-noncovalent-interactions
description: Use NCIPLOT to generate reduced-density-gradient data and colored noncovalent-interaction surfaces from supplied WFN/WFX wavefunctions or molecular XYZ geometries.
---

# Map noncovalent contacts with NCIPLOT

Generate spatial maps of attractive, weak and repulsive contact regions. Start with a prepared structure or wavefunction; geometry optimization and wavefunction generation are upstream work. This workflow produces interaction maps, not distortion energies or quantitative interaction energies.

## Environment

Use NCIPLOT 4.4 at commit `e7a113c35ffdedb4d61479365642643f49580e29` from the [official author repository](https://github.com/juliacontrerasgarcia/NCIPLOT-4.4/tree/e7a113c35ffdedb4d61479365642643f49580e29). Download that commit's source archive or check out that exact commit. Use its own `src_4.4/Makefile.inc` and retain its `dat/` directory.

For the Linux shell path below, provide GNU gfortran with OpenMP and make; official entrypoints are [GNU Fortran](https://gcc.gnu.org/fortran/) and [GNU Make](https://www.gnu.org/software/make/). Set `NCIPLOT_HOME` to the absolute extracted repository root. Review `src_4.4/Makefile.inc` for your compiler, then build:

```bash
export NCIPLOT_HOME=/absolute/path/to/NCIPLOT-4.4
cd "$NCIPLOT_HOME/src_4.4"
make
export PATH="$NCIPLOT_HOME/src_4.4:$PATH"
export OMP_NUM_THREADS=4
```

Keep `NCIPLOT_HOME` set when running: it locates atomic-density resources. Four threads is an example resource choice. This mapping path does not enable the separate clustering or energy-estimation modules.

For interactive display, obtain the Linux release VMD 2.0.0 from the [official VMD download page](https://www.ks.uiuc.edu/Development/Download/download.cgi?PackageName=VMD), which requires registration/login. Select the release build dated March 25, 2026 (RHEL 8+ x86_64), and follow its installation instructions. The newer 2.0.1 entry is an alpha. Provide a graphical display and make the `vmd` launcher available.

## Prepare the input

Use a separate working directory containing the supplied `complex.wfn` (AIMPAC WFN format); WFX is also accepted. Keep the original coordinates unchanged. Relative filenames are resolved from the process working directory.

For a geometry-only analysis, substitute a supplied standard `.xyz` file: NCIPLOT then uses the promolecular approximation rather than the calculated wavefunction density. Do not mix XYZ with wavefunction inputs. For multiple files, the first input line is their count, followed by one filename per line. All wavefunction inputs in a run must use the same format: all WFN or all WFX. Never mix WFN and WFX: this pinned implementation issues a warning and then selects promolecular density instead of calculated wavefunction density.

Create `complex.inp` with:

```text
1
complex.wfn
ONAME MAP
FINE
OUTPUT 3
RDG_CUTOFF 1.0 0.5
DENS_CUTOFF 0.05
```

| Setting | Meaning in this example |
| --- | --- |
| `ONAME MAP` | Output prefix; this pinned code preserves its case. |
| `FINE` | 0.05 angstrom final spacing; multilevel factors 12, 8, 4, 1. |
| `OUTPUT 3` | Write scatter data, both cubes and a VMD script. |
| `RDG_CUTOFF 1.0 0.5` | RDG cutoff for reported points and the displayed RDG isovalue, respectively. |
| `DENS_CUTOFF 0.05` | Absolute signed-density cutoff for reported points, in atomic units. |

These are explicit example settings. All contacts remain eligible: no intermolecular-only filtering is requested. On a complete catalyst complex, do not add `INTERMOLECULAR` merely because the desired contacts connect ligand and substrate; fragment definitions and filtering change what survives.
## Run and inspect

From the directory containing `complex.inp` and `complex.wfn`:

```bash
nciplot complex.inp > complex.out
vmd -e MAP.vmd
```

Inspect `complex.out` before opening the map: check input filenames, wavefunction versus promolecular mode, grid settings, reported errors and the final `End` timestamp. A missing input file is a fatal error. Use a fresh working directory or output prefix for each calculation to avoid collisions with previous results.

| Output | Access and meaning |
| --- | --- |
| `complex.out` | Calculation log, configuration and completion information. |
| `MAP.dat` | Two columns: signed density `sign(lambda2)*rho` in atomic units, then dimensionless RDG; only points passing the reporting filters are written. |
| `MAP-grad.cube` | Spatial RDG field used for the isosurface. |
| `MAP-dens.cube` | Signed-density field for coloring, in atomic units in this pinned implementation. Do not multiply or divide its values by 100. |
| `MAP.vmd` | Loads both cubes and builds atom and interaction-surface representations. |

Keep the cubes beside the script. The generated script uses the density cube as volume 0 for color and the RDG cube as volume 1 for the surface. Its color range is fixed at -0.04 to +0.04 atomic units; `DENS_CUTOFF` controls point filtering and does not change that color range. If the script cannot find its files, start VMD in the output directory. The [official VMD loading instructions](https://www.ks.uiuc.edu/Research/vmd/current/ug/node23.html) also describe File > Load State and `play filename`.

## Interpret the map

The generated blue-green-red scale associates negative signed density with attractive contacts, values near zero with weak van der Waals contacts, and positive values with repulsive regions. Compare the locations of these surfaces with the molecular geometry. A color or patch alone does not establish a bond, a stabilization energy or the cause of an observed selectivity.

An empty scatter file or absent surface can reflect the chosen reporting cutoffs, display isovalue or spatial box; check these and the log before concluding that interactions are absent. For comparisons across structures, keep the density method, grid and display settings consistent. Preserve the cubes, input and log with any saved visualization so that the map remains interpretable.
