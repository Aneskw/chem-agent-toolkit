---
name: construct-retrosynthetic-route-benchmark
description: >
  Draft procedure for constructing a target-disjoint, multi-step retrosynthesis benchmark from a reaction network. Invoke for: Clean reaction records, identify terminal products, extract shortest routes ending in starting materials, exclude single-step targets, and partition the remaining targets. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Construct Retrosynthetic Route Benchmark

This cited draft describes Clean reaction records, identify terminal products, extract shortest routes ending in starting materials, exclude single-step targets, and partition the remaining targets. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p1; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p2; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p3; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p4; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p5; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p6; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p7; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p8; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p9; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p10; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p11; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p12; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p13; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)
- paper: https://arxiv.org/pdf/2209.15315.pdf (source s1p14; SHA-256 ae04ba2f59f117fbde91c670778970757b3485a48ef21e88941648ba16489204)

## Input & Output

Inputs:

- USPTO-full reaction records. (s1p7:L62-L65)
- A set of commercially purchasable starting materials for determining route leaves. (s1p4:L54-L55, s1p7:L91-L92)

Outputs:

- Training, validation, and test datasets of multi-step routes with nonoverlapping target molecules. (s1p7:L93-L96, s1p7:L98-L99)

## Procedure Guidance

- Remove invalid and duplicate reactions, and construct a reaction network from the retained records. (s1p7:L64-L66)
- Select molecules with out-degree zero as targets, and use dynamic programming and backtracking to identify synthetic routes for each target. (s1p7:L67-L68, s1p7:L90-L92)
- Extract the shortest possible routes whose leaves are starting materials; discard targets synthesized in one step. (s1p7:L91-L95, s1p7:L94-L95)
- Split the remaining target molecules in an 80%/10%/10% training/validation/test ratio, ensuring that targets do not overlap across partitions. (s1p7:L95-L96, s1p7:L98-L99)

## Matters & Troubleshooting

Resources:

- external_asset: USPTO-full — Source reaction dataset required to construct the benchmark.
- external_asset: ZINC — Provides the purchasable-compound inventory used to define starting materials.

Unknowns and limits:

- Reaction validity criteria, duplicate detection rules, and molecule normalization are not specified.
- The dynamic-programming recurrence, backtracking implementation, and cycle handling are not supplied.
- Dataset snapshots, split seed, and treatment of tied shortest routes are unspecified.
