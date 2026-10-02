---
name: retroprime-two-stage-inference-check
description: >
  Use RetroPrime for product-to-reactant single-step retrosynthesis only when tokenization, both prediction stages and both matching checkpoints are available. Invoke for: run product-to-synthon and synthon-to-reactant inference in sequence, then inspect the reactant output rather than treating first-stage synthons as final precursors Do not use as evidence of successful execution.
license: undetermined
compatibility: "Bundled resources: 4; external acquisitions: 1; runtime not validated"
allowed-tools: Read, Bash
---

# Retroprime Two Stage Inference Check

Use this cited draft to run product-to-synthon and synthon-to-reactant inference in sequence, then inspect the reactant output rather than treating first-stage synthons as final precursors. Apply it only when the listed inputs and rule preconditions hold. Do not apply it outside the stated scope or treat computed outputs as experimental evidence. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `blocked_resources`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

Use the cited primary text to check scientific scope; use pinned code to check implementation behavior. README statements alone do not establish chemistry or execution. Inspect [the evidence index](references/evidence.json) for each rule's quotes, source hashes and declared assumptions.

- model_doc: https://raw.githubusercontent.com/wangxr0526/RetroPrime/a765b670b72fbfd512d0d437da8f27a95f9f0554/README.md (sources s1).
- repo_code: https://raw.githubusercontent.com/wangxr0526/RetroPrime/a765b670b72fbfd512d0d437da8f27a95f9f0554/run_example.sh (sources s2).
- repo_code: https://raw.githubusercontent.com/wangxr0526/RetroPrime/a765b670b72fbfd512d0d437da8f27a95f9f0554/retroprime/transformer_model/script/smi_tokenizer.py (sources s3).

## Input & Output

Inputs:

- A text file of product SMILES, an output directory, and a beam size. (s1:L158-L164, s2:L3-L7)

Outputs:

- A reactant prediction file produced after the synthon stage and second translation stage. (s2:L40-L49)

## Procedure Guidance

- **When**: A product SMILES is to be converted into reactant candidates with RetroPrime.
- **Requires**: The tokenizer, full pinned RetroPrime checkout, both stage checkpoints and a resolved checkpoint-path mapping.
- **Choose**: Run canonicalization/tokenization, product-to-synthon translation, stage-two preparation, and synthon-to-reactant translation in that order.
- **Avoid**: Return first-stage synthons as final reactants or run stage two with an unmatched checkpoint.
- **Why**: The supplied runner has distinct product-to-synthon and synthon-to-reactant stages with separate model paths.
- **Check**: Confirm the second translation writes reactants_predicted.txt and that both checkpoint paths match files extracted from the documented archive.
- **Stop / fallback**: Stop before inference when either checkpoint is missing or the README and runner filenames have not been reconciled.
- **Scope**: RetroPrime single-step candidate generation; not a multistep route or experimental feasibility prediction.

Support: direct; s1:L124-L128, s2:L40-L49.


- Canonicalize and tokenize the input product SMILES before translation. (s2:L24-L25, s3:L34-L39)
- Load the product-to-synthon checkpoint, translate to synthons, process them for stage two, then load the synthon-to-reactant checkpoint and translate to reactants. (s2:L26-L49)

## Matters & Troubleshooting

Declared requirements:

- None identified.

Resource recovery manifest:

- source_code: `run_example.sh` — status `present`; source: https://raw.githubusercontent.com/wangxr0526/RetroPrime/a765b670b72fbfd512d0d437da8f27a95f9f0554/run_example.sh; revision: a765b670b72fbfd512d0d437da8f27a95f9f0554; sha256: 1ce43453fc5207f027f6b733022c4ecad4742f24e8d9b963ace014eb35ba255a; restore: `included at resources/run_example.sh`
- source_code: `retroprime/transformer_model/translate.py` — status `present`; source: https://raw.githubusercontent.com/wangxr0526/RetroPrime/a765b670b72fbfd512d0d437da8f27a95f9f0554/retroprime/transformer_model/translate.py; revision: a765b670b72fbfd512d0d437da8f27a95f9f0554; sha256: 894defac3eced6bc6292b4222efbebb7e1ee71e12db2b414b29cc672f1a8de33; restore: `included at resources/retroprime/transformer_model/translate.py`
- source_code: `retroprime/transformer_model/script/evaluate.py` — status `present`; source: https://raw.githubusercontent.com/wangxr0526/RetroPrime/a765b670b72fbfd512d0d437da8f27a95f9f0554/retroprime/transformer_model/script/evaluate.py; revision: a765b670b72fbfd512d0d437da8f27a95f9f0554; sha256: 9b714da658a4652961ab8ee1a00a4437918b26c4e620ddd64f0efd6b1cf52239; restore: `included at resources/retroprime/transformer_model/script/evaluate.py`
- preprocessing: `retroprime/transformer_model/script/smi_tokenizer.py` — status `present`; source: https://raw.githubusercontent.com/wangxr0526/RetroPrime/a765b670b72fbfd512d0d437da8f27a95f9f0554/retroprime/transformer_model/script/smi_tokenizer.py; revision: a765b670b72fbfd512d0d437da8f27a95f9f0554; sha256: c95e09f45046ad478728764106d496f4adcf40c20a66b6723cf49dad564a62c4; restore: `included at resources/retroprime/transformer_model/script/smi_tokenizer.py`
- checkpoint: `retroprime/transformer_model/experiments/checkpoints/USPTO-50K_pos_pred/USPTO-50K_pos_pred_model.pt` — status `unverified`; source: https://drive.google.com/file/d/1-715B8jU0rRC3YaY4p6URQcgjcRG2OlV/view?usp=sharing; revision: archive linked by pinned README; archive itself unversioned; sha256: not verified; restore: `gdown 1-715B8jU0rRC3YaY4p6URQcgjcRG2OlV -O retroprime-models.zip && unzip retroprime-models.zip -d retroprime/transformer_model/experiments`
- checkpoint: `retroprime/transformer_model/experiments/checkpoints/USPTO-50K_S2R/USPTO-50K_S2R_model.pt` — status `unverified`; source: https://drive.google.com/file/d/1-715B8jU0rRC3YaY4p6URQcgjcRG2OlV/view?usp=sharing; revision: archive linked by pinned README; archive itself unversioned; sha256: not verified; restore: `gdown 1-715B8jU0rRC3YaY4p6URQcgjcRG2OlV -O retroprime-models.zip && unzip retroprime-models.zip -d retroprime/transformer_model/experiments`
- dependency: `RetroPrime-source.zip` — status `download_required`; source: https://github.com/wangxr0526/RetroPrime/archive/a765b670b72fbfd512d0d437da8f27a95f9f0554.zip; revision: a765b670b72fbfd512d0d437da8f27a95f9f0554; sha256: not verified; restore: `curl -L https://github.com/wangxr0526/RetroPrime/archive/a765b670b72fbfd512d0d437da8f27a95f9f0554.zip -o RetroPrime-source.zip`

Unknowns and limits:

- The upstream README names checkpoint files ending _model.pt, while the pinned run_example.sh expects _model_step_90000.pt and _model_step_100000.pt; inspect the archive and resolve these paths before execution.
- The upstream Google Drive archive is documented but its live download could not be verified from this environment; no inference run was performed for this generated draft.
- Missing model acquisition contracts: checkpoint.
