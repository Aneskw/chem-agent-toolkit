---
name: predict-reaction-products-with-confidence-abstention
description: "Apply a declared confidence threshold to existing forward product predictions and report accepted accuracy together with coverage."
license: undetermined
---


# Product prediction with abstention

Use with a configured forward predictor or its top-1 predictions. Input per reaction: ID, predicted product, documented top-1 score semantics and optional reference product; also supply a threshold chosen on validation data. Output: accepted canonical product or `unknown`, plus coverage and, with labels, accepted accuracy. This Skill does not provide or train the predictor.

## Usage

1. Generate predictions with fixed model/checkpoint and decoding settings. Store raw outputs and scores before filtering.
2. Canonicalize prediction and reference consistently with RDKit, preserving stereo and removing atom maps. Invalid/empty predictions become `unknown`.
3. Accept a valid prediction when its score is at least the declared threshold. The source's probability threshold cannot be applied unchanged to log-probabilities, length-normalized scores or a different model.
4. Report `coverage = accepted / all_attempted`. When references exist, report `accepted_accuracy = correct_accepted / labeled_accepted`; when no labeled prediction is accepted, report accuracy as undefined rather than 0 or 1. Report unlabeled counts separately.

Example: out of 100 attempted labeled reactions, 60 are accepted and 54 match: coverage 0.60 and accepted accuracy 0.90. The 40 abstentions remain in the coverage denominator. Sweep thresholds on validation data, then freeze one for the held-out report; do not tune on test outcomes.

Acceptance controls a model-specific accuracy/coverage tradeoff, not experimental confidence. Do not infer a universal threshold from the paper's example value.

Source: [sequence-model study](https://arxiv.org/pdf/1711.04810.pdf).
