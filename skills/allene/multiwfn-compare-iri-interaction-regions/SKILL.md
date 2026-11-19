---
name: multiwfn-compare-iri-interaction-regions
description: Generate and compare IRI interaction-region maps from prepared molecular wavefunctions with Multiwfn, using VMD to inspect bonding, attractive contacts, and steric regions.
---

# Compare molecular interaction regions with IRI

Start from one wavefunction per structure, for example two competing transition structures. Geometry optimization, transition-state validation, and wavefunction generation are upstream preparation. IRI maps support spatial comparisons of interactions; their colors do not measure interaction energies or establish a preferred reaction pathway.

## Tools and inputs

Use **Multiwfn 2026.11.10**, with its linked **2026.11.3 manual**, from the [official download page](http://sobereva.com/multiwfn/download.html). The example below uses the Linux full binary package, which includes `settings.ini` and `examples/IRIfill.vmd`. Unpack it, give `Multiwfn` executable permission, and follow [manual section 2.1.2](http://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf) for Linux setup, including the Motif library providing `libXm.so.4`. Configure the thread count in `settings.ini` for the available physical CPU cores.

For rendering, obtain **VMD 2.0.0** through its [official registration/download page](https://www.ks.uiuc.edu/Development/Download/download.cgi?PackageName=VMD). The release provides a Linux RHEL 8+ x86_64 graphical build; use a compatible machine with an OpenGL display and follow the archive's installation instructions. Grid calculation and rendering may occur on different machines; transfer each cube pair together.

Prepare:

- `TS1.wfn` and `TS2.wfn`: molecular wavefunctions containing coordinates and the basis/orbital information needed to evaluate electron density and its derivatives. Coordinate-only XYZ/PDB files do not supply this information.
- Comparable electronic-structure preparation for both structures, plus a record of the method and settings used.
- Separate writable directories, such as `/work/iri/TS1` and `/work/iri/TS2`, each containing its corresponding input. The export filenames are fixed, so preserve each pair before another calculation.

## Calculate the grids

In Bash, replace the installation and working paths below. These environment settings follow the Linux setup guidance and apply to the current shell:

```bash
export Multiwfnpath=/path/to/Multiwfn_2026.11.10_bin_Linux
export OMP_STACKSIZE=1000M
ulimit -s unlimited
cd /work/iri/TS1
"$Multiwfnpath/Multiwfn" TS1.wfn
```

Enter the following interactively, one selection at a time, confirming the displayed menu labels:

| Selection | Meaning |
| --- | --- |
| `20` | Visual study of weak interaction |
| `4` | IRI analysis |
| `3` | High-quality grid |
| `3` | Export cube files, after calculation finishes |

The final selection belongs to the post-processing menu. The [manual's IRI example, section 4.20.4](http://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf), documents this sequence.

Keep these outputs in the current working directory:

| File | Role in the supplied plotting script |
| --- | --- |
| `func1.cub` | sign(lambda2)rho field, used to color the surface; density in atomic units |
| `func2.cub` | IRI field, used to construct the isosurface |

Repeat in `/work/iri/TS2` using `TS2.wfn`. Use matching grid choices and IRI settings. The default `uservar=0` selects the recommended IRI exponent 1.1. The default `IRI_rhocut=0.00005` a.u. suppresses surfaces in extremely dilute density regions. Retain the settings and grid information with each pair.

## Render and compare

Copy `examples/IRIfill.vmd` from the chosen Multiwfn package into each result directory. Start VMD, open **Extensions > Tk Console**, and use Tcl commands there:

```tcl
cd /work/iri/TS1
source IRIfill.vmd
```

The script reads both cubes by relative filename. Use a separate VMD session for TS2 and change the directory accordingly. The result is an interactive colored IRI surface over the molecular structure.

The supplied script uses:

| Setting | Default |
| --- | --- |
| IRI isovalue | `1.0` |
| Color field limits | `-0.04` to `+0.02` a.u. |
| Color scale | Blue-green-red (`BGR`) |

Keep these settings consistent across structures. If a different isovalue is needed, adjust **Graphics > Representations** or the value after `mol representation Isosurface` in the local script. Preserve the chosen script with the cubes.

## Read the result

With this color scale, blue/cyan indicates attraction, green indicates weak van der Waals regions near zero signed density, and red indicates repulsive/steric regions. Chemical bonding regions can also appear blue at much larger density: distinguish them by location rather than calling every blue region a noncovalent contact. See the legend in manual section 4.20.4, page 868.

Compare corresponding contacts using comparable molecular views and identical display settings. Report their locations and qualitative differences; energetic or selectivity claims require additional calculations.

If VMD cannot read a cube, check its working directory and the intact cube pair before interpreting the plot. A missing surface at a contact does not establish absence of an interaction: inspect grid coverage, the selected isovalue, and density cutoff. Keep both cubes as the reusable numerical outputs even when only the interactive view is needed.

For publication, use the package's `How to cite Multiwfn.pdf` guidance and cite the [IRI method](https://doi.org/10.1002/cmtd.202100007).
