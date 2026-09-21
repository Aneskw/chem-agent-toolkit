---
name: retro-star-retrosynthetic-planning
description: >
  Draft procedure for planning synthesis routes using an AND-OR tree, estimated synthesis costs, best-first expansion, and a choice between first-solution and admissible optimality stopping conditions. Invoke for: Search backward from a target molecule, expand the frontier molecule with the lowest estimated complete-route cost, propagate updated costs, and stop according to the selected solution criterion. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Retro Star Retrosynthetic Planning

This cited draft describes Search backward from a target molecule, expand the frontier molecule with the lowest estimated complete-route cost, propagate updated costs, and stop according to the selected solution criterion. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p1; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p2; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p3; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p4; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p5; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p6; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p7; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p8; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p9; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p10; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p11; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p12; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p13; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p14; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)
- paper: https://arxiv.org/pdf/2006.15820.pdf (source s1p15; SHA-256 2a568276845af24022d74062b460debb9852d48e3af254bb7862dc0a118e45f9)

## Input & Output

Inputs:

- A target molecule and a set of commercially available starting molecules. (s1p2:L85-L86)
- A one-step retrosynthesis model returning candidate reactions, corresponding reactant sets, and reaction costs. (s1p2:L76-L79)
- Molecule synthesis-cost estimates; use exact costs or valid lower bounds when an optimality guarantee is required. (s1p6:L48-L52, s1p6:L18-L20)

Outputs:

- A proposed reaction route terminating in available starting molecules, if a solution is found. (s1p2:L95-L97, s1p4:L13-L13)

## Procedure Guidance

- Initialize the search with the target as the root. Represent molecules as OR nodes and reactions as AND nodes: one reaction suffices for a molecule, but every reactant is required for a reaction. (s1p4:L56-L59, s1p3:L83-L86)
- Compute reaction numbers recursively: a reaction's cost plus its children's reaction numbers; for a frontier molecule use its synthesis-cost estimate, and for an expanded molecule take the minimum child reaction number. (s1p5:L41-L48)
- Rank frontier molecules using estimated complete-route cost, including incurred reaction costs and estimated remaining synthesis costs. Select the minimum-value frontier molecule. (s1p5:L28-L32, s1p4:L77-L81)
- Call the one-step model for the selected molecule. Add each proposed reaction beneath it and each corresponding reactant beneath that reaction. (s1p4:L87-L91)
- Initialize new-node values and propagate reaction-number changes upward. Stop upward propagation when an ancestor's value does not change, and recompute affected frontier route estimates. Appendix A describes caching reaction-node route estimates and all-node reaction numbers. (s1p5:L89-L91, s1p6:L2-L2, s1p6:L13-L15, s1p10:L17-L18)
- For limited-time planning, return when a solution is found. For the paper's optimality variant, require exact molecule costs or admissible lower bounds and continue until the found route cost is no greater than the best frontier cost estimate. With negative-log-likelihood reaction costs, zero is an admissible molecule-cost lower bound. (s1p6:L18-L22, s1p6:L24-L27, s1p6:L28-L29)

## Matters & Troubleshooting

Resources:

- external_asset: https://github.com/binghong-ml/retro_star — The paper references this implementation repository; no repository files are supplied in the snapshot.

Unknowns and limits:

- No executable implementation, model checkpoints, dependency versions, or invocation interface is supplied.
- The paper writes argmin in its optimal stopping comparison, although the comparison requires a frontier cost value; this notation needs clarification.
- Empty-frontier handling, unsuccessful one-step expansion handling, and tie-breaking are not specified.
- The learned value estimator is not established as admissible.
- Appendix A's UpdateSibling pseudocode updates rn, while the accompanying discussion describes propagation of route estimates; implementation verification is needed.
- Tree search can duplicate intermediate molecules and need not minimize cost over a graph with shared intermediates.
