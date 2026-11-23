---
name: rdkit-descriptor-delivery
description: Calculate RDKit molecular descriptors from SMILES, with JSONL output and explicit invalid-input reporting.
---

Use the delivered `scripts/calc_descriptors.py` in a CPU container environment
with Python and the dependencies below. From the package directory run:

```sh
python scripts/calc_descriptors.py --smiles CCO
python scripts/calc_descriptors.py --input /input/rows.smi --output /output/results.jsonl
```

For a file,
mount a UTF-8 file directory read-only at `/input` and a writable output directory
at `/output`, then pass `--input /input/rows.smi --output /output/results.jsonl`.
Use one SMILES per line. The parser requires exactly one of `--smiles` or `--input`.
Without `--output`, results are written to standard output as JSONL.

Every valid row has `ok: true`, the input, canonical SMILES and descriptors:
molecular weight, logP, TPSA, H-bond donors/acceptors and rotatable bonds.
Invalid or empty SMILES produces `ok: false` and `Invalid or empty SMILES`.
The process exits 0 only when every row is valid; otherwise it exits 2 and retains
the per-row results, including valid rows in mixed files. An empty file produces
zero records and exit 0; check the expected record count. Missing dependencies,
unreadable input or unwritable output cause operational exceptions, which must
be fixed separately from invalid molecule rows. Do not treat a created
output file or exit code alone as proof that every molecule was valid.

Dependencies are public CPU packages pinned by the source requirements:
RDKit 2024.9.6, NumPy 1.26.4 and Pillow 11.3.0. Install them only during image
construction, not on the host. This scope needs no GPU, model weights, credentials
or external inference service. Large input memory needs still depend on workload.

These are descriptors computed from a molecular graph, not experimental
measurements or evidence of biological activity, safety or pharmacokinetics.
They do not predict conformer properties or reactions. This tool has no GPU path.
