---
name: chembl-target-text-search
description: >
  Draft capability for searching ChEMBL targets with a query string. Invoke for: GET /chembl/api/data/target/search?q=:query. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Chembl Target Text Search

This cited draft describes GET /chembl/api/data/target/search?q=:query. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- database_doc: https://www.ebi.ac.uk/chembl/api/data/spore (source s1; SHA-256 72e5b95ce912d114e97998f04f766c4654b78b6c976d858da8284a9ba62b1597)

## Input & Output

Inputs:

- A required query string passed through the q parameter. (s1:L1-L1)

Outputs:

- Target search results associated with the targets collection; the documented default format is application/xml. (s1:L1-L1)

## Procedure Guidance

- Issue a GET request to the target search endpoint, substituting the query string for :query. (s1:L1-L1, s1:L1-L1)

## Matters & Troubleshooting

Resources:

- external_asset: /chembl/api/data/target/search?q=:query — Access to the ChEMBL target search resource is required.

Unknowns and limits:

- Query grammar, searched fields, ranking, and pagination are not specified.
- Response field definitions and error behavior are not supplied.
