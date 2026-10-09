---
name: chem-uspto50k-split
description: >-
  Invoke for: validating local USPTO-50K-style train, validation, and test reaction splits before retrosynthesis training or evaluation. Do not download or redistribute the dataset.
license: Dataset terms vary by source
compatibility: Python 3.10+; licensed local USPTO-50K-style split with train.csv, valid.csv, and test.csv
allowed-tools: Bash(python3:*)
---

# USPTO-50K split validation

Validate local `train.csv`, `valid.csv`, and `test.csv` files for required reaction columns, empty rows, and cross-split overlap. Record the source, preprocessing commit, atom-mapping policy, and split convention.

## Credibility

**medium confidence (Need verification)**. The validator is executable for local files, but dataset identity, preprocessing, licensing, and scientific suitability must be verified from the run manifest.

## Reference

Project evidence identifies `USPTO50K` as a dataset option with train/valid/test files and model-specific preprocessing. Before using the validator, follow [`resources/RESTORE.md`](resources/RESTORE.md) and keep the exact source URL, archive hash, preprocessing commit, split convention, license, and atom-mapping policy in the run record. This repository does not redistribute a canonical USPTO-50K archive.

## Input & Output

The script emits machine-readable JSON. If `ok: false`, do not treat partial fields as a successful scientific result; database and model outputs are not experimental validation.

## Procedure Guidance

1. Read `references/api.md` for the interface, version, and input constraints.
2. Read `resources/RESTORE.md` and verify provenance before touching the data.
3. Run the packaged script or upstream CLI and preserve stdout, stderr, and exit code.
4. Compare fields with `examples/`; mark missing dependencies, data, weights, or endpoints as `blocked_resources`.

## Matters & Troubleshooting

- Correct incomplete or malformed input while retaining the original request.
- Report missing dependencies, network access, weights, or data explicitly; never fabricate output.
- Stop repeated retries when the same error recurs.
