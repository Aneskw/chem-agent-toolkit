---
name: construct-retrosynthetic-route-benchmark
description: "Build a target-disjoint multistep benchmark from an existing reaction network and purchasable inventory, preserving AND requirements and route-extraction assumptions."
license: undetermined
---


# Construct a route benchmark

Use with reaction records, a frozen purchasable-material inventory, molecule-normalization policy, and a route extractor able to handle reaction AND branches. Output: target-disjoint train/validation/test route records plus extraction settings. This is benchmark-construction guidance, not a supplied network extractor.

## Usage

1. Normalize consistently, remove invalid/duplicate reactions, and retain source reaction IDs. Record exclusions. Keep each reaction's complete reactant set attached to one reaction node/hyperedge.
2. For terminal-product selection, orient the synthesis network **reactant → reaction → product**. Molecule nodes with out-degree zero are terminal products; reversing the graph reverses this criterion.
3. Extract routes to inventory leaves with the configured extractor. Every reactant of a selected reaction must be solved. A shortest ordinary graph path is insufficient: `A+B → T` requires both A and B. Declare whether shortest means maximum reaction depth or total reaction count, how cycles are rejected, and how equal-cost routes are retained.
4. Exclude single-step targets for a multistep-only benchmark. Partition by normalized target identity, e.g. the paper's 80/10/10 proportions, with a recorded seed and rounding rule. Assign all routes for one target to the same partition.
5. Verify leaf membership, reaction connectivity, and disjoint target sets. Report shared intermediates/reactions separately; target-disjoint does not mean reaction-disjoint.

Minimal route-record shape (IDs are illustrative, not molecules):

```json
{"target_id":"T", "split":"test", "steps":[
  {"reaction_id":"r1", "product":"T", "reactants":["I","A"]},
  {"reaction_id":"r2", "product":"I", "reactants":["B","C"]}
], "inventory_leaves":["A","B","C"]}
```

Freeze dataset and inventory snapshots alongside the output; missing inventory coverage and exhausted extraction limits are unresolved routes, not evidence of impossibility.

Source: [FusionRetro, dataset construction](https://arxiv.org/html/2209.15315v3).
