---
name: chem-edbo-recommend-next-batch
description: >-
  Invoke for: recommending the next batch of single-objective chemical experiments from a mixed categorical/continuous reaction space and observed yields or scores using Gaussian-process Expected Improvement. Do not use for reaction prediction, retrosynthesis, molecule generation, safety review, or multi-objective Pareto optimization.
license: MIT
allowed-tools: Bash, Read, Write, Glob, WebFetch, WebSearch
---

# EDBO-style next-batch recommendation

Use the packaged EDBO-style Bayesian optimization implementation to select a batch of experiments. The numerical recommendation comes from the scripts; an LLM may explain the JSON but must not change it.

## Scope and credibility

The procedure supports small-data, single-objective optimization with categorical one-hot and continuous descriptors. It uses a Matérn-5/2 Gaussian process, Expected Improvement, normalization, duplicate removal, and greedy batch selection with Kriging-believer updates. The implementation has local benchmark and simulated-loop evidence in `results/RESULTS.md`; it is not a guarantee of experimental success.

Do not use this skill for reaction prediction, retrosynthesis, molecule generation, high-dimensional data, multi-objective Pareto optimization, or safety decisions. Human review is required before running an experiment.

## Reference

- Shields et al., *Nature* 2021, DOI: 10.1038/s41586-021-03213-y
- `references/edbo-literature.md`
- `references/implementation-mapping.md`
- EDBO software: https://github.com/b-shields/edbo
- EDBO+: https://github.com/doyle-lab-ucla/edboplus

## Input and output

`--space` is a JSON object with an objective and descriptors. A descriptor is either categorical with at least two options or continuous with `min < max`. `--data` is CSV or JSON with matching descriptor columns and one objective column. Use a fixed `--seed` for reproducibility.

The JSON output contains `status`, `recommendations`, observed best value, predicted means and standard deviations, Expected Improvement, and confidence labels. Cold-start runs return space-filling points rather than pretending to have a fitted model.

## Procedure

```bash
python <skill>/scripts/recommend_next_batch.py \
  --space examples/direct_arylation_space.json \
  --data examples/initial_data.csv \
  --batch-size 4 --seed 7 --output recommendations.json \
  --report report.md --plot recommendations.png
```

Append measured outcomes to the data file and rerun for the next iteration. Preserve the input files, JSON output, and report together.

## Failure and recovery

Reject inconsistent descriptor names, invalid ranges, duplicate conditions, and unsupported multi-objective requests. With fewer than two observations, report a cold start. Do not silently extrapolate beyond declared bounds or present model predictions as measured yields.
