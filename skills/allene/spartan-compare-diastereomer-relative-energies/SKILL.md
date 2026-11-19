---
name: spartan-compare-diastereomer-relative-energies
description: Compare supplied diastereomers with Spartan by retaining MMFF conformer candidates, refining them at gas-phase B3LYP/6-31G*, and comparing the lowest electronic energies among the tested conformers.
---

# Compare diastereomer energies in Spartan

## Setup and inputs

Use **Spartan '26 v1.1.0 for Windows**, with a valid Wavefunction license. Obtain the installer from the official [version-history/download page](https://www.wavefun.com/spartan-version-history). The [official documentation page](https://www.wavefun.com/spartan-documentation) provides individual/network license installation instructions and the [Spartan '26 manual](https://downloads-s3.wavefun.com/support/Spartan26Manual.pdf).

Start with one correctly specified structure per diastereomer. The example below uses two supplied native documents, `A.spartan` and `B.spartan`, containing the same atoms and connectivity but different stereochemistry. Structures may also be built in Spartan or imported with **File > Open**, for example from SDF or MOL2; verify bond orders, hydrogens and stereochemistry after import. Supply the intended charge and spin state rather than relying on builder defaults.

The example assumes neutral, closed-shell molecules. Use the actual supplied charge/spin for other systems. This workflow compares optimized gas-phase electronic energies; it does not compute solution free energies, reaction rates or experimental stereochemical assignments.

For a diastereomer-stability comparison, retain multiple distinct conformers per candidate for DFT refinement. The lowest MMFF conformer need not remain lowest at DFT. Supply a comparable conformer-selection policy for both diastereomers, recording any MMFF energy window or search limit; there is no universal conformer count. A requested single-conformer comparison is a restricted alternative described below.

## Search and optimize each diastereomer

Run these steps for A, then repeat for B with the same search settings and DFT model.

1. Open `A.spartan`. Use **File > Save As** in native format to create `A-mmff.spartan`, preserving the supplied structure. Each working document should contain only its intended diastereomer.
2. Open **Setup > Calculations** and configure the MMFF search:

   | Control | Selection |
   | --- | --- |
   | Calculate | Conformer Distribution |
   | Method class | Molecular Mechanics |
   | Force field | MMFF |
   | Global Calculations | Unchecked; settings apply to the selected molecule |

   Select plain MMFF rather than the neural-network-corrected or multistep DFT conformer protocols. Review **Geometry > Set Torsions** for the bonds and rings included in the search; preserve the intended stereochemistry. Record any restrictions or **Maximum Conformers Examined** limit. Spartan normally chooses systematic or Monte-Carlo searching according to conformational freedom; a limit below the estimated conformer count forces Monte-Carlo searching.
3. Click **Submit**, confirm the working-document name if prompted, and wait for completion. Open the returned ensemble document (normally a `.Conf`-named document; follow the actual prompt). Save the full MMFF ensemble. The original Conformer Distribution document displays a lowest-energy geometry alongside averaged properties; use the **ensemble's individual rows** for selection and energy records. In **Display > Spreadsheet**, label conformers `A-001`, `A-002`, etc. Preserve a native copy containing the distinct candidates selected by the supplied policy; remove unwanted entries only from that copy.
4. Use **File > Save As** on the selected ensemble to create `A-dft.spartan`. It should contain only A's selected conformers. In **Setup > Calculations**, set:

   | Control | Selection |
   | --- | --- |
   | Calculate | Equilibrium Geometry |
   | Electronic state / medium | Ground state / Gas |
   | Method class / functional / basis | Density Functional / B3LYP / 6-31G* |
   | Total Charge / Unpaired Electrons | Neutral / 0 for this example |
   | Global Calculations | Checked, to refine all retained conformers in this working document |

   Use **More** in a method menu if needed to locate B3LYP. Select B3LYP explicitly: B3LYP-D3 and other functionals are different models. Submit and wait for completion. Total Charge and Unpaired Electrons matter at this DFT stage; molecular mechanics ignores those controls.
5. Open **Display > Output** for each retained entry. Check the Summary for the requested model, formula and electronic state; inspect the Output tab's Optimization history and final total energy. An error such as `OPTIMIZATION has exceeded N steps` means that conformer's optimization did not finish satisfactorily. Keep its unresolved status instead of using an intermediate energy. Check final stereochemistry and connectivity, and identify different starting conformers that converged to the same structure. Save the completed DFT ensemble and retain each starting-to-final conformer mapping.

For an explicitly requested shortcut using only one MMFF-selected conformer per diastereomer, choose **Equilibrium Conformer** in step 2 and **Global Calculations** unchecked for the single-entry DFT job. Label its result "DFT energies of MMFF-selected starting conformers"; it does not establish the lowest DFT conformer of either diastereomer.

## Compare and retain the results

After inspecting both DFT ensembles:

1. Open `A-dft.spartan` and save a native copy as `comparison.spartan`. Use **File > Append Molecule(s)** to append `B-dft.spartan`. This comparison document combines completed results; no further calculation is required.
2. Open **Display > Spreadsheet**. Keep candidate and conformer labels on every row. Click **Add** and select **Energy (au)**. These are the individual final DFT total energies, not MMFF search energies or the original document's averaged properties. Identify the lowest successfully converged DFT energy **within each diastereomer's tested set**; keep all per-conformer energies available for inspection.
3. Select the row with the lowest, most negative energy. Click **Add > Molecule List > Energy from Molecule > Delta E (kJ/mol)** (displayed as the delta symbol). This gives energies relative to that selected reference. Confirm the unit in the column header; the reference should have zero relative energy.
4. Save `comparison.spartan`. Retain the full MMFF ensembles, selected starting structures, `A-dft.spartan` and `B-dft.spartan`. Report each diastereomer's lowest tested DFT energy in au and relative energy in kJ/mol, its conformer ID, numbers selected/completed, failed entries, charge/spin, selection/search settings and software build. To share calculation details, right-click inside **Display > Output** and use **Copy** or **Save As PDF**.

A positive relative energy means that structure is higher in electronic energy than the selected reference at this model. Only compare results with matching composition, charge, spin and computational settings. MMFF selection and local DFT refinement can still miss important conformers; unresolved DFT jobs leave coverage incomplete. Report ordering as conditional on the tested sets rather than a verified global ranking. The workflow supplies neither ensemble free energies nor an experimental diastereomer ratio.
