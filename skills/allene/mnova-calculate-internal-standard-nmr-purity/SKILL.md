---
name: mnova-calculate-internal-standard-nmr-purity
description: Calculate compound purity in Mnova from quantitative proton NMR with a weighed internal standard; use when spectrum quality, sample masses and signal assignments are available.
---

# Internal-standard purity with Mnova

## Setup and inputs

Use **Mnova 17.0.1 build 41952** with an activated **NMR module**. Obtain the platform installer and license/trial through the [official Mnova page](https://mestrelab.com/main-product/mnova). The **Purity Calculator** script requires no separate qNMR-plugin license.

Start with a quantitative 1H spectrum containing both analyte and internal standard. It must have sufficient relaxation between pulses, good shimming, correct phase and a corrected baseline. Acquisition is a supplied prerequisite; this calculator cannot establish full relaxation from an integral.

Have these details ready:

| Input | Meaning |
| --- | --- |
| Sample Mol Weight | Molecular mass of the analyte form being quantified |
| Weight of Sample (mg) | Total weighed sample mass, including its impurities |
| Reference Compound Mol Weight | Molecular mass of the internal standard |
| Reference Compound Purity (%) | Certified standard purity, entered as percent |
| Weight of Reference Compound (mg) | Weighed internal-standard mass present with the sample |
| Integral regions and Nuclide Count | Assigned reference and analyte signals; for 1H, the number of protons represented by each whole region |

Use an already processed spectrum in Mnova, or open its supported dataset through **File > Open**. Opening an FID can automatically process it; inspect phase and baseline before quantifying. Choose resolvable assigned regions rather than solvent, overlapping impurities or problematic broad OH signals. If the analyte form or salt stoichiometry is unresolved, establish that before entering its molecular mass.

## Run the calculator

The following illustrates the manual's worked spectrum. Its masses and regions are example inputs, not settings to transfer to another compound.

1. Make the sample spectrum active and choose **Tools > NMR Tools > Purity Calculator**.
2. Fill the sample and reference details. In the manual example: sample molecular mass **410.471**, sample mass **4.865 mg**; reference named **DMP**, molecular mass **96.13**, purity **98.6%**, mass **1.163 mg**. Select the appropriate reference entry or supply its details; verify them against the actual standard.
3. Click **OK**. Integrate the reference signal and click **Continue**. The worked example uses **5.49-5.95 ppm**, representing **1 proton**.
4. Integrate the analyte multiplets, then click **Continue** again. The example uses **7.58-7.68**, **8.61-8.69** and **8.50-8.59 ppm**, each representing **1 proton**. Substitute assigned regions and proton counts from the actual sample.
5. In the review dialog, check masses, the reference integral and **Nuclide Count** for every region. Inspect the purity estimate beside each analyte integral. Use the checkboxes to include the intended regions; correct assignments or integration problems rather than selecting regions merely to obtain a preferred purity.
6. After edits, use **Re-Calculate**. Check **Add report on new page**, then click **OK**. Save the document through the File ribbon; export a PDF there if a shareable report is needed.

## Read and retain the result

The report contains **Average Purity** in percent, the assumed sample mass and molecular mass, standard details, and each selected region's integral, proton count and purity estimate. Retain this report with the spectrum so the calculation remains inspectable.

Individual multiplet estimates should be similar. Disagreement calls for review of integration bounds, baseline/phase, overlap, proton counts and entered masses; the manual supplies no universal numerical agreement threshold. A reported average alone does not validate those inputs or prove compound identity. If no suitable assigned signal is available, the spectrum does not support this calculation as entered.

For another sample with the same analyte, standard and applicable integration setup, **Use Parameters From Previous Calculation** can reuse the settings. Update the masses and verify that the reused regions still fit the new spectrum.

Consult the [Mnova 17 Purity Calculator instructions](https://mestrelab.com/downloads/mnova/manuals/latest/advanced-plugins-qnmr.html#purity-calculator-script) for the dialog walkthrough, or the [1D guide](https://mestrelab.com/downloads/mnova/manuals/latest/fast-visual-guide-to-process-routine-1.html) for opening and saving spectra.
