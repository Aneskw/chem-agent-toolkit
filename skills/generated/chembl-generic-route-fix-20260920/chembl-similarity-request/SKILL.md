---
name: chembl-similarity-request
description: >
  Draft capability for calling the ChEMBL similarity endpoint with its two required path parameters. Invoke for: GET /chembl/api/data/similarity/:smiles/:similarity. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Chembl Similarity Request

This cited draft describes GET /chembl/api/data/similarity/:smiles/:similarity. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- database_doc: https://www.ebi.ac.uk/chembl/api/data/spore (source s1; SHA-256 72e5b95ce912d114e97998f04f766c4654b78b6c976d858da8284a9ba62b1597)

## Input & Output

Inputs:

- Required smiles and similarity path parameters. (s1:L1-L1)

Outputs:

- A similarity resource response associated with the molecules collection, with application/xml as the documented default format. (s1:L1-L1)

## Procedure Guidance

- Substitute the supplied smiles and similarity values into the documented path and issue a GET request. (s1:L1-L1, s1:L1-L1)

## Matters & Troubleshooting

Resources:

- external_asset: /chembl/api/data/similarity/:smiles/:similarity — Access to the ChEMBL similarity resource is required.

Unknowns and limits:

- The similarity metric, parameter range, units, and threshold semantics are not specified.
- SMILES path encoding, response fields, and result cardinality are not established by the supplied endpoint declaration.
