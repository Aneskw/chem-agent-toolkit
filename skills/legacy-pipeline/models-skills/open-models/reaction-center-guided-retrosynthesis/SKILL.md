---
name: reaction-center-guided-retrosynthesis
description: "Use the pinned Retroformer batch decoder to choose naive versus searched reaction centers and produce ranked single-step retrosynthesis proposals."
license: undetermined
---


# Reaction-center-guided Retroformer inference

Environment: [Retroformer source/setup](https://github.com/yuewan2/Retroformer/tree/4e94540e06f5a0ed52ac7b7c4acdd98e92aeda56), PyTorch 1.10.1 and compatible RDKit/dependencies described there. Install the source with `pip install -e .` in its environment. Obtain the matching pretrained checkpoint, vocabulary and data through that README's official download entry.

Input is the decoder's prepared dataset, not a free-form product string: CSV columns `id`, `class`, `reactants>reagents>production`, plus checkpoint-compatible cooked data/vocabulary. `--known_class False` is for unknown-class evaluation; do not supply true classes to that setting. Keep preprocessing and architecture consistent with the checkpoint.

## Usage

From the repository root, create `result/` and run the actual module (the README's bare `translate.py` is nested under `retroformer/`):

```sh
python -m retroformer.translate --data_dir ./data/uspto50k --intermediate_dir ./intermediate --checkpoint_dir ./checkpoint --checkpoint model_best.pt --known_class False --shared_vocab True --shared_encoder False --beam_size 10 --batch_size_val 4 --stepwise True --use_template False --device cuda
```

`--checkpoint_dir ./checkpoint` becomes `./checkpoint_untyped` internally (`_typed` for known class); do not append the suffix twice. The vocabulary under `intermediate/` must match those weights.

| Switch | Behavior |
| --- | --- |
| `--stepwise False` | Original/naive decoding |
| `--stepwise True --use_template False` | Search predicted reaction-center subgraphs before decoding |
| `--use_template True` | Forces stepwise mode and requires `intermediate/rt2reaction_center.pk` |

Use literal string values `True`/`False`, not flag presence. The checked search decoder uses `T=10`, `beta=0.5`, three candidate centers, atom percentile 40 and bond percentile 40 (unknown class) or 55 (known class). Temperature scales reactive logits before sigmoid in the implementation. Use that implementation rather than reconstructing ambiguous paper pruning/overlap rules.

Output: printed top-k metrics and a pickle `(ground_truths, generations)` under `result/`, with a filename distinguishing vanilla/stepwise and typed/untyped modes. Candidate ranking combines length-normalized decoder score and center score; scores are not calibrated chemical success probabilities. Existing result files can be overwritten, so use separate output/intermediate layouts for experiments. The evaluation loop assumes enough generated candidates; a short/empty beam or exception is a failed evaluation, not a valid zero-free report. For arbitrary-product serving, a separate dataset adapter is required.

Source: [decoder and flags](https://github.com/yuewan2/Retroformer/blob/4e94540e06f5a0ed52ac7b7c4acdd98e92aeda56/retroformer/translate.py), [search implementation](https://github.com/yuewan2/Retroformer/blob/4e94540e06f5a0ed52ac7b7c4acdd98e92aeda56/retroformer/utils/translate_utils.py).
