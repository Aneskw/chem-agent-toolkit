---
name: chem-uspto50k-split
description: "Check local train/valid/test reaction CSV files for required fields, empty values and exact-text cross-split overlap; not a chemical-identity leakage audit."
license: Dataset terms vary by source
---


# Check local reaction splits

Requires Python 3.10+; no third-party packages. Supply a local directory with `train.csv`, `valid.csv` and `test.csv`, each containing a `reaction_smiles` column. This package does not supply a dataset or establish a canonical USPTO-50K split.

```bash
python <skill-dir>/scripts/validate_split.py --root ./reaction-splits
```

Read stdout JSON: `splits` gives row, empty-value and within-split duplicate counts; `overlap_rows` gives shared unique strings across each split pair. Exit **0** / `ok:true` requires all files/columns, nonempty splits, no empty reaction values and no cross-split overlap. Exit **2** reports defects or unreadable inputs. Within-split duplicates are reported rather than silently removed.

Comparison strips surrounding whitespace only. Alternative SMILES, mapping labels or component order can hide chemical duplicates; success does **not** establish molecular identity separation, correct atom mapping or absence of target leakage. Apply a separately declared normalization/grouping policy if those checks are needed.

Keep dataset origin, preprocessing revision and split convention with the evaluation. [Resource provenance guidance](resources/RESTORE.md) explains the required records; user-supplied files remain the inputs.
