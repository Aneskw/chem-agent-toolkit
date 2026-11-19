---
name: spartan-compare-conformer-weighted-nmr
description: Use Spartan26 to calculate Boltzmann-weighted carbon NMR shifts and compare proposed stereoisomers against assigned experimental shifts using DP4 and absolute errors.
---

# Compare stereoisomers with conformer-weighted carbon NMR

## Software and inputs

Use licensed **Spartan’26 Parallel Suite**, Windows/macOS v1.1.0 or Linux v26.1.0. Obtain the supported installer through [Wavefunction’s version history](https://www.wavefun.com/spartan-version-history); the [downloads page](https://www.wavefun.com/downloads) and [documentation page](https://www.wavefun.com/spartan-documentation) provide platform and license installation instructions. A working graphical session and a valid individual or network license are required.

This workflow uses the retained **NMR Spectrum / Density Functional** task. Select its models explicitly below. The newer **NMR Protocol** task also offers ML workflows with different computational steps.

Supply:

- Chemically reasonable candidate diastereomer structures with defined stereochemistry and a common atom correspondence.
- Experimentally assigned **13C chemical shifts in ppm**, associated with atom labels, for one experimental species being compared against those alternatives. Peak acquisition and initial assignment are external inputs.

The result is a saved native `.spartan` document containing the candidate calculations and an inspectable spreadsheet of DP4 percentages and shift-error statistics. Calculations search conformations separately for each candidate.

## Prepare a two-candidate comparison

Use the supplied structures as candidates A and B in one Spartan document. For candidates differing only at stereocenters, preserve labels by making them from one sketch: copy the common sketch before adding the first stereochemical marker, then use **File > Sketch New Molecule**, paste, and add the other stereochemistry. Convert the sketches to 3D. **Geometry > Generate Isomers** is an alternative when the desired alternatives can be generated from selected stereocenters; its output preserves labeling. Retain the intended candidate set.

Check that corresponding carbon atoms have identical labels in every candidate; matching row order or molecular formula alone is insufficient. Open **NMR > Enter Expt. 1H/13C shifts** on A. Enter the supplied assigned carbon shifts manually, or paste the source table into **Scratch Pad** and select the delimiter that correctly separates its columns. Reorder/edit the scratch data, then copy the assigned shift column into the **13C** column under **Experimental Chemical Shifts**. Verify every atom-to-shift mapping, especially combined labels for equivalent atoms. Spartan recognizes equivalent atoms; only unique assignments need entry. Labels can be corrected in the table or in 2D by editing the blue NMR atom labels.

Review **Geometry > Set Torsions** for each candidate. Marked bonds and ring atoms define the conformational search. Double-clicking a marked bond or ring atom removes that degree of freedom. Keep chemically relevant rotors and ring flexibility; do not copy a tutorial’s molecule-specific reduced torsion set. The displayed conformer count excludes ring conformers and is an upper bound before duplicate/high-energy removal. Changing these settings changes the ensemble being considered.
## Calculate the ensemble shifts

Open **Setup > Calculations** and configure the following for both A and B:

| Control | Selection |
| --- | --- |
| Task | NMR Spectrum |
| Method | Density Functional |
| NMR functional / basis | ωB97X-D / 6-31G* |
| Energy model under `using` | ωB97X-V/6-311+G(2df,2p)[6-311G*] |
| Geometry model under `using` | ωB97X-D/6-31G* |
| Global Calculations | Checked: submit all candidates in the document |

The energy model supplies the conformer weights; the geometry and empirically corrected GIAO shift calculations use the specified ωB97X-D model. Select the energy and geometry entries without the **Est.** prefix. Keep the protocol’s default intermediate thresholds; **Details** exposes the multistep calculation and its energy/conformer limits. A custom structure list would replace the initial MMFF conformer search; leave it unused for this path.

Click **Submit**, naming the document, for example `candidate-carbon-nmr.spartan`. Monitor progress in **Options > Monitor**. Flexible candidates can require hours or longer; a submitted or still-running job is not a completed comparison. Wait for every candidate’s calculation to finish before interpreting rankings.

## Compare and save

1. Open **Display > Properties > NMR**. Select **Boltzmann Average**. **Best Fit** instead selects the individual conformer whose shifts best match experiment; it is a different comparison and must not stand in for the ensemble result.
2. Set **Experimental Data From** to A, the molecule holding the experimental assignments, and click **Apply Globally**. Both candidates must be compared with that same experimental dataset. The `<current molecule>` option is appropriate only when each candidate already carries the intended experimental data, as when generated from a populated parent.
3. Inspect each candidate’s **RMS**, **Mean Absolute**, **Max Absolute** errors (ppm) and **DP4** (%). Use the posting button to the left of each statistic to add it to **Display > Spreadsheet**. Compare candidates side by side, keeping Boltzmann Average selected.
4. Investigate large local discrepancies with **Model > Configure > Label > (Calc. – Expt.) Chem Shift**. Recheck atom correspondence, imported columns, equivalent atoms, stereochemistry and search settings before treating a mismatch as structural evidence. DP4 requires both calculated and experimental shifts; absent statistics are not evidence against a candidate.
5. Use **File > Save** to retain the native `.spartan` document with calculations, experimental assignments and posted statistics. Report the candidate labels, model settings, averaging mode, dataset source, DP4 and all three error measures alongside the saved document path.

Larger DP4 percentages indicate stronger relative fit among the supplied alternatives. Read that ranking together with absolute shift errors: a winning candidate can still fit experiment poorly, and a high DP4 does not establish that untested alternatives are excluded. Do not introduce an automatic acceptance threshold from a tutorial example. Agreement supports an assignment; it does not establish it independently.

For interface details, consult the official [Spartan’26 Tutorials & User’s Guide](https://downloads-s3.wavefun.com/support/Spartan26Manual.pdf), printed pp. 32–33 (shift import), 142–143 (shared data and DP4), 203–208 (ensemble calculations), and 246–247 (torsions). The [Spartan’26 release notes](https://downloads-s3.wavefun.com/support/NewFeatures.pdf), pp. 2 and 5, identify the renamed NMR menu and retained task; older tutorial passages calling it **Expt. Data** refer to the same data-entry role.
