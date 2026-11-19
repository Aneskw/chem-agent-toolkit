---
name: mnova-review-and-export-nmr-documents
description: Review existing .mnova NMR documents in Mnova 17, curate peak picks, and export peak tables or spectral CSV data. Use for compound-specific spectra and deposited NMR documents when an interactive Mnova session is available.
---

# Review NMR documents and export usable data

## Prepare the session and inputs

Use **Mnova 17.0.1 with the NMR plugin** and a valid license or active trial. Obtain the platform installer and license/trial through [Mestrelab downloads](https://mestrelab.com/download). This workflow uses the desktop GUI; it requires an interactive session capable of selecting pages, spectra, and dialogs.

Start with an existing `.mnova` document and its sample identity. Identify the nucleus, solvent, and experiment from the document or accompanying acquisition information. Review the stored spectrum before changing its processing or chemical-shift reference. Acquisition and full reprocessing of raw FIDs are separate tasks.

## Example: review a deposited compound spectrum

The [Zenodo record 10951810](https://zenodo.org/records/10951810) contains compound-named NMR documents. For an example input, download `3a.mnova` from its Files list, or run this in a working folder on Windows:

```powershell
curl.exe --fail --location --output "3a.mnova" "https://zenodo.org/records/10951810/files/3a.mnova?download=1"
```

For your own compound, substitute its document. The record supplies checksums for checking a download if needed.

1. Open the document with **File > Open** (`Ctrl+O`; `Cmd+O` on macOS). Use **File > Save As** to create `3a-reviewed.mnova`, retaining the downloaded original.
2. In the page navigator, select the experiment to review, such as the proton spectrum. If the navigator is hidden, use **View > Pages**. Do not assume a particular page number. Select the intended spectrum object: the active object has green handles. Other selected objects have white handles. Operations can affect all selected objects or pages, so leave only the intended selection.
3. Open **View > Tables > Peaks** and inspect existing picks before replacing or adding them. Double-click a table row to zoom to its peak; compare the label and spectral feature.
4. Where picks need to be generated, use **Analysis > Peak Picking**. Choose the appropriate mode:

| Mode | Invocation and use |
| --- | --- |
| Automatic | Click the Peak Picking toolbar icon. GSD is the default automatic method; Standard is available in Peak Picking Options when deconvolution is unnecessary. |
| Manual threshold | Choose Manual Peak Picking, shortcut `k`, then drag over the spectral area to pick. |
| Peak by peak | Choose Peak by Peak, `Ctrl+k` or `Cmd+k`, then click individual highlighted peaks. Normally the peak top is interpolated; Shift-click permits an arbitrary position. |

5. Curate the table against the spectrum. Double-click **Type** or **Flags** cells to correct classifications such as compound, solvent, impurity, or artifact. Delete an unwanted pick using the Peaks Table Delete control; this removes the annotation rather than removing a resonance from the measured spectrum. Automatic solvent/impurity classifications need review.
6. Save the reviewed native document, then export the selected spectrum as described below. Repeat with distinct filenames for other experiments.

For picking options and table controls, consult the [version 17 Peak Picking manual](https://mestrelab.com/downloads/mnova/manuals/latest/peak-picking.html).

## Export and inspect the results

| Result | Interface and material choices |
| --- | --- |
| Peak table | In **Setup Table**, mark the required columns **Visible**. Use **File > Save As > Script: NMR Peaks Table**, select an output path, and retain the dialog's supported file extension. Only visible columns are exported. |
| Simple 1D peak list | **File > Save As > Script: NMR 1D Peak List** supports `.csv` and `.txt`. |
| Spectral trace | **File > Save As > NMR Custom CSV File**. For a real spectrum choose **PPM+Re**; other supported combinations include PPM+Re+Im, Hz+Re, and Hz+Re+Im. Choose the desired left-to-right or right-to-left order. |
| Editable review | Save the complete reviewed document as `.mnova`; CSV and text exports do not preserve its complete multipage state. |

Use a distinct basename such as `3a-1H-peaks` or `3a-1H-spectrum.csv` for each export. Inspect the saved file's columns, delimiter, coordinate direction, and units before downstream analysis. Table fields include chemical shift in ppm/Hz, intensity as height, and width as FWHM in Hz; height is not an integrated proton count. A spectral CSV contains sampled signal values, whereas a peak table contains detected or manually selected features.

An empty peak export does not establish absence of the compound: inspect the active spectrum, existing picks, table filters, and picking threshold. Missing columns usually require changing **Setup Table > Visible** and exporting again. If picking or export controls are unavailable, check the NMR license/trial and active spectrum before proceeding.

Report the source document, experiment, picking method and any changed options, classification edits, and output paths. Peak picks and classifications support spectral review; they do not alone establish molecular identity, absolute configuration, or quantitative purity.
