---
name: rdkit-descriptor-result-triage
description: >
  Run the included RDKit descriptor calculator and distinguish computed graph features from measured chemical or biological outcomes. Invoke for: calculate descriptors for SMILES records, retain explicit invalid-input failures, and limit interpretation to computed structure features Do not use as evidence of successful execution.
license: undetermined
compatibility: "Bundled resources: 1; external acquisitions: 1; runtime not validated"
allowed-tools: Read, Bash
---

# Rdkit Descriptor Result Triage

Use this cited draft to calculate descriptors for SMILES records, retain explicit invalid-input failures, and limit interpretation to computed structure features. Apply it only when the listed inputs and rule preconditions hold. Do not apply it outside the stated scope or treat computed outputs as experimental evidence. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

Use the cited primary text to check scientific scope; use pinned code to check implementation behavior. README statements alone do not establish chemistry or execution. Inspect [the evidence index](references/evidence.json) for each rule's quotes, source hashes and declared assumptions.

- tool_doc: local://tools-skills/rdkit/chem-rdkit-descriptors/SKILL.md (sources s1).
- tool_doc: local://tools-skills/rdkit/chem-rdkit-descriptors/references/science.md (sources s3).
- repo_code: local://tools-skills/rdkit/chem-rdkit-descriptors/scripts/calc_descriptors.py (sources s4).

## Input & Output

Inputs:

- One SMILES string or a text file with one SMILES per line. (s1:L10-L16)

Outputs:

- JSON records with ok status, canonical SMILES and RDKit descriptors, or an explicit invalid-SMILES error. (s4:L7-L27, s1:L19-L19)

## Procedure Guidance

- **When**: A requested descriptor record has ok=false or is being used as evidence of biological activity.
- **Requires**: The calculator's ok status and the intended downstream claim.
- **Choose**: Correct or exclude invalid SMILES; for valid records, describe values only as computed structure descriptors.
- **Avoid**: Use missing descriptor fields or calculated LogP/TPSA as experimental activity or safety evidence.
- **Why**: Invalid SMILES produce ok=false, and the source explicitly limits descriptors to graph-derived quantities.
- **Check**: Verify ok=true before using values and preserve the original input/error record for failures.
- **Stop / fallback**: Stop the descriptor-based comparison for failed records until the input is corrected; request measured data for experimental claims.
- **Scope**: This RDKit descriptor calculator and its JSON records, not all ADMET measurements.

Support: direct; s3:L1-L3, s4:L12-L12.


- Run `python3 resources/tools-skills/rdkit/chem-rdkit-descriptors/scripts/calc_descriptors.py --smiles CCO` (or use --input for a file); check each JSON record's ok field and exclude failed records from descriptor comparisons. (s1:L14-L19, s4:L32-L45)

## Matters & Troubleshooting

Declared requirements:

- repo_file: tools-skills/rdkit/chem-rdkit-descriptors/scripts/calc_descriptors.py — The calculator implements SMILES parsing and descriptor output.

Resource recovery manifest:

- source_code: `tools-skills/rdkit/chem-rdkit-descriptors/scripts/calc_descriptors.py` — status `present`; source: local://tools-skills/rdkit/chem-rdkit-descriptors/scripts/calc_descriptors.py; revision: working-tree-resource-snapshot; sha256: 0b55d6132d83dc3b04413ed1c4a22788a62b96f0a02eda5992c43a080dfe67fe; restore: `included at resources/tools-skills/rdkit/chem-rdkit-descriptors/scripts/calc_descriptors.py`
- dependency: `rdkit` — status `download_required`; source: https://www.rdkit.org/docs/Install.html; revision: version not pinned by source; sha256: not verified; restore: `python3 -m pip install rdkit`

Unknowns and limits:

- Descriptor values are not measured activity, safety or pharmacokinetic outcomes; a target RDKit version is not established by these sources.
