---
name: choose-retrosynthesis-evaluation-scope
description: "Choose and document full-reactant versus principal-fragment top-n evaluation without confusing reagent ambiguity with complete reaction recovery."
license: undetermined
---


# Choose retrosynthesis evaluation scope

Input: ranked reactant predictions, reference reactant sets, and the scientific comparison goal. Output: an explicit metric policy and paired top-n results when both scopes matter. This Skill selects evaluation rules; it does not supply a predictor.

| Goal | Primary report | Limitation |
| --- | --- | --- |
| Recover the recorded reaction | Canonical full-reactant-set exact match | Alternative valid routes may be scored wrong |
| Recover the principal transformation | A declared largest-fragment/MaxFrag match | Does not establish complete reagent or reactant recovery |

## Usage

Before scoring, freeze map removal, stereochemistry, fragment multiplicity, invalid-output handling, deduplication and rank policy. For a largest-fragment metric, obtain the benchmark's precise size definition and tie rule; if unavailable, declare a local convention and do not label the result as exact reproduction of its MaxFrag number.

For example, reference `large_substrate.small_reagent` and prediction `large_substrate.other_reagent` can agree under a principal-fragment rule and disagree under full-set matching. Report both judgments rather than replacing one with the other. For top-n, count each evaluated target once; failed/empty predictions remain failures. Use validation data to choose policies and keep the held-out test fixed.

The paired report should name metric, `n`, target count, correct count, invalid/empty count, and normalization. Neither score proves experimental synthesis success.

Source: [augmented Transformer evaluation study](https://www.nature.com/articles/s41467-020-19266-y).
