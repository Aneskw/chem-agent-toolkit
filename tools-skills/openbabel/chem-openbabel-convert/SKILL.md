---
name: chem-openbabel-convert
description: >-
  Invoke for: deterministic conversion of molecular structure files between Open Babel formats such as SMILES, SDF, MOL2, PDB, XYZ, and MOL. Do not use it to repair structures or infer experimental meaning.
license: GPL-2.0-or-later
allowed-tools: Bash(obabel:*)
---

# Open Babel format conversion

Convert structure files with the local `obabel` executable. Preserve the original file, requested format flags, warnings, and output path because representation details can change during conversion.

## Reference

Upstream: https://github.com/openbabel/openbabel

The command-line interface is `obabel`; input and output formats are selected with `-i` and `-o`. Conversion can change representation details, so retain the original file and inspect warnings.

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
