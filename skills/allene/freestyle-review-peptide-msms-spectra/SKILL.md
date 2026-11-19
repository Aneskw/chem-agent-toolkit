---
name: freestyle-review-peptide-msms-spectra
description: Review targeted peptide MS/MS scans from Thermo RAW files with FreeStyle in the Xcalibur suite, export peak tables, and assess supplied b/y-ion matches with scan provenance.
---

# Manual peptide MS/MS review with FreeStyle

Use this GUI workflow for acquired Thermo RAW data and an externally prepared precursor/fragment table. It covers individual spectrum review and evidence recording; it does not calculate peptide masses, search databases, operate instruments, or estimate quantitative reactivity.

## Prepare the software and inputs

Target **FreeStyle 1.8 SP3 (1.8.91.0)** supplied with **Xcalibur 4.8 SP1 (4.8.67.0)** and **Foundation 3.1 SP11 (3.1.387)**. Obtain the package through Thermo's [Software Download Portal](https://thermo.flexnetoperations.com). Follow the [4.8 SP1 release notes](https://docs.thermofisher.com/v/u/Xcalibur-4.8-SP1-Release-Notes), including the separate upgrade procedure for an existing system.

The documented environment is US-English Windows 11 x64 IoT Enterprise LTSC 2024 (24H2), .NET Framework 4.8 or later, 32 GB RAM, a 12-core processor, 1920 × 1080 display, and a 4 TB NTFS drive. Installation requires administrator rights: extract the installer ZIP to a local drive outside the desktop and launch ThermoLauncher.exe. The bundle includes Foundation and FreeStyle; Xcalibur needs no license key but remains subject to its EULA. Use a spreadsheet or text viewer to inspect exported CSV files.

Prepare these external inputs:

| Input | Required information |
|---|---|
| RAW files | File paths and sample/technical-replicate identifiers; retain originals. |
| Expected precursor table | Peptide sequence, modifications and sites, precursor charge and expected m/z; retention-time window in minutes if known. |
| Expected fragment table | Ion labels (series, ordinal and charge), theoretical m/z, and the complete expected y/b series used for counting. |
| Matching policy | Supplied numerical tolerance and units, plus any signal-selection rule. Obtain missing tolerance before assigning matches. |
| Output directory | A writable review folder outside Program Files; separate files for each RAW/scan. |

Do not infer a tolerance from the software defaults. For example, FreeStyle's FTMS default is 5 ppm, which is a software setting, not the study's acceptance threshold. Displayed mass precision defaults to four decimal places for FTMS and permits 0–5; retain exported digits and verify they support the chosen tolerance. See [Mass Precision parameters](https://docs.thermofisher.com/r/FreeStyle-User-guide/enGUID-F676E300-6D5B-4138-A200-3226DFC5F20D).

## Select and export one scan

Example handoff: three supplied replicate RAW files, an expected-ion spreadsheet, and a documented tolerance. Names such as `rep1_scanN_peaks.csv` below are output naming examples, not measured results.

1. Launch FreeStyle. Choose **File > New Workspace**, select the first RAW file, and click **Open**. The default workspace displays a TIC chromatogram above the first mass spectrum.
2. In **Workspace Options > Filter > Scan Filters**, select the acquired MS/MS filter corresponding to the target precursor and acquisition event. Prefer an actual filter from the file over constructing filter text. The default Time Range is `*` (the full acquisition); restrict it to the supplied window when appropriate.
3. Confirm the Spectrum view is linked to the intended chromatogram trace: a suffix such as **C1T1** identifies chromatogram 1, trace 1. Click a single chromatogram point at the relevant retention time. The red vertical marker selects that scan. Arrow keys move between scans satisfying the filter. Review nearby eligible scans individually.
4. Right-click the Spectrum view and choose **Ranges** to inspect its RAW file, filter, scan number and retention time. Enter a supplied scan number if needed; its corresponding time appears when you click elsewhere in the row. A linked spectrum inherits file/detector/filter from its chromatogram, so change the chromatogram filter rather than trying to edit those linked fields here. Use an individual acquired scan for each decision; do not pool fragment evidence across averaged scans.
5. With the target spectrum selected, choose **Workspace Options > Reports > Spectrum List**. It lists peak positions, intensities and relative intensities. Use the Field Chooser left of the first column heading to retain the required m/z and intensity columns. **Display Options > Exception Flags** adds flags when available; preserve them.
6. Click the Spectrum List view, then choose **Workspace Options > Exports > Export Selection As > To CSV File**, click **OK**, and save as `rep1_scanN_peaks.csv`. Open the saved CSV and confirm it contains numeric peak data for the intended scan, with adequate m/z precision. Preserve the export unchanged; put annotations in a separate table.
7. Select the chromatogram, then **Workspace Options > Reports > Scan Header**. Export this view by the same CSV procedure. Record the RAW path, complete scan filter, scan number and retention time alongside the peak file; do not assume a peak CSV automatically includes all provenance fields.

The [FreeStyle 1.8 SP3 guide](https://docs.thermofisher.com/r/FreeStyle-User-guide) documents these views. Its [export procedure](https://docs.thermofisher.com/r/FreeStyle-User-guide/enGUID-07B3D071-512A-4F02-86E7-A714FD5AE823) distinguishes numeric CSV from a Clipboard EMF image. Numeric export is not a guarantee of unrounded RAW precision: keep the RAW and check the actual exported digits before close mass comparisons.

## Match fragments and record the decision

Compare each supplied expected fragment m/z with the exported observed peaks under the documented tolerance. Keep ion identity and charge explicit. Record theoretical m/z, observed m/z, error in the policy's units, observed intensity, match status, and ambiguity for each ion. Count distinct assigned ions, not duplicate assignments to the same ion label.

For the manual identification method in [J. Med. Chem. 2020, DOI 10.1021/acs.jmedchem.0c01464](https://doi.org/10.1021/acs.jmedchem.0c01464), a single spectrum meets the reported criterion when **all or all but one expected y ions and at least two b ions** are identified. State the expected y-ion denominator and unmatched labels. A missing tolerance or incomplete expected series leaves this decision unresolved.

Save a review row containing:

- Sample and technical replicate, RAW path, software build, scan filter, scan number, RT (min), and exported peak/header filenames.
- Peptide/modification/precursor identity, expected-table version, tolerance and units.
- Matched/expected y count, matched b count, missing or ambiguous ions, decision and reason.

Repeat independently for every technical replicate. A scan that fails the criterion is not positive under this rule; failure to find a suitable acquired MS/MS scan is “no evaluable scan,” not proof of peptide absence. Check file identity, filter and time window before interpreting an empty view. Saturation flags indicate signals outside the detector's measurable range. Fragment support establishes the recorded identification assessment; peak intensity alone does not establish adduct occupancy or thiol reactivity.
