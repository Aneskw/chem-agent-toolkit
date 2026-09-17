---
name: retroprime-two-stage-retrosynthesis
description: >-
  Invoke for: single-step retrosynthesis with RetroPrime when one product SMILES must pass through its P2S and S2R stages to produce deduplicated reactant candidates. Do not use for multi-step routes, training, or calibrated success probabilities.
license: MIT (upstream code; weights subject to source terms)
allowed-tools: Read, Bash, Write
---

# RetroPrime two-stage retrosynthesis

Run the pinned RetroPrime compatibility wrapper for one connected product SMILES. The procedure executes product-to-synthons and synthons-to-reactants, then normalizes and deduplicates the final candidates.

## Credibility

Status: `inference_smoke_tested`. Two real CPU two-stage examples and three negative cases passed in the tested Python 3.11/PyTorch 2.2.2 compatibility environment. This is an execution check, not an accuracy benchmark.

## Reference

- Paper: https://doi.org/10.1016/j.cej.2021.129845
- Upstream commit: `a765b670b72fbfd512d0d437da8f27a95f9f0554`
- [Upstream example runner](https://github.com/wangxr0526/RetroPrime/blob/a765b670b72fbfd512d0d437da8f27a95f9f0554/run_example.sh)
- [SMILES tokenizer](https://github.com/wangxr0526/RetroPrime/blob/a765b670b72fbfd512d0d437da8f27a95f9f0554/retroprime/transformer_model/script/smi_tokenizer.py)

## Input and output

Input: one connected product SMILES with a bond and `top_k` from 1–10. The wrapper uses the pinned USPTO-50K two-stage weights and a beam size of 10.

Output: JSON containing the normalized product, deduplicated reactants, intermediate positions, both weight hashes, and per-stage timing. The upstream interface does not provide calibrated probabilities, so none are added.

## Procedure

1. Use the tested dependencies in `requirements-retroprime-lock.txt` and restore both weight files.
2. Run `./run_retroprime.sh --product "CC(=O)Nc1ccccc1" --top-k 10`, or call `scripts/predict_retroprime.py --source-root PATH_TO_RETROPRIME`.
3. Check the exit code and `ok` field; retain stderr and optional intermediate files in a new output directory.

## Failure and recovery

Reject invalid, disconnected, bondless, or out-of-range inputs. Restore missing or mismatched resources instead of bypassing hashes. If either stage fails, preserve the log and stop repeated retries. An empty candidate list does not prove that the target is unsynthesizable.
