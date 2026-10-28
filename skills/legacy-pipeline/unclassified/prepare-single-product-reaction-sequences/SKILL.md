---
name: prepare-single-product-reaction-sequences
description: "Prepare mapped single-product reaction records for a supplied tokenizer/reagent vocabulary while keeping atom contribution, grouped splitting, and model compatibility explicit."
license: undetermined
---


# Prepare single-product reaction sequences

Input: mapped `reactants>reagents>products` SMILES; RDKit; the target model's tokenizer and canonicalization policy; and, for the source protocol, its supplied 76-reagent vocabulary **and token mapping**. Output: grouped dataset partitions and tokenized source/target pairs. Do not invent a missing vocabulary or substitute a new tokenizer for an existing checkpoint.

## Usage

1. Parse molecules and retain exactly one product under the dataset's declared product convention. Record invalid, multi-product and unmapped/unreliably mapped exclusions rather than guessing contribution.
2. Before removing maps, collect mapped product atoms. An input molecule contributing mapped atoms to that product is a reactant; other input molecules are reagents. An unmapped atom is not evidence of non-contribution.
3. Remove atom maps, apply the model's hydrogen policy and canonicalize consistently. Remove duplicate reaction records. Build a stable group key from the complete canonical reactant multiset.
4. Assign whole groups to train/validation/test, e.g. the source's 18:1:1 proportions, using a recorded seed. Do this before augmentation so equivalent reactants do not leak across splits.
5. Tokenize reactants and product using the model's actual atom-wise tokenizer; append known reagent tokens in its documented order. Drop out-of-vocabulary reagents only when reproducing that explicit protocol, and record that loss. Keep spaces/token separators exactly as its encoder expects.

Intermediate record example (molecules illustrative; tokens depend on the supplied model):

```json
{"id":"rxn-1", "reactants":["CCO"], "reagents":["O"],
 "product":"CC=O", "group_key":"CCO", "split":"train"}
```

If the reagent mapping/tokenizer is unavailable, stop at these canonical role-separated records and identify the missing input; do not claim checkpoint-ready sequences. Report pair counts, exclusion reasons, vocabulary version and group-disjointness checks.

Source: [sequence-model study](https://arxiv.org/pdf/1711.04810.pdf).
