---
name: chem-openmm-md
description: >-
  Invoke for: checking an OpenMM molecular simulation environment and available platforms before energy minimization or molecular dynamics. Do not claim a trajectory or physical result from preflight alone.
license: MIT
allowed-tools: Bash(python3:*)
---

# OpenMM simulation preflight

Check the installed OpenMM version and requested platform. The packaged script is a preflight only; a real simulation requires a documented topology, force field, integrator, and output protocol.

## Reference

Upstream: https://github.com/openmm/openmm

OpenMM exposes platforms such as Reference, CPU, CUDA, and OpenCL depending on the installation. Record OpenMM version and the selected platform in any run report.

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
