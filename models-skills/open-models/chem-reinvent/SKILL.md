---
name: chem-reinvent
description: >-
  Invoke for: running or preflighting REINVENT4 configuration-driven molecular design tasks, including de novo generation, scaffold hopping, R-group replacement, linker design, and optimization. Do not claim generated molecules are synthesizable.
license: Apache-2.0
allowed-tools: Bash(reinvent:*)
---

# REINVENT4 molecular design

Use a pinned REINVENT4 checkout, TOML configuration, scoring components, seed, and output directory. The packaged script checks the CLI and configuration path; it does not download checkpoints.

## Reference

Repository: https://github.com/MolecularAI/REINVENT4

The upstream CLI is configuration-driven. Pin the repository revision, configuration file, scoring components, random seed, and output directory.

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
