---
name: multiwfn-compare-metal-ligand-bond-orders
description: Calculate and compare Mayer and fuzzy bond orders with Multiwfn when prepared molecular wavefunctions are available and weak metal-ligand contacts or changes in coordination need analysis.
---

# Compare metal–ligand bonding with Multiwfn

Use the same atom-pair mapping across structures to compare two complementary bond-order definitions. Wavefunction calculations and geometry optimization are upstream inputs to this workflow.

## Setup and inputs

Use **Multiwfn 2026.11.10, Windows 64-bit**. Download `Multiwfn_2026.11.10_bin_Win64.7z` from the [official download page](http://sobereva.com/multiwfn/download.html) and extract the complete package. The executable is `Multiwfn.exe`; retain its accompanying `settings.ini`. These analyses operate on supplied wavefunctions without invoking Gaussian.

For interface details, the [official manual](http://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf), §§2.1–2.5 and 4.9.1, covers setup, input formats and the examples used here.

| Input | Required preparation |
|---|---|
| One wavefunction per structure | Prefer `.fch`/`.fchk`; `.mwfn`, `.molden` and `.gms` also carry the basis information required by Mayer analysis. Files must contain the calculated orbitals, occupations and geometry, not just coordinates. |
| Atom-pair mapping | Identify the metal and each ligand atom by its index in each loaded structure. Indices may change between files; match chemical identities before comparing. |
| Calculation record | Retain each structure's electronic method, basis/ECP, charge and spin treatment. Compare like computational treatments, and identify any differences. |

`.xyz` and other coordinate-only files cannot supply the required electronic information. `.wfn`/`.wfx` can support fuzzy analysis but lack the basis-function information needed for Mayer analysis. If diffuse functions are present, do not interpret the Mayer values as reliable; use fuzzy analysis for that input and label the Mayer limitation rather than silently changing the upstream wavefunction.

Create a separate working directory for each structure and copy the distributed `settings.ini` into each directory before its first run. Multiwfn reads settings from the working directory; merely keeping the file beside the executable does not ensure it is found. Edit each local copy for this workflow, including `nthreads` if CPU allocation needs adjustment, and restart Multiwfn after changes. Preserve edited copies on subsequent runs. The following example assumes externally supplied `C:\bond-analysis\A\complex.fch` and `C:\bond-analysis\B\complex.fch`. Replace the executable path with the actual extracted location.

## Calculate and retain the results

For the first run of structure A, copy the settings and launch in PowerShell:

```powershell
Set-Location 'C:\bond-analysis\A'
Copy-Item -LiteralPath 'C:\Tools\Multiwfn\settings.ini' -Destination '.\settings.ini'
& 'C:\Tools\Multiwfn\Multiwfn.exe' '.\complex.fch'
```

Enter these responses at the corresponding prompts, one per line:

```text
9
1
y
```

`9` opens bond-order analysis, `1` calculates Mayer bond orders, and `y` answers the subsequent full-matrix export prompt. The atom-pair table appears on screen and the complete matrix is written to **`bndmat.txt` in the working directory**. Enter `0` at the bond-order menu to return to the main menu, then `q` to exit.

Preserve the matrix before another export uses the same filename:

```powershell
Copy-Item -LiteralPath '.\bndmat.txt' -Destination '.\mayer-matrix.txt'
& 'C:\Tools\Multiwfn\Multiwfn.exe' '.\complex.fch'
```

For fuzzy bond orders, enter:

```text
9
7
```

Retain the printed atom-pair table as `fuzzy-table.txt`, including the header that states the printing threshold. Copy the table from the terminal; this filename is your saved record, not an automatic Multiwfn output. Once the table has been captured, Ctrl+C exits the interactive program.

Before structure B's first run, copy A's local `settings.ini` into B's directory to use the same analysis settings, then change to B's directory and repeat both analyses. On reruns, keep the edited local settings instead of copying the distribution defaults again. Keep the matrix and fuzzy table beside each input, so results remain associated with their original atom indices. Record the selected entries in a comparison table with columns `structure`, `metal index`, `ligand index`, `Mayer`, `fuzzy`, and `calculation/settings`. Bond orders are dimensionless.

## Read weak contacts and compare definitions

- **A missing printed pair is not zero.** The default screen cutoff is 0.05, controlled by `bndordthres` in the working directory's local `settings.ini`. Read the full Mayer matrix for suppressed entries. For fuzzy contacts below the cutoff, lower `bndordthres` (for example, to `0.0`), restart Multiwfn and repeat option 7. Record the chosen cutoff.
- **Keep definitions separate.** Compare Mayer values across structures and fuzzy values across structures. Agreement in the ranking of contacts supports the bonding interpretation; disagreement needs inspection rather than averaging the indices. Polar bonds can yield appreciably different Mayer and fuzzy values. There is no universal metal–ligand bond-order threshold for assigning coordination.
- **Check spin labels.** For open-shell inputs, Multiwfn prints alpha, beta and total Mayer results. Use the summed alpha-plus-beta total consistently; do not mix it with the separately labelled result from the mixed alpha/beta density matrix.
- **Check numerical integration when small differences matter.** Fuzzy analysis is more expensive and less basis-sensitive than Mayer analysis. Its documented default integration grid is 40 radial by 230 angular points. To refine it explicitly, adjust `radpot` and `sphpot` and set `iautointgrid=0` in each working directory's local `settings.ini`; restart and rerun consistently across structures and retain the settings.

A successful Mayer calculation provides the atom-pair output and, after accepting export, `bndmat.txt`; fuzzy analysis provides its printed atom-pair table. If loading fails, basis information is missing, or calculation terminates before producing the table, no usable result has been established. Preserve signed values and output labels. Interpret the indices as computed descriptors of bonding within the chosen electronic model, not measured bond energies or a stand-alone proof of mechanism.

For research reporting, follow the package's `How to cite Multiwfn.pdf`; its required program citations are [Lu and Chen (2012)](https://doi.org/10.1002/jcc.22885) and [Lu (2024)](https://doi.org/10.1063/5.0216272).
