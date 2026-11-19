---
name: skyline-calculate-modified-peptide-precursors
description: Calculate theoretical 2+ and 3+ precursor targets in Skyline from peptide sequences, specified cysteine sites, and verified modification formulas; save the document and export a precursor reference table.
---

# Calculate modified-peptide precursor targets in Skyline

## Prepare

Use **Skyline 26.1, 64-bit, on Windows**, from the official [installation page](https://skyline.ms/home/software/Skyline/wiki-page.view?name=SkylineInstall_64_26-1). This workflow uses the graphical application. Raw MS data, a spectral library, and an instrument connection are unnecessary for these calculations.

Supply each variant's unmodified sequence, intended modification sites (positions counted from 1 within the peptide), a unique modification name, and its verified **net elemental change relative to the unmodified residue**. Preserve any protein-position mapping separately. Use positive precursor charges `2, 3`.

A reagent's intact formula may differ from the composition added during attachment. Resolve losses and isotope substitutions in the input formula; a rounded mass increment alone does not establish complete chemistry.

For a concrete carbamidomethyl example:

| Sequence | Peptide site |
|---|---|
| FSGDLDDQTCR | C10 |
| IGCLLK | C3 |
| SLEEKIGCLLK | C8 |

[Unimod record 4](https://www.unimod.org/modifications_view.php?editid1=4) gives carbamidomethyl composition `H(3) C(2) N O`, monoisotopic increment **57.021464 Da**, and cysteine specificity. Enter `C2H3NO` in Skyline. This example uses one modification condition; other adducts require their supplied, verified formulas.

## Build and calculate

1. Open **Blank Document**, select the upper-right **Proteomics interface**, and choose **Settings > Default**. This resets document settings; start in a fresh document.
2. Open **Settings > Peptide Settings > Modifications**. Uncheck default **Carbamidomethyl (C)** and other unintended structural/isotope modifications. Use explicit site assignments for this workflow.
3. Beside **Structural modifications**, choose **Edit List > Add**. Enter name `CAM_explicit_C`, **Amino Acid** = `C`, no terminal restriction, **Variable** unchecked, and **Chemical Formula** = `C2H3NO`. Confirm the formula-derived monoisotopic increment against the verified input and accept the dialogs. Leave this definition unchecked in the document's structural checklist; it remains available for explicit residue selection. Fragment neutral losses are unnecessary for precursor calculation.
4. Open **Settings > Transition Settings**:

   | Tab | Settings |
   |---|---|
   | Prediction | **Precursor mass** = `Monoisotopic`; **Product ion mass** = `Monoisotopic` |
   | Filter | **Precursor charges** = `2, 3`; **Ion charges** = `1`; **Ion types** = `y, b`; enable **Auto-select all matching transitions** |
   | Library | Uncheck **If a library spectrum is available, pick its most intense ions** |

   The ordinary `y, b` settings retain child transitions so the precursor targets remain in the document. The reference report below selects precursor properties only, without exporting or interpreting fragment predictions. Check **Instrument** minimum/maximum m/z limits cover the intended precursors and retained products; adjust when necessary. The [Skyline 26.1 PRM tutorial](https://skyline.ms/tutorials/26-1/PRMOrbitrap/en/) defines the ion-type controls.
5. Copy the sequence column as plain text, one peptide per line, and use **Edit > Paste** in Targets. Skyline creates a peptide list; this route needs no FASTA/background proteome.
6. Select each peptide and choose **Edit > Modify Peptide**. In the per-residue **structural** modification dropdown, select `CAM_explicit_C` only at the intended C. Leave other sites blank unless the input specifies further modifications. Accept and inspect all sites for unintended defaults.
7. Expand each peptide in Targets. Confirm both `++` and `+++` precursor entries and record displayed m/z with variant, sequence, sites, and charge. This three-peptide, one-condition example should retain six precursor entries. If a charge is absent, inspect/select it in the peptide's drop-arrow pick list; check m/z limits and retained transitions as well.

For mutually exclusive adduct alternatives, repeat in separately named documents, replacing the explicit C modification for each condition. Do not combine alternative adducts at one site.

## Save and export

Save with **File > Save** to a variant-specific `.sky` file. Export calculated precursor properties directly through **File > Export > Report**:

1. Click **Edit List**, then **Add**, and name the report `Modified peptide precursors`.
2. In the column tree, expand **Peptides > Precursors** and select the precursor **Modified Sequence**, **Precursor Charge**, **Precursor Mz**, and **Isotope Label Type** fields. Use the displayed hierarchical labels to distinguish these from product-ion fields. Select only sequence/precursor properties: no Transitions, replicate or result fields are needed.
3. Click **Preview**. Verify one row per retained precursor, correct modification increments and charges, and six precursor rows for this three-peptide example. Return to the column selection if rows repeat because transition/result fields were included.
4. Save the report definition, select it in Export Report, and export CSV under a variant-specific filename. Inspect the exported headers, numeric precision and row identities against Targets.

The [Skyline 26.1 custom-report tutorial](https://skyline.ms/tutorials/26-1/CustomReports/en/) documents report creation, preview and CSV export; the [official precursor-report example](https://skyline.ms/_webdav/home/software/Skyline/%40files/tutorials/PRMOrbitrap-22_2.pdf) illustrates the sequence, precursor m/z and charge fields. These properties exist without raw data. Keep the original CSV and add the variant and original site assignments from the input record to the delivered reference table. Retain **variant + sequence + site assignment + isotope label + charge** as identity; rounded m/z alone is insufficient. m/z is mass-to-charge, whereas the modification increment is a neutral-mass change in Da.

### Optional instrument transition list

If a transition list is requested, configure the intended fragment-ion types/charges and instrument predictors separately. For the documented SCIEX example, select monoisotopic product mass, `y, b` ions with product charge `1`, and SCIEX collision-energy and declustering-potential predictors, then use **File > Export > Transition List** and SCIEX format. Follow the [26.1 method-editing tutorial](https://skyline.ms/tutorials/26-1/MethodEdit/en/) for grouping or split exports, collecting every returned CSV. Its rows describe precursor/product transitions and repeat precursor values; they are not distinct precursor targets. This optional instrument setup is unnecessary for the precursor reference table.

Missing targets/export rows warrant checking modification applicability and sites, charges, retained transitions, and m/z limits. Reopen **Modify Peptide** for unexpected mass shifts. Preserve the `.sky` documents with their definitions and settings.

Deliver documents, original report CSV files, and the calculated reference table. These are theoretical targets for acquisition planning or spectrum review; they do not establish observed adduction, identification, or reactivity. Any optional instrument transition list requires separate method validation.
