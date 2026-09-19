---
name: chem-retro-candidate-evaluation
description: >-
  Evaluate ranked retrosynthesis precursor proposals by canonical exact match and optional supplied forward-model round trip. Invoke for: checking top-k predictions against known reactants and products; do not use it to generate precursors or claim route feasibility.
license: MIT
compatibility: Python 3.10+ with RDKit; optional forward predictions must be supplied by a separate model
allowed-tools: Bash, Read, Write
---

# Retrosynthesis candidate evaluation

Compare predicted precursor sets with known reactants without depending on
component order or atom-map labels. Optionally score a precomputed forward
prediction against the target product. Use for evaluation records, not for
retrosynthesis generation, synthesis planning, or experimental validation.

## Credibility

**High confidence (Enforce strictly)** for the packaged exact-match operation:
component-order invariance, map removal, invalid-SMILES rejection and top-k
aggregation have executable tests. **Medium confidence (Need verification)**
for round-trip interpretation: this package checks *supplied* forward outputs
but does not run or validate the forward model. A model's own accuracy and
preprocessing can dominate the result. No published benchmark score is claimed.

## Reference

- Wang et al., *JACS Au* 2021, DOI `10.1021/jacsau.1c00246`, reports exact
  matching and forward-model round-trip evaluation for LocalRetro.
- Pinned source: `kaist-amsg/LocalRetro` commit
  `eba83e72efabeb854fec86c865e8743c295a8a1e`; hashes in
  `creation_pipeline/source_locks/2GFR874J.json`.
- Our handling of invalid entries, partial forward coverage, atom-map removal,
  and explicit top-k fields is a package convention; see
  `references/interpretation.md` before comparing to a published number.

## Input & Output

Input JSONL rows need `target_product`, `ground_truth_reactants`, and a ranked
`predictions` array. Each prediction needs `reactants`; optional
`forward_product` must be a result from an independently run forward model.
Each output JSONL row reports `exact_top1`, `exact_topk`, per-prediction results,
and `roundtrip_top1/topk`. Round-trip fields are `null` if forward coverage is
incomplete. A malformed row has `ok: false`; process exit code is 2.

## Procedure Guidance

```bash
python scripts/evaluate_candidates.py \
  --input predictions.jsonl --top-k 10 --output evaluation.jsonl
```

Keep each forward model's identifier, checkpoint, preprocessing, and test split
with the input record. Compare methods only on the same cases and evaluation
policy. Count a proposal as exact when canonical precursor components match;
ground truth with unspecified stereo is compared by connectivity.

## Matters & Troubleshooting

- A reaction product predicted by a weak forward model is not chemical proof.
- Missing `forward_product` is reported as unassessed, not as a failure or a
  fabricated success.
- This evaluates one-step precursor proposals only; it does not assess route
  cost, purchasability, reaction conditions, yield or safety.
