---
name: pkcsm-predict-admet-properties
description: Obtain small-molecule ADMET predictions from pkCSM's graph-signature models, inspect model-specific values and units, and export batches of up to 100 molecules.
---

# Predict and export ADMET properties with pkCSM

## Access and prepare inputs

Open the hosted [pkCSM prediction page](https://biosig.lab.uq.edu.au/pkcsm/prediction) in a browser; no local installation is needed. Target: the unversioned pkCSM interface inspected on 2026-11-11. The homepage advertises Deep-PK separately: select pkCSM when graph-signature predictions are required. The inspected pages expose no immutable model version; record the service URL and actual submission date with saved results.

The [official homepage](https://biosig.lab.uq.edu.au/pkcsm/) states that academic studies do not require a license. For non-academic use, follow its **License (non-academic)** contact entry.

Start with checked canonical SMILES supplied by the user or their structure-preparation workflow. Structure generation and canonicalization are external preparation steps. Keep a local compound-ID-to-SMILES manifest for matching outputs.

| Input | Contract |
|---|---|
| One molecule | Paste one SMILES into **Provide a SMILES string**. |
| Batch | Upload a plain-text SMILES list with column headers, at most 100 molecules. Use one molecule per line; a single SMILES column avoids multi-column delimiter ambiguity. |
| Mode | **Absorption**, **Distribution**, **Metabolism**, **Excretion**, or **Toxicity** selects one class; **ADMET** runs all models. |

Syntax-noncompliant molecules are ignored. Page loading does not establish complete compound coverage.

## Run and export a batch

Save a plain-text file named `compounds.smi`. This minimal one-column example uses a descriptive header, the site's aspirin example and ethanol; replace the data lines with the checked structures of interest:

```text
SMILES
CC(=O)OC1=CC=CC=C1C(=O)O
CCO
```

1. Open the prediction page and select the file under **Upload your SMILES file**. Use either the upload or the single-string field for a submission.
2. Click **ADMET** for the complete panel, or the required class button.
3. Wait for the result table. Batch results have no molecule depictions. Match returned compound identities/SMILES and compound count against the manifest before comparing values. Do not match by row position: the table can be sorted or filtered.
4. Download the batch table using its CSV export control. Preserve the original download, submitted file, manifest, mode, URL and date. Inspect headers and delimiter before importing it; retain the returned model names and units.

For one molecule, leave the upload empty, paste `CC(=O)OC1=CC=CC=C1C(=O)O` into the single-string field and click **ADMET**. The result includes a molecular depiction and calculated descriptors beside the predictions. Check the depiction against the intended structure. The documented CSV download applies to batches; capture a single result's table directly if no export control is present.

## Interpret and handle incomplete results

The single-molecule prediction table reports **Property**, **Model Name**, **Predicted Value**, and **Unit**. Preserve the regression/classification distinction:

| Result type | Handling |
|---|---|
| Numeric regression | Keep the displayed scale and unit; logarithmic values are not linear concentrations or rates. |
| Categorical classification | Preserve the returned label and model identity; a label is not a probability or measured assay result. |
| Different models | Compare compounds within the same model and unit; do not combine heterogeneous endpoint values into an invented score. |

Examples from the [official Theory page](https://biosig.lab.uq.edu.au/pkcsm/theory): water solubility is log mol/L, human intestinal absorption is percent absorbed, VDss is log L/kg, and total clearance is log(mL/min/kg). CYP substrate and inhibitor predictions are separate endpoints. Consult that page for the particular model before applying thresholds or converting scales.

If compounds are absent, check canonical SMILES syntax and the 100-molecule limit, correct affected inputs and resubmit them. An empty or partial table is not a negative ADMET prediction. A mismatched single-molecule depiction requires correcting the input before using its values. If the service returns no result table, report the failure rather than filling values or silently substituting another predictor.

These predictions support screening and prioritization; they do not establish experimental pharmacokinetics, safety or clinical suitability. The [official Help](https://biosig.lab.uq.edu.au/pkcsm/help) describes submission and result handling.
