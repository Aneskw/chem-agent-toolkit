---
name: chembl-compound-image
description: >
  Draft capability for requesting a compound image with documented rendering options. Invoke for: GET /chembl/api/data/image/:ID. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Chembl Compound Image

This cited draft describes GET /chembl/api/data/image/:ID. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- database_doc: https://www.ebi.ac.uk/chembl/api/data/spore (source s1; SHA-256 72e5b95ce912d114e97998f04f766c4654b78b6c976d858da8284a9ba62b1597)

## Input & Output

Inputs:

- A compound identifier: ChEMBL ID or Standard InChI Key. (s1:L1-L1)
- Optional engine, dimensions, and ignoreCoords parameters. The only documented engine is rdkit, which is also the default. Dimensions is the square side length, with maximum and default 500. (s1:L1-L1, s1:L1-L1, s1:L1-L1)

Outputs:

- A compound image; the documented default response format is image/svg+xml. (s1:L1-L1, s1:L1-L1)

## Procedure Guidance

- Substitute the compound identifier for :ID and issue a GET request to the image endpoint, including any desired documented rendering options. (s1:L1-L1, s1:L1-L1, s1:L1-L1)

## Matters & Troubleshooting

Resources:

- external_asset: /chembl/api/data/image/:ID — Access to the ChEMBL image service is required.

Unknowns and limits:

- The accepted value syntax and default for ignoreCoords are not specified.
- The mechanism for selecting an output format and image dimension units are not specified.
