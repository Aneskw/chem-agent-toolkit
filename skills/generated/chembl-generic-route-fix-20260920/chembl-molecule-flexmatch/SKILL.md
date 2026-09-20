---
name: chembl-molecule-flexmatch
description: >
  Draft capability for retrieving ChEMBL molecules using the documented SMILES flexmatch operator. Invoke for: GET /chembl/api/data/molecule/ with the molecule_structures__canonical_smiles__flexmatch query parameter. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Chembl Molecule Flexmatch

This cited draft describes GET /chembl/api/data/molecule/ with the molecule_structures__canonical_smiles__flexmatch query parameter. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- database_doc: https://www.ebi.ac.uk/chembl/api/data/spore (source s1; SHA-256 72e5b95ce912d114e97998f04f766c4654b78b6c976d858da8284a9ba62b1597)

## Input & Output

Inputs:

- A SMILES structure supplied as molecule_structures__canonical_smiles__flexmatch. (s1:L1-L1, s1:L1-L1)

Outputs:

- A list of molecules matching the supplied structure under flexmatch semantics. (s1:L1-L1, s1:L1-L1)

## Procedure Guidance

- Send a GET request to the molecule list endpoint with the SMILES in molecule_structures__canonical_smiles__flexmatch, following the documented query pattern. (s1:L1-L1, s1:L1-L1)

## Matters & Troubleshooting

Resources:

- external_asset: https://www.ebi.ac.uk/chembl/api/data/molecule — The documented external endpoint performs the structure-matching request.

Unknowns and limits:

- Complete flexmatch semantics, including stereochemistry handling, are not specified beyond the example.
- Pagination, error handling, and complete URL-encoding rules are not supplied.
