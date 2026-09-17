---
name: chem-uspto50k-split
description: >-
  Invoke for: validating local USPTO-50K-style train, validation, and test reaction splits before retrosynthesis training or evaluation. Do not download or redistribute the dataset.
license: Dataset terms vary by source
allowed-tools: Bash(python3:*)
---

# USPTO-50K split validation

Validate local `train.csv`, `valid.csv`, and `test.csv` files for required reaction columns, empty rows, and cross-split overlap. Record the source, preprocessing commit, atom-mapping policy, and split convention.

## Reference

Project evidence identifies `USPTO50K` as a dataset option with train/valid/test files and model-specific preprocessing. Keep the exact source, preprocessing commit, split convention, and any atom-mapping policy in the run record.

## Input and output

The script emits machine-readable JSON. If `ok: false`, do not treat partial fields as a successful scientific result; database and model outputs are not experimental validation.

## Procedure

1. Read `references/api.md` for the interface, version, and input constraints.
2. Run the packaged script or upstream CLI and preserve stdout, stderr, and exit code.
3. Compare fields with `examples/`; mark missing dependencies, data, weights, or endpoints as `blocked_resources`.

## Failure and recovery

- Correct incomplete or malformed input while retaining the original request.
- Report missing dependencies, network access, weights, or data explicitly; never fabricate output.
- Stop repeated retries when the same error recurs.
