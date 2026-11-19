---
name: multiwfn-estimate-hydrogen-bond-energies
description: Use Multiwfn to identify hydrogen-bond critical points in a prepared wavefunction, extract electron density, and estimate individual or summed hydrogen-bond energies for neutral complexes.
---

# Estimate hydrogen-bond energies from Multiwfn topology

## Prepare the analysis

Use **Multiwfn 2026.11.3, Windows 64-bit**, with its graphical interface for checking bond paths. Obtain the binary archive from the [official download page](http://sobereva.com/multiwfn/download.html), selecting `Multiwfn_2026.11.3_bin_Win64.7z`, and extract it with its supporting files. No compilation is required. Obtain the matching [2026.11.3 manual](http://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf); sections 2.1.1, 2.2, 2.5 and 4.2.1 document this path.

Required inputs:

| Input | Requirement |
|---|---|
| Wavefunction | A prepared `.fch`/`.fchk`, `.wfn` or `.wfx` carrying the electron wavefunction, not just coordinates or a Gaussian text log. |
| Candidate bonds | Donor, hydrogen and acceptor atom identities mapped to the loaded structure's atom indices. |
| Calculation provenance | Geometry identity, total charge, electronic method, basis and relevant calculation settings. Confirm eligibility for the neutral-complex relation before calculating energies. |

The quantitative application in [Braire et al., J. Org. Chem. 2023](https://doi.org/10.1021/acs.joc.2c02476), p.1476, uses **B3LYP-D3(BJ)/ma-TZVPP single-point densities** on the studied transition states. Preserve that density-generation level when reproducing the analysis. Generating the wavefunction is an upstream handoff; this workflow starts after it exists. A formatted checkpoint avoids requiring Gaussian's `formchk` at analysis time.

The neutral relation below does not cover charged complexes. For those, report the topology/density and leave this energy estimate uncomputed; do not substitute the manual's charged relation or a potential-energy-density correlation.

## Locate and map each BCP

For example, after extracting Multiwfn to `C:\Tools\Multiwfn_2026.11.3`, launch it from PowerShell with your external wavefunction:

```powershell
Set-Location 'C:\Tools\Multiwfn_2026.11.3'
& .\Multiwfn.exe 'D:\analysis\complex.fchk'
```

The working directory determines where Multiwfn writes files. This example uses the extracted program directory. In the interactive console, enter the following options one at a time; annotations are explanations, not input:

| Menu/input | Action |
|---|---|
| Main menu `2` | Enter topology analysis. Retain the default real-space function, electron density. |
| Topology `2` | Search from nuclear positions for nuclear CPs. |
| Topology `3` | Search from atomic-pair midpoints, principally for bond CPs. |
| Topology `0` | Print CP positions, types and counts and open the visualization. |

Close the visualization with **RETURN**, enter topology option `8` to generate bond paths, then `0` to view again. The console now identifies atoms connected to each BCP. Enable **CP labels** in the GUI if necessary.

For each candidate D-H···A, identify the **H···A** path and its `(3,-1)` BCP using both endpoints and the visualization. Do not select the covalent D-H BCP or reuse CP indices from a tutorial or another wavefunction. Record D, H, A atom indices and the BCP index together.

## Extract density and calculate the estimate

Close the visualization, choose topology option `7`, and enter the mapped BCP index when prompted. Confirm `CP type: (3,-1)` and copy the **Density of all electrons** value, including its exponent. This is rho in atomic units (electrons per bohr cubed). Do not use alpha density, spin density, the Laplacian or `V(r)`.

For an eligible neutral complex, calculate each bond separately:

```text
E_kcal_mol = -223.08 * rho_au + 0.7423
E_kJ_mol   = E_kcal_mol * 4.184
```

For example, this PowerShell calculation accepts one measured density from the console and prints both energy units; it does not invoke a new quantum calculation:

```powershell
$rho = [double]::Parse((Read-Host 'Density of all electrons (a.u.)'),
                      [Globalization.CultureInfo]::InvariantCulture)
$energyKcal = -223.08 * $rho + 0.7423
[pscustomobject]@{
    rho_au = $rho
    E_kcal_mol = $energyKcal
    E_kJ_mol = 4.184 * $energyKcal
}
```

Repeat option `7` for each mapped bond. Preserve full density precision for arithmetic and round only the reported energies. If a sum is requested, sum the individual signed energies for the explicitly listed bonds; apply the intercept once per bond, rather than applying the equation to a summed density.

## Save and interpret results

Copy each BCP property block and the atom/path mapping from the console to an analysis text file. The manual's section 5.4 describes console copying; on Windows 11, hold Alt while dragging a rectangular selection, then press Enter to copy it. Save a table with:

```text
structure_id, wavefunction_file, charge, density_method, basis,
donor_atom, hydrogen_atom, acceptor_atom, BCP_index,
rho_au, E_kcal_mol, E_kJ_mol, status
```

Record Multiwfn version with the table and retain individual rows beside any requested sum. These are empirical hydrogen-bond energy estimates; negative values retain the stabilizing sign of the relation. They are not total interaction energies, transition-state energies or independently calculated reaction barriers. The study explicitly notes that other interactions affect relative transition-state energies.

A missing or ambiguous H···A path is an unresolved assignment, not a zero energy. The initial searches can miss CPs: for an isolated system, failure of `N(3,-3) - N(3,-1) + N(3,+1) - N(3,+3) = 1` signals incompleteness, while satisfying it alone does not prove completeness. If needed, topology search option `1` accepts a pair of atom indices as a midpoint starting guess; retry with the requested H and A indices and recheck the resulting path. For missing curved or long paths, consult manual section 3.14.3 for path step size and maximum-point controls. If the mapping remains unresolved, retain that status and omit its estimate; label any remaining sum as partial.

For research reporting, cite the [density-based correlation](https://doi.org/10.1002/jcc.26068) and the required Multiwfn method papers: [2012](https://doi.org/10.1002/jcc.22885) and [2024](https://doi.org/10.1063/5.0216272).
