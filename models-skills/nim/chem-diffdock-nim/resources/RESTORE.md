# DiffDock NIM resource restore contract

This package is a request preflight for a configured NVIDIA NIM endpoint. It
does not contain DiffDock weights and does not claim that a local machine can
run docking without an endpoint.

## Source and resource ownership

- Reference implementation: [DiffDock](https://github.com/gcorso/DiffDock)
- NIM skill reference: [NVIDIA BioNeMo DiffDock skill](https://github.com/NVIDIA-BioNeMo/bionemo-agent-toolkit/tree/main/nim-skills/diffdock-nim)
- Model weights: managed by the operator's NIM deployment; no checkpoint is
  bundled or downloaded by this repository.
- Required runtime resource: `DIFFDOCK_ENDPOINT` pointing to the configured
  authenticated service.

## Restore checklist

1. Obtain access to a licensed DiffDock/NIM deployment and record its model
   version, endpoint owner, and API contract.
2. Prepare an actual receptor structure and ligand file. Record their paths,
   formats, hashes, protonation/charge preparation, and any seed.
3. Export the endpoint for the preflight process:

```bash
export DIFFDOCK_ENDPOINT='https://<operator-endpoint>'
python3 scripts/preflight.py --receptor /path/receptor.pdb --ligand /path/ligand.sdf
```

4. Only after `ok: true` submit the request through the endpoint's documented
   client. Preserve the raw response and generated pose files.

If the endpoint, input files, authentication, or model version is missing,
return `blocked_resources`. Never invent pose coordinates, confidence scores,
binding affinities, or output filenames.
