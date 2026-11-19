---
name: multiwfn-visualize-interfragment-igmh
description: Generate IGMH grids from a molecular wavefunction with Multiwfn and visualize interfragment contacts in VMD using supplied fragment atom lists.
---

# Visualize interfragment contacts with IGMH

## Prepare the tools and inputs

Use Multiwfn **2026.11.10** and VMD **2.0.0** on Linux x86_64 with a graphical desktop. Obtain the full Linux Multiwfn binary package from the [official download page](https://sobereva.com/multiwfn/download.html); retain its `settings.ini` and `examples` directory. Follow §2.1.2 of the [2026.11.3 manual](https://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf) for executable permissions, environment and the full build's Motif/libXm.so.4 prerequisite. Set `Multiwfnpath` to the unpacked directory and put its executable on PATH. The manual specifies `OMP_STACKSIZE=1000M` and `ulimit -s unlimited` for Linux.

For grid export without Multiwfn's own graphical windows, the dated Linux **noGUI** package also supports this menu path. Retain its `settings.ini` and `examples/IGM_inter.vmd`; the subsequent VMD display still requires a graphical session.

Obtain the **release** VMD 2.0.0 Linux build (RHEL 8+ platform listing) from the [official VMD downloads](https://www.ks.uiuc.edu/Development/Download/download.cgi?PackageName=VMD), then follow its supplied installation instructions. Downloads require registration/login. Use the release entry rather than the 2.0.1 alpha.

Required preparation:

| Input | Contract |
| --- | --- |
| Wavefunction | Computed molecular `.wfn`, `.fch`, `.mwfn` or `.molden` containing wavefunction information; coordinates alone are insufficient for IGMH. |
| Fragments | Chemically justified atom lists in the loaded wavefunction's **1-based atom numbering**, such as `1-12` and `13-25`. Preserve that ordering when preparing the file. |
| Plotting resources | `examples/IGM_inter.vmd` and, for a matching legend, `examples/IGMH_colorbar.png` from Multiwfn. |

Wavefunction calculation and chemical fragment selection are supplied inputs. Use a separate writable directory for each case because exported cubes have fixed names.

## Generate the grids

In a shell, change to the case directory and invoke Multiwfn with the supplied wavefunction:

```bash
cd /work/igmh-case
Multiwfn /absolute/path/complex.wfn -set "$Multiwfnpath/settings.ini"
```

Enter the following responses interactively, one per prompt. The atom lists below are the manual's 25-atom dimer example; **replace both lists with the supplied fragments for complex.wfn**. To use those lists unchanged, load the distributed `examples/2-pyridoxine_2-aminopyridine.wfn` instead.

```text
20
11
2
1-12
13-25
2
3
```

| Response | Meaning |
| --- | --- |
| `20 → 11` | Visual study of weak interactions → IGMH |
| First `2`, then the two lists | Define two fragments |
| Next `2` | Medium-quality grid, an initial visualization choice |
| `3` after grid calculation | Export cube files to the current directory |

Keep `IGMvdwscl=0` in `settings.ini` for this normal path; it disables overlap-based grid skipping. A positive value enables an optimization that can truncate surfaces if too small and only supports interfragment surfaces.

Retain `dg_inter.cub` (δg_inter grid) and `sl2r.cub` (sign(λ₂)ρ grid) **from the same calculation**. Record the input, fragment lists, grid parameters and settings beside the cubes. Recheck atom numbering and prompts if file loading fails or either expected cube is absent.

## Display and compare the contacts

Copy `examples/IGM_inter.vmd` into the case directory with the two cubes. Start VMD and, in its console, run:

```tcl
cd /work/igmh-case
source IGM_inter.vmd
```

This displays a δg_inter isosurface coloured by sign(λ₂)ρ. The documented defaults are **isovalue 0.01** and **colour limits −0.05 to +0.05**, in atomic units. Under **Graphics → Representations**, select the isosurface representation to change **Isovalue**. Its **Trajectory** tab exposes the colour-scale limits. The manual illustrates 0.015 with limits −0.045 to +0.045 for a smaller, more vividly coloured surface; these are optional display choices, not acceptance thresholds.

Read the surface with the matching IGMH colour bar: blue indicates attractive regions, green weak low-density contacts, and red steric/repulsive regions. Colours and surface extent characterize the computed density; they are not interaction energies. No visible surface at a chosen isovalue does not establish absence of interaction: check fragment assignments, grid coverage/resolution and display settings first.

For comparisons, use corresponding fragment definitions, consistent grid coverage/resolution, the same isovalue and identical colour limits. Inspect grid refinement if apparent contacts depend on resolution. Preserve the cube pair and report plotting settings with any exported image; a screenshot alone loses the underlying fields.

For method interpretation and citation, see the [IGMH paper](https://doi.org/10.1002/jcc.26812), its [implementation erratum](https://doi.org/10.26434/chemrxiv-2022-g1m34), and manual §§3.23.6 and 4.20.11. Follow the distribution's `How to cite Multiwfn.pdf` when reporting results.
