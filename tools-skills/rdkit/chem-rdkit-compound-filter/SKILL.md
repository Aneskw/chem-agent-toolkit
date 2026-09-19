---
name: chem-rdkit-compound-filter
description: >-
  Filter candidate compounds using RDKit structural alerts and active-reference similarity. Invoke for: removing invalid SMILES, PAINS/Brenk hits, and compounds whose Morgan-fingerprint Tanimoto similarity is at or above a specified threshold; do not use for toxicity conclusions or experimental safety approval.
license: MIT
compatibility: Python 3.10+ with RDKit; local hits and active-reference CSV files required; no network or model weights
allowed-tools: Bash, Read, Write, Glob
---

# RDKit compound filtering

Use the packaged script when a task requires the conjunction of structural-alert filtering and novelty filtering against known active compounds. The script is deterministic and preserves the input order of retained candidates. Do not use this skill to infer toxicity, synthesize a route, or predict experimental outcomes.

## Credibility

**High confidence (Enforce strictly)** for deterministic application of the stated RDKit rules and output ordering: the packaged positive, negative, threshold, and CLI examples pass local tests. RDKit supplies the PAINS and Brenk catalogs, Morgan fingerprints, and Tanimoto similarity. **Low confidence (Highly flexible)** for biological interpretation: these are computational triage rules, and a retained molecule is not proven safe, synthesizable, inactive, or experimentally novel.

## Reference

Read `references/science.md` when interpreting structural alerts or changing fingerprint parameters. Use the RDKit version in the run record; the packaged examples are computational checks, not experimental measurements.

## Input & Output

The hits CSV must contain a `SMILES` column. The training CSV must contain `SMILES` and normally an `ACTIVITY` column. Numeric activity values greater than zero and common truthy labels are treated as active; use `--all-train-active` only when every training row is already an active reference set.

The output is a UTF-8 text file containing one retained SMILES per line. Standard output is a JSON summary with row counts, rejection reasons, threshold, fingerprint radius, and bit length.

With the benchmark filenames (`hits.csv` and `train.csv`), the script can be run without arguments and writes `pred_results/compound_filter_results.txt`.

## Procedure Guidance

```bash
python tools-skills/rdkit/chem-rdkit-compound-filter/scripts/filter_compounds.py \
  --hits hits.csv --train train.csv \
  --output pred_results/compound_filter_results.txt \
  --similarity-threshold 0.5 --radius 2 --fp-size 2048
```

Accept a candidate only when all of the following hold:

1. RDKit parses its SMILES.
2. Neither the PAINS nor Brenk catalog reports a match.
3. Its maximum Tanimoto similarity to every active reference is strictly less than the threshold.

Do not round similarities before applying the threshold. A value equal to `0.5` is rejected when the requirement is “less than 0.5.”

## Matters & Troubleshooting

Reject missing columns, an empty active reference set, invalid thresholds, and unreadable files with a nonzero exit code. Invalid candidate SMILES are counted and excluded. Invalid active-reference SMILES are counted; fail if none of the active references remain valid. Never replace missing activity labels with invented labels.
