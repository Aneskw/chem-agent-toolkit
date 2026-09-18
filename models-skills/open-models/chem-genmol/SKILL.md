---
name: chem-genmol
description: >-
  Invoke for: preparing or preflighting GenMol SAFE-fragment generation tasks such as de novo design, linker design, motif extension, scaffold decoration, and lead optimization. Do not fabricate molecules when the checkpoint is unavailable.
license: Upstream license applies
allowed-tools: Bash(python3:*)
---

# GenMol molecule generation

Use the pinned GenMol checkout, model checkpoint, SAFE input, seed, and requested sample count. The packaged script checks resources only; it does not substitute another generator.

## Reference

Repository: https://github.com/NVIDIA-BioNeMo/genmol

GenMol uses masked discrete diffusion over SAFE molecular sequences. Record the GenMol revision, checkpoint path, SAFE input, seed, and requested generation count.

## Input and output

The script emits machine-readable JSON. If `ok: false`, do not treat partial fields as a successful scientific result; database and model outputs are not experimental validation.

## Procedure

1. Read `references/api.md` for the interface, version, and input constraints.
2. Run the packaged script or upstream CLI and preserve stdout, stderr, and exit code.
3. Compare fields with `examples/`; mark missing dependencies, data, weights, or endpoints as `blocked_resources`.

## Fixed cases

Use [examples/cases.json](examples/cases.json) for the fixed positive requests, negative requests, and expected checks. A valid SAFE request is not a successful generation result: when the pinned checkout or checkpoint is missing, the expected answer is `blocked_resources` with no fabricated molecule strings.

## Failure and recovery

- Correct incomplete or malformed input while retaining the original request.
- Report missing dependencies, network access, weights, or data explicitly; never fabricate output.
- Stop repeated retries when the same error recurs.
