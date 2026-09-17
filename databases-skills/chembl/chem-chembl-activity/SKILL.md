---
name: chem-chembl-activity
description: >-
  Invoke for: retrieving public ChEMBL bioactivity annotations by molecule or target identifier, with assay IDs and source URL preserved. Do not treat database annotations as experimental confirmation.
license: Apache-2.0
allowed-tools: Bash(python3:*)
---

# ChEMBL activity query

Query public ChEMBL activity records by a ChEMBL molecule or target identifier. Keep the retrieval URL, limit, and activity IDs; do not merge heterogeneous assays into one endpoint.

## Reference

API: https://www.ebi.ac.uk/chembl/api/data/docs

The script uses the ChEMBL REST endpoint `/activity.json` with `molecule_chembl_id` or `target_chembl_id`. Results depend on the current public database and should be cached with retrieval time.

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
