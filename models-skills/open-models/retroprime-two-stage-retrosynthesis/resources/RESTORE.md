# RetroPrime resource restore contract

## Pinned source

```bash
git clone https://github.com/wangxr0526/RetroPrime.git
cd RetroPrime
git checkout a765b670b72fbfd512d0d437da8f27a95f9f0554
```

The required source files and both USPTO-50K stage checkpoints are listed with
SHA-256 in [`scripts/inference_manifest.json`](../scripts/inference_manifest.json).

## Checkpoint and dataset acquisition

The upstream project publishes the trained two-stage archive at:
https://drive.google.com/file/d/1-715B8jU0rRC3YaY4p6URQcgjcRG2OlV/view?usp=sharing
This is the source download method documented by the pinned README. Download
the archive, record its provenance, and extract it under
`retroprime/transformer_model/experiments/` so both stage checkpoints appear at:

- `retroprime/transformer_model/experiments/checkpoints/USPTO-50K_pos_pred/USPTO-50K_pos_pred_model.pt`
- `retroprime/transformer_model/experiments/checkpoints/USPTO-50K_S2R/USPTO-50K_S2R_model.pt`

Verify the extracted checkpoint hashes against `scripts/inference_manifest.json`.
The archive itself has no pinned hash in this Skill.

Do not use a checkpoint from another preprocessing or split convention. The
USPTO-50K data provenance must be recorded separately using the
[`USPTO-50K restore contract`](../../../databases-skills/uspto50k/chem-uspto50k-split/resources/RESTORE.md).

## Runtime

Install the pinned Python/PyTorch/RDKit dependencies from the upstream
checkout, then run the wrapper:

```bash
python3 scripts/predict_retroprime.py \
  --source-root /path/to/RetroPrime \
  --product 'CC(=O)Nc1ccccc1' --top-k 10 \
  --output-dir /path/to/run-output
```

The wrapper runs P2S, intermediate evaluation, and S2R, preserving stage logs
in the output directory. Missing or mismatched files are
`blocked_resources`; an empty candidate list is not evidence that synthesis is
impossible.
