---
name: multiwfn-analyze-electron-density-bond-topology
description: Locate electron-density critical points and bond paths in Multiwfn, identify the atoms connected to selected bond critical points, and report their density and Laplacian from an existing molecular wavefunction.
---

# Electron-density bond topology with Multiwfn

## Prepare

Use **Multiwfn 2026.11.10, Windows 64-bit full binary** from the [official download page](http://sobereva.com/multiwfn/download.html). Unpack the binary archive, keeping its runtime DLL and `settings.ini` with the executable. The same page supplies the **2026.11.3 manual**; sections 4.2.1 and 3.14 document this workflow. Numerical inspection requires no VMD installation.

Provide an existing wavefunction for the geometry of interest: `.wfn`, `.wfx`, or Gaussian formatted checkpoint `.fch`/`.fchk`. A geometry-only XYZ/PDB file is insufficient for this molecular-density workflow. Record the atom indices and element identities of each target contact in this input's ordering. Generating the wavefunction is an upstream handoff.

Work in a separate results directory per structure. Exports go to the current working directory and replace files of the same name. Keep `laplfac=1.0` for the unscaled Laplacian and `iaddprefix=0` for the filenames below. For pseudopotential wavefunctions, preserve the default EDF core-density supplementation; disabling it can prevent nuclear CPs and connecting paths from being found.

## Search and identify contacts

Illustrative PowerShell invocation; replace both external paths:

```powershell
Set-Location 'D:\analysis\contact-A'
& 'C:\tools\Multiwfn_2026.11.10\Multiwfn.exe' 'D:\wavefunctions\structure.wfn' -set 'C:\tools\Multiwfn_2026.11.10\settings.ini'
```

Enter these numbers interactively, one at a time. Comments explain the inputs and are not program input:

```text
2    # Main menu: topology analysis
2    # Search from nuclear positions
3    # Search from atom-pair midpoints
0    # Print CP summary/counts and open topology display
```

A fresh session uses electron density (function 1). Do not change to the Laplacian as the topology function: the goal is to measure the Laplacian **at density CPs**. Option `-11` changes the function and clears existing topology results.

Inspect counts and the display, then click **RETURN** to close the display. For an isolated molecule, check:

```text
NCP - BCP + RCP - CCP = 1
```

The types are `(3,-3)` nuclear, `(3,-1)` bond, `(3,+1)` ring, and `(3,+3)` cage CPs. Failure of this relation signals an incomplete search; satisfaction is necessary but does not prove completeness. Check the target regions as well.

Back in the topology menu:

```text
8    # Generate paths connecting (3,-1) and (3,-3) CPs
0    # Inspect CPs, paths and connected atom identities
```

Use the printed atom-pair mapping to select each contact's BCP, then close the display with **RETURN**. CP indices are session results, not atom indices. Do not reuse a tutorial's CP number. When there are at least 500 CPs or paths, `0` omits the full printed summary; enter `00` in the topology menu to print it.
## Read and save properties

Choose `7`, then enter the BCP index just identified. Confirm `CP type: (3,-1)` and read these exact output fields:

| Field | Quantity and units |
|---|---|
| `Density of all electrons` | Total electron density rho, atomic units (`Bohr^-3`) |
| `Laplacian of electron density` | Laplacian of rho, atomic units (`Bohr^-5`), with `laplfac=1.0` |
| `Position (Bohr)` / `Position (Angstrom)` | Same CP location in the explicitly labeled units |

Repeat `7` and the next selected CP index for other contacts. To save a durable property record, select `7` then `0`: all CP properties, positions, types and available atom connections are written to **`CPprop.txt`**. Selecting `7` then `-1` writes the same file while skipping expensive electrostatic-potential evaluation. With the specified prefix setting, either choice replaces an existing `CPprop.txt`.

Report one row per selected contact: input filename, atom pair with indices/elements, CP index/type, position with units, rho and Laplacian with units, and search status/settings. Keep the density and Laplacian labels distinct. Positive Laplacian indicates local density depletion; negative indicates local concentration. These descriptors and bond paths alone do not yield an interaction energy or establish a stereochemical cause.

## Resolve incomplete searches

An unlocated BCP means it was not found under the recorded search settings; it is not by itself proof of no interaction. Missing atom mappings can also reflect missing or failed paths.

- Try topology options `4` and `5` for ring/cage CPs. If initial searches still miss CPs, use `6` then its suboption `-1` to search around every atom (default: roughly 1000 starting points per atom within 3 Bohr). This can be expensive; repeated searches use different random points. Use `-9` to leave this submenu.
- For a missing BCP, topology `-1` opens search parameters; suboption `2` changes step scale from the default `1.0`. The manual suggests trying `0.5`, then `0` to return and repeat the search. Record adjustments and recheck counts and target regions.
- For a located BCP whose path fails, topology `-2` controls path generation. A highly curved path may need a smaller step; a long path may need more points. A trajectory is discarded if it reaches the point limit before a CP.

After additional searches, regenerate paths with `8`, inspect the updated mapping, and regenerate the property export. Reidentify CPs rather than assuming their earlier indices still identify the same contacts. Use manual sections 3.14.2-3.14.3 and 4.2.1 for difficult heavy-atom or numerical cases.

## Optional topology export

From the topology menu, use `-4` → `6` to write **`CPs.pdb`**, `0` to return, then `-5` → `6` to write **`paths.pdb`**. These replace existing files in the working directory. They are visualization representations: CPs use synthetic element labels C/N/O/F for nuclear/bond/ring/cage CPs, and path atoms sample curves; they are not a modified chemical structure. See manual section 4.20.1 for external-viewer styling. Preserve the numerical property record alongside these files. Use `-10` to return to the main menu, then `q` to exit. For published work, follow the package citation instructions, including the [2012](https://doi.org/10.1002/jcc.22885) and [2024](https://doi.org/10.1063/5.0216272) Multiwfn papers.
