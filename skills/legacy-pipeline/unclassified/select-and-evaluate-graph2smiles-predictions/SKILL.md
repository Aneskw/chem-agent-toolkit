---
name: select-and-evaluate-graph2smiles-predictions
description: "Select Graph2SMILES checkpoints on validation top-1 and run its prepared-data decoder, preserving its actual invalid/deduplication evaluation behavior."
license: undetermined
---


# Select and evaluate Graph2SMILES predictions

Environment: [pinned Graph2SMILES setup](https://github.com/coleygroup/Graph2SMILES/tree/1b87f9ffdb739346b94853dfe8e5d63ac0198a38), with its compatible PyTorch/RDKit environment. Required: trusted trained checkpoint, its vocabulary, matching preprocessed test NPZ, and ordered tokenized test targets for scoring. A product string alone is not `--test_bin`.

Choose the checkpoint by validation top-1 accuracy before viewing held-out results. Match task direction and preprocessing to that checkpoint. Architecture/vocabulary settings are loaded from checkpoint arguments; old checkpoints missing `mpn_type` or `rel_pos` need those CLI values explicitly matched to their training configuration.

## Usage

From the repository root, after creating output/log parent directories, for a compatible `g2s_series_rel` checkpoint:

```sh
python predict.py --model g2s_series_rel --task retrosynthesis --load_from ./checkpoints/selected.pt --test_bin ./processed/test.npz --test_tgt ./data/tgt-test.txt --result_file ./results/test.txt --log_file ./results/test.log --beam_size 30 --n_best 30 --predict_batch_size 4096 --do_predict --do_score
```

Replace paths with the checkpoint's prepared assets. Do not copy `scripts/predict.sh` blindly: at this revision its checkpoint naming/MPN setting and undefined relative-position variable need alignment with the chosen model. Use a new result filename: `predict.py` skips prediction when that file already exists.

Output has one line per input, comma-separated tokenized candidate SMILES; scoring removes token whitespace and canonicalizes candidates. The upstream scorer removes invalid/empty and `CC` sentinel predictions, deduplicates remaining candidates preserving order, and then computes top-n over that compressed list. It retains all target lines in the denominator, including skipped empty/`CC` targets. Record this behavior for paper reproduction; for an independent evaluation, declare any different rank/sentinel policy.

Before accepting metrics, check prediction/target line counts and order: the source uses `zip`, so a truncated prediction file can go unnoticed. Report invalid and empty cases. Exact molecular agreement includes stereochemistry and excludes atom maps under the chosen normalizer; benchmark agreement does not prove chemical feasibility.

Sources: [decoder and scorer](https://github.com/coleygroup/Graph2SMILES/blob/1b87f9ffdb739346b94853dfe8e5d63ac0198a38/predict.py), [argument definitions](https://github.com/coleygroup/Graph2SMILES/blob/1b87f9ffdb739346b94853dfe8e5d63ac0198a38/utils/parsing.py).
