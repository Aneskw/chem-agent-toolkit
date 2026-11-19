---
name: sea-query-target-hypotheses
description: Use the hosted Similarity Ensemble Approach (SEA) service to obtain target hypotheses from up to ten curated SMILES records and download completed search results.
---

# Query SEA for target hypotheses

## Service and inputs

Open the official [SEA service](https://sea.bkslab.org/) in a JavaScript-enabled browser. This workflow targets the hosted **ChEMBL 36** interface inspected on November 11, 2026. Check the displayed library version before use; record any change rather than treating different databases as interchangeable. The normal search form uses fingerprint `ecfp4` and **all reference targets**. No local SEA installation is needed; complete the site's CAPTCHA verification when requested.

The site is public and explicitly makes no confidentiality guarantee. Use inputs suitable for submission to that service; its displayed secure-use contact is `support+sea*bkslab*org`.

Prepare 1–10 nonempty records, one per line:

```text
<SMILES> <compound_id>
```

Use curated SMILES, including intended stereochemistry, and stable IDs without commas, spaces or tabs. Separate SMILES and ID with a single space. IDs are labels, not a chemical-name lookup. For an unnamed SMILES line the client adds `compound_<line_number>`; explicit IDs make later mapping easier. The form checks presence and record count, so passing those checks does not establish chemical validity.

## Submit a representative search

1. Paste your records into **Run SEA**. For example, these two structures appear among the site's examples; the IDs below are illustrative:

   ```text
   NCCc1c[nH]c2ccc(O)cc12 serotonin
   NCCc1ccc(O)c(O)c1 dopamine
   ```

2. Use the normal form's `ecfp4` fingerprint and all-target reference scope. This path needs no target-ID list. Record these settings with the input. The inspected client contains advanced-option code but hides its menu; do not depend on opening it to run this search.
3. Complete verification if shown, then click **Submit**. Successful submission opens a result URL of the form `https://sea.bkslab.org/result?taskId=<returned-task-id>`. Save that URL and task ID. A form or network error without a returned task is a submission failure.
4. Allow the result page to update until the SEA task completes. It can expose partial rows while running; wait for completion before reporting the final table. For nonempty results, compare **Input Compounds** IDs, SMILES and structures with your submitted records.
5. Click **Download Results (ZIP)** on the completed, nonempty result page. Save the ZIP locally, inspect its actual members, and use their supplied headers when extracting results; this workflow does not assume an archive filename or internal schema. Record the saved path alongside the task URL, submitted text, library version, fingerprint, reference scope and submission date.

Single-molecule submissions may automatically queue Boltz2 structure predictions for the top five novel targets with Tc below 1, according to the current page. SEA task completion is separate from those jobs. This workflow uses the SEA table and **Download Results (ZIP)**; interpreting affinity or structure-prediction outputs requires a separate workflow.

## Inspect and interpret results

The result table exposes these fields when present:

| Fields | Use |
| --- | --- |
| `Target_Chembl_ID`, `Target_Name` | Identify each target hypothesis. Click the ChEMBL ID to inspect its known-ligand similarity detail. |
| `Uniprot_ID`, `Uniprot_Accession` | Preserve available protein identifiers when reporting or joining results. |
| `Z_score`, `p_value`, `MaxTc` | Retain the service's reported scores with each target. The headers are sortable; a new column selection initially sorts descending, so click again if you want ascending p-values. |

Target detail shows known-hit IDs, SMILES and **Tanimoto Score**, with a query-compound filter. For a multi-compound task, inspect this detail or **Compound VS Targets** before attributing a target to an individual input. Keep the query ID attached to any compound-specific observation.

SEA relates proteins through set-wise chemical similarity among their ligands. Treat the output as hypotheses for follow-up: the displayed p-value is not a probability of binding, and similarity is not an affinity measurement. Do not invent acceptance thresholds or convert the reported scores to binding constants. Preserve the scores and inspect supporting ligands when selecting hypotheses. The service requests citation of [Keiser et al., Relating protein pharmacology by ligand chemistry (2007)](https://doi.org/10.1038/nbt1284) when publishing SEA results.

Distinguish these outcomes:

- **Complete with rows:** report target hypotheses and archive the ZIP.
- **Complete / SUCCESS with “No results found for this task.”:** report a successful search with no returned hits for the recorded inputs and settings. The ZIP link is rendered only when there are rows. Save the task URL and empty-result message; absence of hits does not establish absence of biological activity.
- **Task Failed / ERROR:** retain the displayed error; do not interpret it as a negative prediction.
- **Results No Longer Available / EXPIRED:** the page states that results are removed after **96 hours**. Retrieve a previously saved archive or resubmit the original inputs and settings, recording the new task and date.
- **Still running or status cannot be retrieved:** report an incomplete or inaccessible task, rather than an empty prediction. If submission fails, correct the reported input or verification issue before retrying.
