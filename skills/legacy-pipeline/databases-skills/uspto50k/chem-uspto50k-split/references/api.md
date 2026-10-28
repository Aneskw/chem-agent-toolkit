# Validator interface

`python scripts/validate_split.py --root DIRECTORY` reads train.csv, valid.csv and test.csv. Only `reaction_smiles` is required. It emits a JSON summary and exit code 0/2.

Overlap is exact equality after trimming whitespace. It is not an RDKit canonicalization or benchmark-identity check. Dataset provenance is separate from these structural checks.
