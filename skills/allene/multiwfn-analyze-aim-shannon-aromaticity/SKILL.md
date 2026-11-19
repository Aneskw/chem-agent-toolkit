---
name: multiwfn-analyze-aim-shannon-aromaticity
description: Use Multiwfn to locate electron-density critical points, map bond paths to ring bonds, inspect BCP properties, and calculate a selected ring's Shannon aromaticity index from a supplied molecular wavefunction.
---

# Electron-density topology and ring Shannon aromaticity

## Prepare

Use **Multiwfn 2026.11.10, Windows 64-bit full binary** from the [official download page](http://sobereva.com/multiwfn/download.html) ([versioned archive](http://sobereva.com/multiwfn/misc/Multiwfn_2026.11.10_bin_Win64.7z)). Extract the whole archive, keeping its runtime DLL beside Multiwfn.exe. The official page supplies the [2026.11.3 manual](http://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf); sections 2.1–2.5 cover setup and input, 3.14 covers topology, and 4.2.1 illustrates this analysis. This workflow uses the graphical build to inspect connectivity.

Required external inputs:

| Input | Requirement |
|---|---|
| Wavefunction | Optimized molecule in .fch/.fchk, .wfn or .wfx, containing occupied orbitals and basis/Gaussian-function information. An XYZ geometry alone is insufficient. Wavefunction generation is an upstream handoff. |
| Ring | Atom identities/indices in cyclic order, including the closing bond; use the numbering in the loaded wavefunction. |
| Calculation record | Method, basis, charge/spin, geometry and ECP treatment, needed when comparing results. |

A Gaussian binary .chk must first be converted with Gaussian's formchk utility; alternatively configure `formchkpath` in Multiwfn's settings.ini. Supplying an already formatted file avoids this dependency.

For ECP atoms, including Ru, retain the density reconstruction defaults: `readEDF=1` reads an available .wfx EDF field; `isupplyEDF=2` supplies EDFs from the built-in library when needed. EDFs restore core-density contributions to density topology, but do not correct wavefunction-dependent functions such as kinetic energy density. Do not treat the resulting energy-density properties as automatically equivalent to an all-electron calculation. Small-core ECPs are preferable to large-core ones for CP accuracy. Missing core density can prevent nuclear CPs and their connecting paths from being found normally.

## Launch and identify the ring BCPs

Example PowerShell invocation; substitute your extracted installation and supplied wavefunction paths. Use a separate working directory per analysis because exports use fixed filenames.

```powershell
Set-Location 'D:\analysis\ring-case'
& 'C:\Tools\Multiwfn_2026.11.10_bin_Win64\Multiwfn.exe' '.\molecule.fchk' -set 'C:\Tools\Multiwfn_2026.11.10_bin_Win64\settings.ini'
```

The working directory must already exist. Explicit `-set` selects the intended configuration; without it, Multiwfn searches the current directory and then `Multiwfnpath` for settings.ini before using defaults.

Enter these menu selections interactively:

| Selection | Action |
|---|---|
| Main menu `2` | Enter topology analysis. Keep the default real-space function, electron density. |
| Topology `2`, then `3` | Search from nuclear positions, then atomic-pair midpoints. |
| `0` | Print CP positions/types/counts and visualize. Click RETURN to close the plot. |
| `8`, then `0` | Generate bond paths, then inspect the summary and plot. The summary now identifies the two atoms linked to each BCP. Enable CP labels in the plot if needed. |

If the menu separates printing for a large system, use `00` to print the summary. Classifications are NCP `(3,-3)`, BCP `(3,-1)`, ring CP `(3,+1)` and cage CP `(3,+3)`.

Map **each ring edge to its BCP using the connected atom pair**, including the last-to-first edge. Keep this mapping with the results. CP indices are session-specific and are distinct from atom indices. In a metallacycle, include the ring's C–metal edges; exclude unrelated coordination contacts to a second metal. Do not choose BCPs solely by spatial proximity or reuse another calculation's indices.

## Inspect properties, calculate SA, and save

1. In topology option `7`, enter a mapped BCP index. Record `Density of all electrons`, `Laplacian of electron density`, `Lagrangian kinetic energy G(r)`, `Potential energy density V(r)` and `Energy density` as needed. These real-space properties use atomic units: density is electrons/Bohr³ and energy density is Hartree/Bohr³. Repeat for the ring BCPs. To save properties of **all** CPs directly, choose `7` and enter `0`; this writes CPprop.txt. Entering `-1` instead also writes properties but skips the expensive electrostatic-potential calculation.
2. Select `20`. At `Input the indices of the CPs in the ring`, enter the complete comma-separated BCP list. The count is inferred; do not enter a separate count. For example, the manual's bundled `examples\2-pyridoxine_2-aminopyridine.wfn` tutorial uses `44,42,32,29,31,40` for its aminopyridine ring. For your supplied molecule, replace that entire list with the indices established by your connectivity mapping. Multiwfn prints each selected CP's density and local entropy, total density, total entropy, maximum entropy, and `Shannon aromaticity index`. Copy this output into a result text file; SA is not automatically included in the topology-coordinate exports. Enter `q` to leave the repeated SA prompt.
3. From the topology menu, export with the following selections. In each export submenu, `0` returns to the topology menu.

| Selections | File in working directory | Contents |
|---|---|---|
| `-4`, `4` | CPs.txt | CP count, then CP index, XYZ in Bohr, and integer type: 1=NCP, 2=BCP, 3=ring CP, 4=cage CP. |
| `-5`, `4` | paths.txt | Path count and individual path point coordinates in Bohr. |
| `-5`, `9` (optional) | bpcp.txt | Combined detailed CP and bond-path information for post-processing. |

Exports replace existing files of the same name. Preserve CPprop.txt, the atom-pair-to-BCP mapping, the selected ring list and captured SA output together with CPs.txt and paths.txt. To exit, use `-10` from topology, then `q` at the main menu.

## Interpret and resolve incomplete searches

For an isolated molecule, the printed Poincaré–Hopf check is `NCP − BCP + ring CP − cage CP = 1`. Failure indicates missing CPs. Passing is necessary for a complete topology but does not prove every CP was found.

If an expected ring BCP is missing, do not calculate SA from a shortened ring. Try targeted starting points with topology option `1`, additional searches with `4`/`5` for ring/cage CPs, or option `6` → `-1` for the more expensive atom-centered sphere search. For difficult BCP searches, option `-1` permits reducing the search stepsize scale from its default 1.0 to 0.5. If a located BCP lacks a connecting path, inspect path settings in `-2`: highly curved paths can require smaller steps and long paths more points. After changing searches or paths, recheck connectivity and rebuild the index mapping. See manual sections 3.14.2–3.14.3 and 4.2.1 for further adjustments. Report search settings and an unresolved absence explicitly; a failed search alone does not establish absence of bonding.

SA is dimensionless: `p_i = rho_i / sum(rho_j)` and `SA = ln(N) + sum(p_i ln(p_i))`. It measures variation among the selected ring BCP densities; smaller SA indicates greater equalization and, within the method's scope, stronger aromaticity. Compare rings using consistent computational settings and ring definitions. The conventional-arene boundary around 0.003–0.005 is not a universal metallabenzene classifier: the [ruthenabenzene study](https://doi.org/10.1039/d2dt01071b), pp. 8392–8393, explicitly discusses aromatic metallabenzenes above that range. Treat SA and BCP properties as computed descriptors, not standalone proof of aromaticity or bond strength.
