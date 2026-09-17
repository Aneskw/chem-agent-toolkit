---
name: chem-diffdock-nim
description: >-
  Invoke for: preparing or preflighting a DiffDock protein-ligand docking request through a configured NVIDIA NIM endpoint. Do not interpret a pose as binding affinity or experimental validation.
license: Upstream license applies
allowed-tools: Bash(python3:*)
---

# DiffDock NIM docking

Check receptor and ligand files and the configured NIM endpoint before submission. Record endpoint, model version, seed, input representations, and output pose files.

## Reference

Reference implementation: https://github.com/gcorso/DiffDock
NVIDIA BioNeMo skill format reference: https://github.com/NVIDIA-BioNeMo/bionemo-agent-toolkit/tree/main/nim-skills/diffdock-nim

Record receptor path, ligand representation, endpoint URL, model/version, seed, and output pose files.

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
