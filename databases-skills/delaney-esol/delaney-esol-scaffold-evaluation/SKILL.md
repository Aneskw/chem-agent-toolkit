---
name: delaney-esol-scaffold-evaluation
description: >
  Use the Delaney ESOL molecular-solubility dataset with its measured label and a scaffold split when evaluating structure-based solubility models. Invoke for: load the bundled Delaney CSV, identify SMILES and measured log-solubility labels, then choose a scaffold split for model evaluation Do not use as evidence of successful execution.
license: undetermined
compatibility: "Bundled resources: 2; external acquisitions: 0; runtime not validated"
allowed-tools: Read, Bash
---

# Delaney Esol Scaffold Evaluation

Use this cited draft to load the bundled Delaney CSV, identify SMILES and measured log-solubility labels, then choose a scaffold split for model evaluation. Apply it only when the listed inputs and rule preconditions hold. Do not apply it outside the stated scope or treat computed outputs as experimental evidence. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

Use the cited primary text to check scientific scope; use pinned code to check implementation behavior. README statements alone do not establish chemistry or execution. Inspect [the evidence index](references/evidence.json) for each rule's quotes, source hashes and declared assumptions.

- database_doc: https://raw.githubusercontent.com/deepchem/deepchem/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/delaney_datasets.py (sources s1).

## Input & Output

Inputs:

- A Delaney CSV containing SMILES structures and measured log solubility labels. (s1:L45-L50)

Outputs:

- Features and regression labels, optionally divided into train, validation and test sets. (s1:L58-L59)

## Procedure Guidance

- **When**: Evaluating a structure-to-solubility model on Delaney ESOL.
- **Requires**: The Delaney CSV and a plan for train, validation and test separation.
- **Choose**: Use the loader's scaffold split as the default comparison setup.
- **Avoid**: Silently replace the recommended split with a different split while comparing reported results.
- **Why**: The supplied Delaney loader explicitly recommends scaffold splitting for this dataset.
- **Check**: Record the split choice and verify that the target is measured log solubility in mols per litre.
- **Stop / fallback**: If the CSV or label column is missing, restore the pinned dataset before evaluation.
- **Scope**: Delaney ESOL model evaluation, not a universal rule for all chemistry datasets.

Support: direct; s1:L38-L50.


- Read the bundled CSV using the smiles feature field and the measured log-solubility task; use scaffold splitting for the evaluation configuration. (s1:L17-L24, s1:L27-L30)

## Matters & Troubleshooting

Declared requirements:

- repo_file: datasets/delaney-processed.csv — The loader reads this CSV as the dataset file.

Resource recovery manifest:

- dataset: `datasets/delaney-processed.csv` — status `present`; source: https://raw.githubusercontent.com/deepchem/deepchem/455d07f3e17e880a4d980b5b0365e4a02b417e14/datasets/delaney-processed.csv; revision: 455d07f3e17e880a4d980b5b0365e4a02b417e14; sha256: 8c06a76f0c6487d29ab0f903e6a7a7139f189ab3c1178f159c8be8964602f189; restore: `included at resources/datasets/delaney-processed.csv`
- source_code: `deepchem/molnet/load_function/delaney_datasets.py` — status `present`; source: https://raw.githubusercontent.com/deepchem/deepchem/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/delaney_datasets.py; revision: 455d07f3e17e880a4d980b5b0365e4a02b417e14; sha256: 12bf9a7118a9d9bf47347224b57a45900306f2b55813e2e310c55e18473d21ce; restore: `included at resources/deepchem/molnet/load_function/delaney_datasets.py`

Unknowns and limits:

- The source recommends scaffold splitting but does not establish that every other split is invalid; do not generalize this rule to unrelated datasets.
