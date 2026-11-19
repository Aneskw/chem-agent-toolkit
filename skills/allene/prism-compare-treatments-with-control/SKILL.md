---
name: prism-compare-treatments-with-control
description: Use GraphPad Prism to compare independent treatment groups with a predefined control using ordinary one-way ANOVA and Dunnett multiple comparisons for one endpoint.
---

# Treatment versus control comparisons in GraphPad Prism

## Prepare Prism and inputs

Use **GraphPad Prism 11.1.0 for Windows or Mac**. Obtain the official installer from [Prism Updates](https://www.graphpad.com/updates) ([Windows](https://cdn.graphpad.com/downloads/prism/11/InstallPrism11.msi), [Mac](https://cdn.graphpad.com/downloads/prism/11/InstallPrism11.dmg)); use a valid license or the [official trial](https://www.graphpad.com/free-trial). Confirm the installed version: these major-version download links can advance to later patches. This is a desktop GUI workflow.

Required inputs are individual replicate measurements for one endpoint, group labels, a predefined control, and the planned confidence/significance level. Use this path for three or more independent groups defined by one factor, with Gaussian sampling and equal population variances justified. Matched subjects, repeated measurements and factorial designs require another configuration. If unequal variances are appropriate, use a separately configured analysis; ordinary Dunnett and Dunnett T3 are distinct procedures.

From **Welcome** or **New Table & Graph**, choose **Column**, then **Enter replicate values stacked into columns**. Put one group's measurements in each column and its label in the column title. Unequal sample sizes are allowed; leave unused cells blank. Rows do not denote matched subjects in this workflow. Do not enter means or SEMs as replicates.

For example, paste the following tab-separated illustrative measurements (latency in seconds), starting in the first data cell, and set column titles to `Control`, `Treatment A`, and `Treatment B`. These are example inputs, not publication data.

```text
12.1	10.4	8.5
11.3	11.1	9.4
13.0	9.8	8.9
12.5	10.7	9.8
11.8	10.2	9.1
```

## Run ordinary ANOVA with Dunnett comparisons

With the data table active, click **Analyze** and choose **One-way ANOVA** under **Column analyses**. Include the intended control and treatment columns in the analysis.

Set the parameters explicitly:

| Tab | Setting |
| --- | --- |
| Experimental Design | **No matching**, **Normal (Gaussian)**, and **assume equal variances/SDs**. This selects ordinary one-way ANOVA. |
| Multiple Comparisons | **Compare the mean of each column with the mean of a control column**; designate `Control` as the control column for this example. Choose the comparisons from the experimental plan. |
| Options | **Correct for multiple comparisons using statistical hypothesis testing**, then **Dunnett's**. |
| Options | Enable **Report multiplicity adjusted P value for each comparison**. Set confidence/significance levels to the planned values; this example uses **95% confidence / alpha 0.05**. |

Accept the dialog to calculate results. The example requests Treatment A versus Control and Treatment B versus Control, not Treatment A versus Treatment B. If Dunnett's is unavailable, recheck the control-comparison selection and equal-variance setting; do not substitute Dunnett T3 merely because its name is similar.

For exact dialog terminology, consult the Prism 11 [design](https://www.graphpad.com/guides/prism/11/statistics/stat_choosing_test_one-way_anova.htm), [comparison](https://www.graphpad.com/guides/prism/11/statistics/stat_how_to_multiple_comparisons_af.htm), and [options](https://www.graphpad.com/guides/prism/11/statistics/stat_options_tab_1wayanova.htm) guides.

## Read and retain results

Open the analysis results. Record the ordinary ANOVA **F statistic, degrees of freedom and overall P value**. That P value tests equality of all population means; it does not identify which treatment differs from control. Keep the equal-variance test P values separate from the ANOVA P value. Evidence of unequal variances calls for reconsidering the configuration, rather than interpreting ordinary ANOVA uncritically.

Click **Multiple Comparisons** at the top of the results sheet; it is a separate tab from the main ANOVA results. For each planned treatment-control comparison, retain:

- The group names and sample sizes.
- The mean difference, its direction and the multiplicity-adjusted confidence interval, in the endpoint's original units.
- The multiplicity-adjusted P value and the comparison decision at the selected alpha.

Read the displayed subtraction order before interpreting the sign. **Swap direction of comparisons** in Options reverses the reported difference signs. If long titles become `Column A`, `Column B`, etc., map them back to the original column titles.

Use adjusted P values for the planned comparison family. At alpha 0.05, a value below 0.05 supports a difference for that comparison; the confidence interval describes its magnitude and uncertainty. A nonsignificant comparison is a valid result and does not establish equal means. Prism reports very small Dunnett adjusted P values as **<0.0001**; retain that bound rather than replacing it with zero or an exact value. If comparison results are absent, first check the separate results tab, then verify that multiple comparisons were requested.

Save the **Prism project** to retain the data, analyses and graphs. Exporting a graph creates an image and does not preserve the underlying analysis. Deliver the saved project with a concise table of the planned comparisons, units, mean differences, adjusted intervals and adjusted P values, plus the ANOVA summary and settings. See [multiple-comparison results](https://www.graphpad.com/guides/prism/11/statistics/stat_multiple-comparison-results.htm) for result-tab details and [saving versus exporting](https://www.graphpad.com/guides/prism/11/user-guide/saving_vs__exporting.htm) for persistence.
