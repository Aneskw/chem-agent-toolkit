---
name: swissadme-screen-druglikeness
description: Submit checked small-molecule SMILES to SwissADME and export descriptors, pharmacokinetic predictions, drug-likeness rules and PAINS alerts for early compound screening.
---

# Screen named molecules with SwissADME

## Access and prepare

Open the official [SwissADME service](https://www.swissadme.ch/) in a browser with download access. This workflow targets the live service inspected on 2026-11-11; the public interface exposes no immutable server/model release. Save the access date with each result set. Use direct SMILES entry; the site reports removal of ChemAxon dependence, while older sketcher instructions remain in Help.

Start with checked SMILES for individual small molecules and stable compound identifiers. Models primarily cover druglike organic compounds; macromolecular predictions may be irrelevant. Prefer the appropriate neutral form, retaining permanent ions or zwitterions where chemically required. SwissADME does not consistently neutralize inputs. Preserve the original structures separately and document any intentional change of microspecies.

Prepare plain text with **one SMILES, a space, and an optional name per line**. Use unique names to preserve identity. Separate molecules by newlines: dot-disconnected fragments on one line are treated as one entry. Follow the [official FAQ](https://www.swissadme.ch/faq.php): at most 200 entries per batch, one batch at a time, and no more than 10,000 molecules total. These operational limits take precedence over Help's statement of no technical limit.

## Submit and export

The following illustrative two-compound input can be replaced with the user's checked structures:

```text
CC(=O)Oc1ccccc1C(=O)O aspirin
CC(=O)Nc1ccc(O)cc1 acetaminophen
```

1. Paste the text into **Enter a list of SMILES here**. Retain a local copy of the exact submitted list.
2. Click **Run**, which activates when the list is nonempty.
3. Wait for every molecule's panel to fill and its processing wheel to disappear. Results populate sequentially on the same page.
4. Check each panel's name, rendered structure and returned canonical SMILES against the intended compound. Canonicalization can change SMILES text; assess chemical identity rather than string equality.
5. After completion, click the **red CSV icon below the SMILES list**. Save the download, for example as `swissadme-screen.csv`, and inspect it in a text or spreadsheet application. The adjacent clipboard icon is an alternative export.
6. Match exported entries to input names and structures; resolve missing or mismatched entries before comparing compounds. Keep the unmodified CSV with the submitted list and access date.

The [official Help](https://www.swissadme.ch/help.php) describes the controls and per-molecule panels. Hover over red question marks for field-specific definitions and references. If browser operation is unavailable, hand the prepared list and these steps to a browser operator and request the exported CSV and structure checks.

## Read the results

Keep the tool's field names, model names and displayed units when making a comparison table:

| Panel | Results to retain |
| --- | --- |
| Physicochemical Properties | Molecular weight, TPSA, rotatable-bond and H-bond donor/acceptor counts |
| Lipophilicity | Each selected log P estimate with its predictor label; do not silently merge different models |
| Pharmacokinetics | GI absorption, BBB permeation, P-gp substrate and CYP inhibition predictions; skin permeability if relevant |
| Druglikeness | Lipinski, Veber and Egan outcomes plus the reported violations |
| Medicinal Chemistry | PAINS alert count and reported fragments |

Log P describes neutral-form octanol/water partitioning; SwissADME does not supply log D or pKa. Use reported rule violations rather than reconstructing Lipinski from descriptor counts: its `NorO` and `NHorOH` definitions differ from the displayed H-bond counts. PAINS flags assay-interference-associated fragments; zero alerts does not prove absence of interference.

Use predictions and rule outcomes to prioritize further work. Passing filters does not establish experimental pharmacokinetics, efficacy or toxicity.

## Incomplete or failed results

A broken structure image indicates failed SMILES interpretation: discard that panel's values even if populated, correct the structure, and rerun after the active batch ends. An active wheel or absent panel is incomplete processing, not a negative prediction. Recover missing results before treating the export as complete.
