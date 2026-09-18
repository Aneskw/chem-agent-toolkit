---
name: localretro-single-step-retrosynthesis
description: >-
  Invoke for: single-step retrosynthesis when a target product SMILES must be converted into ranked reactant candidates with LocalRetro. Do not use for forward prediction, multi-step routes, or experimental success probabilities.
license: CC-BY-NC-SA-4.0 (upstream README; see references)
allowed-tools: Read, Bash, Write
---

# LocalRetro single-step retrosynthesis

Use the pinned LocalRetro wrapper to generate ranked, deduplicated reactant candidates for one connected product SMILES. This is a candidate-generation procedure, not a route planner or an experimental feasibility assessment.

## Credibility

Status: `inference_smoke_tested`. Two real CPU predictions and three invalid-input checks passed in the tested macOS arm64/Python 3.11 environment. This does not establish reaction accuracy or experimental success. The package records the pinned upstream commit, resource hashes, model device, and runtime.

## Reference

- Paper: https://doi.org/10.1021/jacsau.1c00246
- Upstream commit: `eba83e72efabeb854fec86c865e8743c295a8a1e`
- [Retrosynthesis.py](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c8653c295a8a1e/Retrosynthesis.py)
- [Default model configuration](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/data/configs/default_config.json)

## Input and output

Input: a connected product SMILES containing at least one chemical bond and `top_k` in the range 1–100. The wrapper removes atom-map labels and canonicalizes the product; do not use it when map preservation is required.

Output: JSON containing `product_smiles`, `candidates`, `candidate_count`, model scores, local templates, commit, weight SHA-256, device, and elapsed time. A valid response has `ok: true` and a non-empty deduplicated candidate list. Scores are model scores, not calibrated probabilities.

## Procedure

1. Restore the pinned source, templates, weights, and locked dependencies listed in `scripts/inference_manifest.json` and `requirements-localretro-lock.txt`.
2. From the repository root run `./run_localretro.sh --product "CC(=O)Nc1ccccc1" --top-k 10`, or call `scripts/predict_localretro.py` with `--source-root`.
3. Check the exit code and parse stdout JSON. Preserve stderr and the run record.

## Fixed cases

Use [examples/cases.json](examples/cases.json) for two positive and three negative cases. Expected checks cover valid JSON, non-empty deduplicated candidates, legal SMILES, rank continuity, and explicit rejection of invalid inputs; model scores are not experimental probabilities.

## Failure and recovery

Reject invalid, disconnected, bondless, or out-of-range inputs. A missing or hash-mismatched resource is `blocked_resources`; restore the matching resource instead of bypassing the check. If no valid candidates remain, report that outcome without claiming the target is unsynthesizable. Retry only after the input or environment changes.
