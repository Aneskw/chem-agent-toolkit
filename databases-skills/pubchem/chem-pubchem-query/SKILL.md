---
name: chem-pubchem-query
description: Query PubChem compound records by name or identifier and return a small, reproducible JSON record. Use for retrieving public compound identity and basic properties; do not use as a substitute for experimental measurements.
license: MIT
allowed-tools: Bash(python3:*)
---

# PubChem compound query

Query one compound from PubChem using its name, CID, InChIKey, or SMILES. Return the canonical SMILES, molecular formula, molecular weight, and CID when available.

## Inputs and outputs

Input is exactly one identifier and an optional output path. The command writes JSON to stdout or to `--output`. A successful response has `ok: true`, `cid`, `input`, and a `properties` object. A lookup failure has `ok: false` and an explanatory `error`; do not invent missing properties.

## Usage

```bash
python3 scripts/query_pubchem.py --query caffeine
python3 scripts/query_pubchem.py --query 2244 --output result.json
```

Check the process exit code and `ok` before using the result. PubChem records are database annotations; retain the returned CID and the retrieval URL in downstream records.

## Failure and recovery

- Network or TLS failure: report the error and retry only after connectivity is restored.
- No match or ambiguous input: return `ok: false`; ask for a CID or a more specific identifier.
- Malformed response: do not parse partial fields as a valid record.
