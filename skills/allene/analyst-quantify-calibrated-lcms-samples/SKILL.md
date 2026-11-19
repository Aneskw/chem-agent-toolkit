---
name: analyst-quantify-calibrated-lcms-samples
description: Generate, review, save and export internal-standard LC-MS/MS concentrations from acquired WIFF samples and an existing quantitation method in a supported Windows 10 SCIEX Analyst project.
---

# Calibrated LC-MS/MS results in SCIEX Analyst

Use the Quantitation Wizard to create a Results Table, inspect integration and calibration, and hand off reviewed concentrations. This workflow starts with acquired data and an assay-specific method; acquisition, assay validation, SCIEX OS migration and pharmacokinetic modeling require separate workflows.

## Prepare the environment and inputs

Use licensed **SCIEX Analyst 1.7.4 with HotFix 2** on a supported **Windows 10** workstation. Obtain software, license activation and the base installation guide through [SCIEX software downloads](https://sciex.com/support/software-support/software-downloads). HotFix 2 requires Analyst 1.7.4 with HotFix 1 and AB SCIEX Reporter Template Suite 3.2 already installed. Have the workstation administrator follow the [HotFix 2 installation notes](https://download.sciex.com/Analyst-1.7.4-HotFix-2-Release-Notes.pdf), including applicable instrument firmware requirements, before processing. This Skill assumes setup is complete.

Analyst is unsupported on Windows 11 and is undergoing a support phase-out. Check [SCIEX's lifecycle notice](https://sciex.com/support/software-support/analyst-software-end-of-support) before selecting this workflow for an existing installation.

Have these external inputs ready:

| Input | Required information |
| --- | --- |
| Analyst project/subproject | Acquired `.wiff` samples containing calibration standards, QCs and unknowns; retain original WIFF filenames once referenced by a Results Table. |
| Existing `.qmf` quantitation method | Correct analyte transitions, retention/integration settings, assigned internal standards and calibration settings for these data. The method must be available in the selected project. |
| Sample metadata | Identities, sample types, actual standard/QC concentrations and units, internal-standard information, and any applicable preparation/dilution factors. Resolve these from the assay records. |
| Review criteria | Assay-approved QC/calibration criteria and any validated Results Table query. The manual's example query named `Accuracy 15%` is not a universal acceptance rule. |

The representative path below uses one acquired batch, its existing method and an existing assay-approved query. Substitute their actual names; no study data or method files are bundled. Use the [Analyst Software User Guide](https://sciex.com/content/dam/SCIEX/pdf/customer-docs/user-guide/an-software-user-guide-en.pdf), pp. 75–86, for the wizard and review controls.

## Generate and review the Results Table

1. Select the project/subproject from the software toolbar's project list. Under **Quantitate** on the Navigation bar, double-click **Quantitation Wizard**.
2. On **Create Quantitation Set – Select Samples**, open the data folder, select the batch WIFF file and add its intended standards, QCs and unknowns. **Add All** adds all samples in the selected file. Exclude acquisitions that terminated abnormally or unexpectedly. Click **Next**.
3. On **Select Settings & Query**, choose **Select Existing: Query** and the assay-approved query. Query criteria must be validated for the application. Click **Next**.
4. On **Select Method**, click **Choose Existing Method**, select the project's `.qmf`, then **Finish**. The Results Table opens. If the intended method or samples are missing, resolve the project/input mismatch before interpreting results. **Tools > Results Table > Add/Remove Samples** changes the included sample set.
5. Review sample types and actual concentrations against the metadata. Standards define the curve; QCs have known concentrations but are treated as unknowns for comparison against their actual values. Check analyte/internal-standard assignments in the method rather than inferring them from names.
6. Select an analyte, then **Tools > Peak Review > Pane**. Select table rows or use the pane arrows to inspect peaks. Check peak identity, integration boundaries and the associated internal-standard signal. Inspect statistics and the internal-standard metric plot; **Metric Plot** is available from the Results Table right-click menu. Investigate anomalous internal-standard responses against the assay records before accepting concentrations.

If integration needs correction, review the method's algorithm parameters before drawing peaks manually. In Peak Review, **Show or Hide Parameters**, **Specify Parameters** and **Apply** permit parameter adjustment. **Update Method** propagates algorithm values to all peaks for that analyte or internal standard, not every compound. Recheck affected samples after updating. For an assay-permitted manual correction, select **Manual Integration Mode**, drag between the peak start and end, then **Accept**; clearing **Manual Integration** discards the change, and **Revert to Method** restores method-based integration. The **Record Modified** column identifies manual or sample-specific changes. Manual integration is a last resort; see guide pp. 79–84 for algorithm-specific controls.

## Inspect and accept calibration

With the Results Table open, choose **Tools > Calibration > Pane**. Select the analyte and **Area** response. For an internal-standard method, inspect the analyte-to-internal-standard area response and verify the method's concentration/IS configuration.

For an assay using weighted linear calibration:

| Control | Explicit setting |
| --- | --- |
| **Regression > Fit** | **Linear** |
| **Regression > Weighting** | **1 / x** |
| Confirm | **OK**, inspect the curve, then **Accept** to save reviewed changes |

Use these settings only when appropriate to the assay; do not treat them as software defaults. Review standards, QC agreement and integration before excluding calibration points. Apply the assay's documented acceptance criteria rather than changing the fit merely to improve its appearance. Repeat review for each analyte. **Calculated Concentration** reflects changes to the fitted curve, so review concentrations again after calibration or integration changes.

## Save and hand off concentrations

Save the reviewed Results Table in Analyst, retaining its calibration and review context. Then use the **Export as Text** toolbar control to write a `.txt` table for downstream use. Choose an existing destination directory: exporting to a nonexistent typed path can make Analyst stop responding.

Check the exported sample/analyte identities, sample coverage, calculated concentrations and units against the saved Results Table. Analyst can export all table data or only visible columns; make the export choice match the intended handoff. Keep enough identity and review information to trace each value back to its sample and analyte.

Two documented boundaries require extra attention:

- Different concentration units per analyte in a method do not reliably propagate to the Results Table: only the first set of units is used. Verify units against the method and assay records before labeling exported concentrations.
- **Sum Multiple Ions** Results Tables have a documented text-export defect involving incorrect column headers. If used, reconcile headers and values against Analyst before handing off the text file.

A generated table or a numeric concentration alone does not establish assay acceptance. Missing peaks, anomalous IS response, failed QC criteria or inconsistent units require resolution before reporting. The text export is a handoff; retain the native Results Table for subsequent review. Release-note details are in [Analyst 1.7.4 base release notes](https://sciex.com/content/dam/SCIEX/pdf/customer-docs/release-notes/analyst-software-release-notes-en.pdf), Quantitate known issues, pp. 76–78.
