---
name: prism-plot-assay-summaries
description: Plot concentration-dependent assay means with externally calculated SDs in GraphPad Prism when normalization and biological-replicate aggregation are already complete.
---

# Plot assay summaries with supplied SDs in Prism

## Prepare

Use GraphPad Prism **11.1.0** for Windows or Mac with a suitable license and desktop GUI access. Obtain the installer through the official [Prism updates page](https://www.graphpad.com/updates) ([Windows](https://cdn.graphpad.com/downloads/prism/11/InstallPrism11.msi), [Mac](https://cdn.graphpad.com/downloads/prism/11/InstallPrism11.dmg)). Confirm the installed version before following this workflow.

Start with one concentration and each compound's final mean response and SD at that concentration. Normalization, biological-replicate aggregation and SD propagation must already be complete; obtain those summaries upstream if they are missing. Keep the supplied response definition, normalization reference and replicate information with the table.

| Field | Placement and meaning |
|---|---|
| Concentration | Numeric X column, in one declared unit such as µM |
| Compound | One Y data set per compound; use its name as the column title |
| Mean | Y mean subcolumn; preserve the supplied normalization and response units |
| SD | Y SD subcolumn; an error magnitude in the same units as the mean, not an endpoint or SEM |
| Missing observation | Blank cell; do not substitute zero |

For plotting only, N is unnecessary. Do not pool technical replicates, recompute the supplied SDs, or infer a statistical test or dose-response model from this plotting task.

## Enter and graph

1. Launch Prism. In the Welcome or **New Table & Graph** dialog, choose **XY**. Choose entry of error values calculated elsewhere, then the **Mean and SD** format without N. Use numeric X values and no X error subcolumn. See [precalculated error entry](https://www.graphpad.com/guides/prism/11/user-guide/graphing_errorbars_calclated_e.htm) if reformatting an existing table.
2. Create the table. Enter concentrations in **X**, and each compound's summaries into its **Mean** and **SD** subcolumns. Do not put concentrations in row titles: those are labels, not numeric X coordinates.

3. For example, enter this **illustrative input**, replacing it with the supplied summaries. Here the response is percent of an induced control; use that label only if it matches the actual upstream normalization.

   | X: concentration (µM) | A: Compound A Mean | A: SD | B: Compound B Mean | B: SD |
   |---:|---:|---:|---:|---:|
   | 1 | 92 | 5 | 98 | 4 |
   | 3 | 75 | 7 | 90 | 6 |
   | 10 | 40 | 6 | 65 | 8 |

   The SD entry is a distance from the mean. For the illustrative A point at 10 µM, enter 40 and 6, not 34 and 46. If compounds have different concentrations, use the union of X values and leave the other data sets blank on unmatched rows; Prism has one shared X column per table.
4. Open the associated graph sheet. Use an XY symbol plot with SD error bars. Double-click a symbol to open **Format Graph**, select a data set, and configure its symbols, lines and error bars. Repeat for the other data sets and click **OK**. Use distinguishable symbols and a compound legend. Keep the displayed error type as **SD**. If error-bar choices are absent, check that the table actually has SD subcolumns.
5. Leave connecting lines off for a simple summary plot. If requested, enable point-to-point lines and identify them as visual connections; they are not fitted regression curves. Do not run Analyze merely to create this graph. Label X with concentration and units, and Y with the supplied response definition, for example “Response (% of induced control)”. State “mean ± SD” and the supplied biological-replicate information in the caption.

The [XY table guide](https://www.graphpad.com/guides/prism/11/user-guide/xy_table.htm) covers data placement; [Format Graph — XY](https://www.graphpad.com/guides/prism/11/user-guide/using_format_graph_xy.htm) covers appearance controls.

## Inspect and deliver

Check that every plotted mean and SD maps to the intended compound and concentration. Error bars should extend to mean minus SD and mean plus SD; inspect axis limits if they appear clipped. A missing point may reflect a blank cell or an excluded value (blue italics in the table). Resolve accidental omissions or exclusions before export. Do not alter valid summaries to make the plot look cleaner.

Use **File > Save** to retain the editable Prism project, choosing an output location and a descriptive name such as `assay-summary`. Saving preserves the table and graph; exporting creates a picture and does not preserve the underlying data for editing in Prism.

With the graph active, choose **File > Export** or the toolbar **Export** button, then choose the filename, location and format:

| Format | Use and settings |
|---|---|
| PDF or SVG | Vector output for scalable figures; no DPI setting |
| TIFF | Raster output when required; select the required resolution from 100, 300, 600 or 1200 DPI and set the final figure width |
| Color/background | Prefer RGB unless the recipient requires CMYK; choose a white or transparent background to suit the destination |

Export size refers to the whole graph object, including legends, not just the plotting area. Open the exported image to check labels, legend, error bars and clipping. Deliver both the editable project and exported figure, with the concentration units, response normalization and error-bar definition stated. This graph displays supplied summaries; it supplies no fitted potency estimate or significance result.

For destination-specific requirements, consult [export options](https://www.graphpad.com/guides/prism/11/user-guide/exporting_options.htm).
