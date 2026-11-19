---
name: swisstargetprediction-inspect-target-hypotheses
description: Use SwissTargetPrediction to submit a verified small-molecule structure for a selected organism, inspect ranked target hypotheses, and examine similar known active ligands.
---

# Inspect SwissTargetPrediction targets and supporting ligands

## Prepare

Use the [official hosted service](https://www.swisstargetprediction.ch/) in a JavaScript-enabled browser; no local installation is needed. This workflow targets the hosted interface inspected on November 11, 2026. It has no verified immutable build identifier, so retain the access date and results locally. The public service does not guarantee query confidentiality.

Start with one verified small-molecule structure and the intended organism. Supply SMILES, or draw/import the structure in the molecular sketcher. Preserve the intended stereochemistry and check the displayed structure before submission. The text box and sketcher synchronize.

| Input | Choices |
| --- | --- |
| Structure | One query molecule, preferably supplied as verified SMILES |
| Species | Homo sapiens (human, default), Mus musculus (mouse), Rattus norvegicus (rat) |

This is a similarity-based target prediction service for molecules assumed to be bioactive. It does not establish whether an untested molecule is bioactive.

## Submit and inspect

For a representative browser invocation, use the site's Coniine example SMILES `CCC[C@H]1CCCCN1` and select **Homo sapiens**. Substitute the user's verified structure and organism for actual work.

1. Open the home page, paste the SMILES into the input box, and inspect the synchronized drawing. Alternatively, use the sketcher to draw/import the molecule; see the [input guide](https://www.swisstargetprediction.ch/help.php).
2. Select the species explicitly, then click **Predict targets**. The interface advises that calculations can take up to one minute. Completion is the predicted-targets page with the query structure and ranked table; a submission message alone is not a result.
3. Confirm the returned query structure. Inspect the target table and retain its initial ranking before changing sorts. Column headers sort; the table also supports row-count changes, text search and pagination. Clear searches and inspect additional pages before treating a target as absent.
4. For each target of interest, follow the numbered **Known actives** links for the available 2D and/or 3D evidence. These numbers indicate how many supporting compounds will be displayed.


## Capture and interpret results

Save a local table or structured record connected to the query:

| Record | Retain |
| --- | --- |
| Run | Input SMILES/structure, compound label, species, access date, result URL |
| Target | Initial rank, target name, gene name, UniProt ID, ChEMBL target ID, target class, displayed probability |
| Support | Predicted target, 2D/3D link type and count, ligand ChEMBL ID, displayed similarity, actual assayed target when shown |

The target identifiers link to GeneCards, UniProt and ChEMBL. Copy identifiers as displayed, including multi-subunit targets; keep target IDs separate from supporting ligand IDs. Preserve the displayed probability without estimating a numeric value from bar length. Save the returned query drawing and relevant result pages alongside the records when useful.

The green bar represents the probability that a protein is a target **assuming the query molecule is bioactive**. It is neither an affinity nor a probability of overall bioactivity. A value of 1 often means the query is already a known active. The class pie chart defaults to **Top 15** targets; it can show other top-ranked subsets or all predictions. State the selected subset if reporting this chart. See the [results guide](https://www.swisstargetprediction.ch/help_results.php) for table controls.

The [Known Actives page](https://www.swisstargetprediction.ch/help_mol.php) shows experimentally active compounds driving a prediction, their clickable ChEMBL IDs and similarity values. The result links show highly similar actives above **0.65 for 2D** or **0.85 for 3D**; these are evidence-display thresholds, not query-activity cutoffs. Record which similarity measure each value belongs to. If a prediction uses homology, the page also names the actual protein on which the supporting ligand is active. Preserve that distinction when describing support.

Report ranked targets as hypotheses for follow-up, supported by identified similar ligands. An absent target, zero probability or missing supporting-link entry does not establish absence of activity. If the browser shows an input error, stays on a loading/submission state or never produces the target table, record the attempt as incomplete rather than as an empty biological result.
