---
name: evaluate-planning-with-depth-pruning-and-set-matching
description: "Evaluate completed retrosynthesis plans against alternative reference starting-material sets under an explicitly declared reference-depth benchmark protocol."
license: undetermined
---


# Evaluate route completion and starting-material agreement

Input: targets, reference routes with depth and starting-material sets, predicted routes from a configured planner, inventory, and a fixed molecular-identity policy. Output per target: completion, depth outcome, starting-material-set match, failures; aggregate rates retain every attempted target.

## Usage

1. Freeze the benchmark depth convention (longest root-to-leaf reaction depth versus total steps). If reference routes differ in depth, use the benchmark's specified cap; absent one, declare a convention before evaluation and report it as a local variant.
2. A route is complete only when **all** leaves belong to the frozen inventory. Apply a reference-depth cap only in this retrospective benchmark; reference depth is unavailable in real prospective planning. Record depth-pruned, exhausted and invalid routes separately.
3. Convert valid leaf molecules to full InChIKeys under one standardization/stereo policy. Compare predicted starting-material sets against each reference route's set, not their union. Accept agreement with any one reference set.
4. Use set semantics only if that is the protocol: sets ignore multiplicity and stoichiometry. Report route validity/completion separately; equal leaf sets do not prove equal reactions or an experimentally feasible route.

For example, references `{A,B}` and `{C,D}` accept predicted `{A,B}` but reject `{A,C}`. Invalid leaf structures are unassessed/failures, not silently removed before matching. Do not omit failed targets from the rate denominator.

Source: [FusionRetro evaluation protocol](https://arxiv.org/html/2209.15315v3).
