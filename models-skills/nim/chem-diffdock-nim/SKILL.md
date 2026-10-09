---
name: chem-diffdock-nim
description: >-
  Invoke for: preparing or preflighting a DiffDock protein-ligand docking request through a configured NVIDIA NIM endpoint. Do not interpret a pose as binding affinity or experimental validation.
license: Upstream license applies
compatibility: Python 3.10+; receptor and ligand files; authenticated NVIDIA NIM DiffDock endpoint
allowed-tools: Bash(python3:*)
---

# DiffDock NIM docking

Check receptor and ligand files and the configured NIM endpoint before submission. Record endpoint, model version, seed, input representations, and output pose files.

## Credibility

**medium confidence (Need verification)**. The packaged check verifies request readiness only; it does not execute docking or validate binding experimentally.

## Reference

Reference implementation: https://github.com/gcorso/DiffDock
NVIDIA BioNeMo skill format reference: https://github.com/NVIDIA-BioNeMo/bionemo-agent-toolkit/tree/main/nim-skills/diffdock-nim

Read [`resources/RESTORE.md`](resources/RESTORE.md) before running. Record receptor path, ligand representation, endpoint URL, model/version, seed, input hashes, and output pose files. The Skill does not include local weights; the NIM deployment owns them.

## Input & Output

The script emits machine-readable JSON. If `ok: false`, do not treat partial fields as a successful scientific result; database and model outputs are not experimental validation.

## Procedure Guidance

1. Read `references/api.md` and `resources/RESTORE.md` for the interface, version, and resource contract.
2. Run the packaged preflight and preserve stdout, stderr, and exit code.
3. Submit only through the configured endpoint after preflight passes; preserve the raw response and pose files.
4. Compare fields with `examples/`; mark missing dependencies, data, weights, or endpoints as `blocked_resources`.

## Matters & Troubleshooting

- Correct incomplete or malformed input while retaining the original request.
- Report missing dependencies, network access, weights, or data explicitly; never fabricate output.
- Stop repeated retries when the same error recurs.
