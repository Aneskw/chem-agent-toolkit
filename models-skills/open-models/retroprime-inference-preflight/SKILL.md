---
name: retroprime-inference-preflight
description: >-
  Check RetroPrime two-stage inference scripts, weight paths, input file and visible dependencies. Invoke for: diagnosing why a pinned RetroPrime run cannot start before running P2S and S2R prediction; do not use it to claim inference accuracy or successful prediction.
license: MIT
compatibility: Python 3.10+; optional RDKit, PyTorch and pandas checks; pinned RetroPrime checkout and weights required for inference
allowed-tools: Bash, Read
---

# RetroPrime inference preflight

Inspect the resources needed by RetroPrime's pinned example runner before an
inference attempt. Use it for a local checkout and product SMILES input file.
Do not use it as a prediction tool, weight downloader, or chemical validator.

## Credibility

**High confidence (Enforce strictly)** for file presence and readable input
checks, covered by complete and incomplete synthetic layouts. **Medium
confidence (Need verification)** for runtime readiness: import visibility does
not establish compatible library versions, valid weights, or a working GPU.
No model forward pass occurs in this skill.

## Reference

- RetroPrime, DOI `10.1016/j.cej.2021.129845`.
- Pinned `wangxr0526/RetroPrime` commit
  `a765b670b72fbfd512d0d437da8f27a95f9f0554`: consult `run_example.sh`
  for actual P2S/S2R weight paths and `README.md` for dataset and invocation
  context. The source lock is `creation_pipeline/source_locks/VQ33W3ED.json`.
- The README embeds generic `_model.pt` names, while the pinned example script
  uses step-numbered names. Follow the exact script that will be executed.

## Input & Output

Input: `--source-root` for a RetroPrime checkout; optional `--input` UTF-8
file containing one nonempty product SMILES per line. Output: JSON with
`ok`, `status`, missing scripts/weights/modules, input errors and warnings.
`execution_performed` is always `false`; exit code 2 denotes blocked resources.
The preflight deliberately does not call the tokenizer or validate SMILES.

## Procedure Guidance

```bash
python scripts/preflight.py --source-root /path/to/RetroPrime --input products.txt
```

Resolve missing scripts and weights using the exact pinned checkout. If the
result is `ready_to_attempt`, run the separate
`retroprime-two-stage-retrosynthesis` skill and retain its logs. If using
`--skip-env-check`, treat the result as a file-only check.

## Matters & Troubleshooting

- Missing weights are a resource block, not evidence the model failed.
- The README and script weight filenames differ; do not rename arbitrary files
  to satisfy this check without verifying their identity.
- A readable line is not necessarily valid SMILES. Validate input separately.
- A successful preflight does not demonstrate GPU compatibility or scientific
  prediction quality.
