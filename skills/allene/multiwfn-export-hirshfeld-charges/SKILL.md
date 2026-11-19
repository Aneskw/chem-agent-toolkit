---
name: multiwfn-export-hirshfeld-charges
description: Calculate and export normalized Hirshfeld atomic charges with Multiwfn from prepared molecular wavefunctions, and compare charges using a supplied atom mapping.
---

# Hirshfeld charges from molecular wavefunctions

## Prepare

Use **Multiwfn 2026.11.10**. Obtain the Windows 64-bit binary package from the [official download page](http://sobereva.com/multiwfn/download.html), accept its license terms, and extract the package with its runtime DLLs and `settings.ini`. The page also supplies the [2026.11.3 manual](http://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf); sections 2.1 and 2.5 cover setup and wavefunction formats, and 4.7.1 covers this analysis. Follow the bundled `How to cite Multiwfn.pdf` when publishing results.

Required inputs:

| Input | Requirement |
|---|---|
| Molecular wavefunction | A prepared `.fch`/`.fchk`, `.mwfn`, `.wfn`, `.wfx` or supported `.molden` file containing Gaussian-type wavefunction information. Coordinates alone in `.xyz`/`.pdb` are insufficient. |
| Molecular charge | Known net charge, in units of elementary charge, for checking the loaded system and integration. |
| Atom mapping | Corresponding atom indices across structures, supplied independently when their ordering differs. Check element identities as well. |

The normal path below is for a nonperiodic molecule and built-in sphericalized free-atom reference densities, available for H through Lr. It calculates ordinary Hirshfeld charges; Hirshfeld-I, ADCH and CM5 are separate population methods.

For pseudopotential/ECP wavefunctions, check the loading messages for core-density treatment. Default `readEDF=1` reads a supplied `.wfx` EDF field; default `isupplyEDF=2` supplies missing core density from the built-in library. Preserve a consistent treatment across structures; investigate missing or incompatible core-density information using manual Appendix 6.4 before interpreting charges.

## Calculate and check integration

Example paths below are placeholders for an existing wavefunction and extracted Windows package. Start in the directory where the charge export should be written; passing `-set` selects the settings file explicitly:

```powershell
Set-Location 'D:\analysis\A'
& 'C:\tools\Multiwfn_2026.11.10\Multiwfn.exe' 'D:\analysis\A\molecule_A.fch' -set 'C:\tools\Multiwfn_2026.11.10\settings.ini'
```

Check the loaded atoms, electron count and net charge against the prepared input. At the successive interactive menus enter:

```text
7
1
1
```

These select population analysis, Hirshfeld atomic charges, and built-in free-atom densities. Wait for calculation to finish and inspect the output **before answering the export prompt**:

- `Hirshfeld charge of atom ...` and `Summing up all charges` report the unnormalized result. Compare that sum with the known molecular charge, rather than with zero for every system.
- `Normalize sum of atomic populations to actual number of electrons...` precedes `Final atomic charges`. These final values are normalized by the program. A normalized sum matching the molecular charge does not establish adequate quadrature.

If the raw sum differs appreciably from the expected charge, answer `n`, increase integration density in the selected `settings.ini`, restart, and repeat. Defaults are `radpot=75` radial and `sphpot=434` angular points; the manual suggests `100` and `590` for greater accuracy. Check the reported radial/angular grids and the raw sum again. Do not invent a universal numerical tolerance; assess the charge differences of interest against integration sensitivity, retaining the settings and raw sum with the results.

## Export and compare

Once integration is satisfactory, answer `y` at the export prompt. Multiwfn writes the **normalized** charges in the current working directory, naming the file from the input basename before its first dot plus `.chg`: `molecule_A.fch` produces `molecule_A.chg`. An existing file with that name is **overwritten**. Preserve separate names or directories for different structures and integration trials.

Inspect the resulting text file, for example after exiting Multiwfn:

```powershell
Get-Content 'D:\analysis\A\molecule_A.chg'
```

Each whitespace-delimited row contains `element X Y Z charge`, with coordinates in angstroms and charge in elementary-charge units. There is no header or explicit atom-index column: row 1 corresponds to atom 1, continuing in loaded atom order. Verify the row count, element sequence, coordinates, and charge sum against the final screen output and input structure; small summation differences can arise from printed precision. A missing export after answering `n` is intentional. A missing-wavefunction-information error requires a wavefunction-bearing input, not a coordinate-only file.

Repeat the calculation for structure B with the same reference-density choice and adequately converged integration. Join the results using the supplied mapping, retaining `atom_A`, `atom_B`, `element`, `q_A`, `q_B`, and `delta_q = q_B - q_A`. Positive `delta_q` means that the corresponding atom is more positive in B. For protonation/deprotonation comparisons, map the common atoms explicitly; an added or removed proton has no matching row in the other structure.

These are density-partitioned partial charges. Their differences can describe redistribution within the chosen computational model; they are not measured atomic charges. Hirshfeld charges alone generally reproduce molecular dipole moments and electrostatic potentials poorly (manual section 3.9.1), so the printed charge-derived dipole is not an independent validation of the wavefunction.
