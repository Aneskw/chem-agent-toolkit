---
name: chem-rdkit-descriptors
description: "Invoke for: Calculate standard RDKit molecular descriptors from one or more SMILES strings. Use for reproducible structure-property features; do not interpret descriptors as measured activity or toxicity."
license: BSD-3-Clause
allowed-tools: Bash(python3:*)
---

# RDKit descriptor calculation

Read SMILES from `--smiles` or a text file and emit one JSON record per molecule. Invalid SMILES are reported with `ok: false` and do not produce fabricated values.

## Usage

```bash
python3 scripts/calc_descriptors.py --smiles "CCO"
python3 scripts/calc_descriptors.py --input examples/input.smi --output descriptors.jsonl
```

The output includes canonical SMILES, molecular weight, LogP, TPSA, H-bond donors and acceptors, and rotatable bonds. Check `ok` for each record before downstream use.

## Failure and recovery

- Missing RDKit: activate an environment containing the pinned RDKit package.
- Invalid or empty SMILES: correct the input; retain the original string in the error record.
- Batch inputs: continue processing other lines, but report the number of failed records.
