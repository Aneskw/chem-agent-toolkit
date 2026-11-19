---
name: multiwfn-map-pi-electron-localization
description: Generate and export LOL-pi plane maps in Multiwfn from an orbital-containing wavefunction and a justified pi-orbital selection; use the documented automatic selection for planar, coordinate-aligned systems.
---

# Map π-electron delocalization with Multiwfn

## Prepare the program and wavefunction

Use **Multiwfn 2026.11.10**, graphical Windows 64-bit edition. Obtain and unpack [the official binary archive](https://sobereva.com/multiwfn/misc/Multiwfn_2026.11.10_bin_Win64.7z), retaining its DLL and settings files. The [official download page](https://sobereva.com/multiwfn/download.html) supplies the license and other platforms; the Linux noGUI edition cannot perform this graphical workflow. Consult the [official manual](https://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf), §§2.1–2.3 for platform setup and §4.4.9 for the LOL-π tutorial.

Required inputs and choices:

| Item | Requirement |
|---|---|
| Wavefunction | A prepared orbital-containing file, such as Gaussian formatted checkpoint `.fch`, with coefficients and occupations. Geometry alone or a precomputed density grid is insufficient for orbital selection. Wavefunction calculation and conversion are external preparation. |
| π selection | For automatic selection below, delocalized orbitals and an exactly planar molecule parallel to XY, XZ or YZ. Inspect the detected plane, orbital indices, occupations and total π-electron count before applying the selection. |
| Plot geometry | Plane orientation and absolute normal coordinate, in Bohr by default. Plot above/below the molecular plane, avoiding the π nodal plane. |
| Settings | Use the supplied settings with `ELFLOL_type=0` for standard LOL. Use a writable working folder for exported figures. |

For nonplanar or substituted systems with σ–π mixing, the simple automatic selection is not a general solution. Obtain a separately justified selection and occupation preparation first; the resulting analysis wavefunction must preserve the selected π occupations and set other occupations to zero. Then skip detection and occupation changes: start at `4` (plane plotting) in the sequence below, adapting the plane to your geometry. Manual §3.100.22 describes separate localized-orbital methods and their restrictions; it does not make the planar MO detector valid for arbitrary geometry. Do not rotate only the coordinates in a finished wavefunction file: alignment must remain consistent with its orbital coefficients.

## Select π orbitals and plot

Representative input: an externally prepared `molecule.fch` whose molecular plane is YZ at **X=0**. Paths below are example locations to replace. Start from your writable output folder, using the actual executable and settings paths:

```powershell
Set-Location C:\work\lol-pi
& 'C:\tools\Multiwfn\Multiwfn.exe' 'C:\inputs\molecule.fch' -set 'C:\tools\Multiwfn\settings.ini'
```

Enter `100`, `22`, `0` in sequence: other functions → detect π orbitals → delocalized orbitals. **Pause to review the detected plane and orbital list.** A warning that the plane cannot be detected, an implausible selection or `No pi orbital was found!` requires revisiting the input/selection; do not force a plane merely to proceed.

If the selection is defensible, enter:

```text
2
0
4
10
1
200,200
3
1.2
```

These inputs retain the π occupations while zeroing all others; return to the main menu; choose plane plotting → LOL → color-filled map; use a 200×200 grid; choose YZ; and plot at **X=1.2 Bohr**. Pressing Enter at the grid prompt also selects 200×200 for this map. The occupation change modifies the wavefunction in memory and updates its electron count/density matrix. Reload the original file in a fresh session before performing analyses requiring the full wavefunction.

The 1.2-Bohr offset follows the manual's illustrative plotting choice, not a universal optimum. For a molecule at X=X₀, enter X₀ plus the desired offset. Plot menu choices `1`, `2`, `3` mean XY at specified Z, XZ at specified Y, YZ at specified X, respectively. These plotting indices differ from any plane-selection prompts inside the orbital detector. Increase the grid for smoother maps when needed; region extension can be changed through `0` at the plane-definition prompt (Bohr).

## Inspect and export

Close the plot using its Return control (or right-click if no Return control is shown) to reach the plotting controls. For the example, `1` followed by `0,0.66` sets the color limits. This is a display choice, not a scientific threshold. Use `-1` to replot. Keep color limits and sampling geometry consistent when comparing maps.

If atom labels are needed, enable them with option `4` when its prompt says Enable, and choose a label color. Set option `17` to a distance greater than the plane offset: `2` Bohr followed by `y` works for this example. Option `8` enables bonds and asks for their color. Follow the displayed toggle status rather than blindly repeating a toggle.

After inspecting the map, enter:

```text
-3
10
7
0
0
```

This opens other plotting settings, selects export format → PDF, returns to plotting controls, and saves the figure **in the current working folder**. Check the console's save message and open the exported PDF (the default name has a `dislin` prefix). Preserve it under a descriptive name before another export. Record the input file, selected orbital indices/occupations, plotting plane and offset, grid and color limits alongside the figure.

High LOL-π regions identify favorable π-electron delocalization paths. The map is an orbital-derived localization descriptor; it does not measure induced current density or by itself establish aromaticity. A map computed without zeroing the non-π occupations is total LOL, not LOL-π. Missing labels can reflect their distance cutoff; a blank or unexpected map calls for checking selection, plane position, region and color limits before drawing a chemical conclusion.

For scientific reporting, follow the package's `How to cite Multiwfn.pdf` and cite the π-analysis method [Lu and Chen, Theoretical Chemistry Accounts 139, 25 (2020)](https://doi.org/10.1007/s00214-019-2541-z), as requested by the detector and manual.
