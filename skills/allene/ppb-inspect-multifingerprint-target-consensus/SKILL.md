---
name: ppb-inspect-multifingerprint-target-consensus
description: Use original Polypharmacology Browser to compare target predictions across fingerprint spaces and inspect supporting ligands for a verified molecular structure, when its fixed ChEMBL 21 coverage is suitable.
---

# Inspect target consensus with original PPB

## Access and inputs

Open the University of Bern [tools directory](https://gdb.unibe.ch/tools/), choose **PPB**, then **Browser** ([direct interface](https://webtools.gdb.tools/PPB/browser.html)). Use a web browser with JavaScript enabled and access to result windows and downloads. This workflow uses original hosted PPB and its **ChEMBL Database Version 21** snapshot. Choose another workflow if current database coverage is required; PPB3/PPB4 are separate services.

Start with a verified query structure supplied as SMILES or drawn in the embedded JSME sketcher. Check the rendered structure against the intended input before submission.

| Control | Normal path |
| --- | --- |
| No. of targets | Keep **20**, the page default; use an integer from **1 to 50** when changing it. Retrieval is performed per fingerprint space before merging, so this is not a cap on the merged table. |
| Fingerprints | Retain all ten preselected spaces below for consensus inspection. |

Single spaces: **APfp, Xfp, MQN, SMIfp, Sfp, ECfp4**.

| Combined space | Components |
| --- | --- |
| Ffp1 | Xfp + SMIfp + Sfp |
| Ffp2 | Xfp + MQN + SMIfp |
| Ffp3 | Xfp + SMIfp + Sfp + ECfp4 |
| Ffp4 | Xfp + MQN + SMIfp + Sfp + ECfp4 |

Older help calls these combinations Hyp1-Hyp4.

## Submit and inspect

For a concrete example, use the official tutorial's Metaraminol SMILES:

```text
CC(N)C(O)c1cccc(O)c1
```

1. Right-click inside JSME and use its SMILES paste option. Substitute the supplied query for ordinary use.
2. Keep 20 targets and all ten spaces. Click the green **Submit** button once. Submit only one job at a time; wait for the result window.
3. Read cross-space agreement before comparing p-values: targets are ordered by occurrence across spaces, then summed p-values.
4. Select a target row to see its full name; **Link To ChEMBL** opens its database details.
5. Click its **No. of Molecules** value to inspect retrieved known ligands. Entries show the retrieving fingerprint, city block distance and linked ChEMBL compound ID.
6. Use each window's save control: export the target table and, separately, molecule tables for selected targets. Keep the query, target-count setting and fingerprint labels with the downloads.

The [illustrated tutorial](https://webtools.gdb.tools/PPB/SimpleExample01.html) shows these controls and windows.

## Interpret results and failures

PPB assigns targets through similarity to known active ligands. Its p-value derives from the closest ligand's distance against a target-specific random-distance distribution; it is not a measured affinity or a calibrated probability of binding. Smaller values indicate more unusual similarity under that model. See [General Information, B2](https://webtools.gdb.tools/PPB/basics.html) for the calculation.

| Display | Meaning |
| --- | --- |
| Green bar | Scale runs from p = 0.01 toward 0; full green at 0. Values above 0.01 have an empty bar and a numeric value. |
| Grey | Target was not retrieved in that fingerprint space. |
| Red | Query matches a known target ligand. |

Compare ligand distances within their fingerprint space; retain the fingerprint labels. Agreement supports prioritization for follow-up, without establishing experimental activity. An absent target reflects the selected retrieval depth and fixed database coverage; it does not establish inactivity.

For target-count alerts, enter a value in the supported range. For an unreadable/empty molecule alert, inspect and re-enter the structure. If the sketcher or results fail to load, check JavaScript and result-window access; use the provider's [troubleshooting page](https://webtools.gdb.tools/PPB/problem.html). Do not interpret a stalled or failed job as an empty biological result.
