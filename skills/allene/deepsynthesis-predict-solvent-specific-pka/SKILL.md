---
name: deepsynthesis-predict-solvent-specific-pka
description: Obtain solvent-specific molecular pKa estimates with DeepSynthesis when screening acidity in DMSO, water, acetonitrile, methanol or aqueous ethanol. Use for predictions, not measured or site-resolved acidities.
---

# Predict molecular acidity by solvent

## Service and inputs

Use the Luo Group's [Deep Synthesis entrypoint](https://luoszgroup.com/index.php/deep-synthesis/) and its [pKa predictor](http://isyn.luoszgroup.com/prediction). This Skill targets the unversioned hosted XGBoost interface inspected on 2026-11-11. It requires an interactive browser with JavaScript and network access; no local model installation is needed. Record the access date because the service does not expose an immutable model release.

The [About page](http://isyn.luoszgroup.com/about) states that free use is for nonprofit academic purposes. Follow its citation terms when publishing results; the prediction page links the [model paper](https://doi.org/10.1002/anie.202008528).

Prepare the molecular structure with its intended charges and protonation state, and identify the solvent required for the question. The result is a molecular pKa estimate on that solvent's scale. This interface does not establish which proton a prediction describes in a molecule with several possible acidic sites.

## Enter a structure and retrieve predictions

1. Open the predictor. It automatically requests a benzoic-acid example on page load; do not mistake that initial table for a result for your molecule.
2. Draw your molecule in **Ketcher** or **JSME**, then click **Analysis**. The page specifically directs protonated molecules to JSME. Preserve the intended charge rather than neutralizing the structure just to enter it.
3. Wait for the request to complete and the solvent table to update. Check the displayed structure and **Identification** fields, including SMILES, against the intended molecule before copying results.
4. Read the row for the required solvent and retain its displayed model label and value. Save the submitted structure/SMILES, solvent, model, pKa, service URL and access date in the task's result file. This is your output record; the workflow does not promise a downloaded file.

For a concrete example, predict neutral benzoic acid, `O=C(O)c1ccccc1`, in DMSO. This page invocation supplies the same example SMILES and automatically starts analysis when opened in a browser:

```text
http://isyn.luoszgroup.com/prediction?smiles=O=C(O)c1ccccc1
```

Confirm the displayed molecule is benzoic acid and extract the **DMSO** row. For other structures, use the editor workflow above.

## Interpret the table

Use the page's solvent names and recommended prediction ranges:

| Row | Solvent | Recommended pKa range |
| --- | --- | --- |
| H2O | Water | -2 to 16 |
| DMSO | Dimethyl sulfoxide | 5 to 35 |
| EtOH_50% | Ethanol:water = 50:50 | 0 to 20 |
| AN | Acetonitrile | 5 to 30 |
| MeOH | Methanol | 0 to 18 |

Keep comparisons on the same solvent scale. The site warns that values outside solvent leveling ranges were excluded from training and can yield unreliable predictions. Flag estimates outside the recommended ranges. Two displayed decimal places are formatting, not an uncertainty estimate. These predictions do not establish experimental acidity, site-specific gamma acidity, reaction feasibility or catalyst-induced acidity changes.

**Failure handling:** `smiles cannot be empty` means the editor provided no structure. A prediction-error alert, an absent requested solvent row or a table left over from a failed request is not a usable prediction. Correct an empty structure and resubmit; if the request still fails, report the failure without supplying a pKa. Molecular identification is fetched separately from predictions, so an identification failure does not prove prediction failure, and successful identification alone does not prove a completed prediction.
