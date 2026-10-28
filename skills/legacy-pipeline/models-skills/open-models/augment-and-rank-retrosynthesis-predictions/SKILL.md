---
name: augment-and-rank-retrosynthesis-predictions
description: "Organize randomized product inputs and two-stage sampling for an already configured reasoning-capable retrosynthesis predictor, then rank valid canonical reactant sets."
license: undetermined
---


# Two-stage retrosynthesis sampling

Use with a configured predictor that can sample a reasoning prefix and then continue reactant-answer sampling from that prefix. A generic beam decoder without prefix continuation is insufficient. This is sampling-method guidance, not a deployment package.

| Input | Meaning |
| --- | --- |
| product SMILES | One target; equivalent randomized encodings must preserve identity |
| configured predictor | Model/tokenizer/checkpoint and the provider's actual prefix-continuation interface |
| `ka`, `ks`, `kb`, `top_k` | Requested input encodings, reasoning samples per encoding, answer samples per prefix, final candidates |
| decoding settings | Temperatures, token limits, seed where supported, answer parser |

## Usage

1. Retain the canonical product and generate up to `ka` distinct equivalent SMILES. Small molecules may have fewer unique encodings; report the actual count.
2. For every encoding, sample `ks` reasoning prefixes with the configured model. For each prefix, sample `kb` answers starting at its answer boundary. Use the model's prompt/tag format; do not fabricate a universal API or concatenate unrelated responses.
3. Keep raw answers associated with encoding/prefix/sample IDs. Parse reactant SMILES, reject invalid molecules, remove atom maps, and canonicalize with stereochemistry. Sort disconnected components while preserving multiplicity.
4. Count each sampled valid answer once, merge equivalent reactant sets, sort by decreasing count with a declared deterministic tie rule, and return up to `top_k`. Report invalid/failed samples and actual sampling totals; do not retry selectively until a favored answer wins.

For example, `ka=2, ks=2, kb=3` requests at most 12 answers. These are illustrative budget choices; the paper's larger settings and answer temperature are experimental choices, not universal requirements. Prefixes from different runs remain separate even when final answers agree.

Output: canonical reactant sets with counts and sample provenance. Frequency is not calibrated chemical confidence. This method assumes the trained reasoning predictor already exists; it does not teach an arbitrary LLM the specialized model behavior.

Sources: [paper, inference augmentation](https://arxiv.org/html/2507.17448v1#S3.SS4), [official implementation](https://github.com/OpenDFM/RetroDFM-R/tree/8eeb3f4564ad10b3d8d1c4f62b4506f453948291).
