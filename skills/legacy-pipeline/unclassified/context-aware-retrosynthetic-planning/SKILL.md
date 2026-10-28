---
name: context-aware-retrosynthetic-planning
description: "Guide use of an existing context-conditioned retrosynthesis predictor while preserving route ancestry, inventory matching, and separate alternative branches."
license: undetermined
---


# Context-aware retrosynthetic planning

Use when an already configured model explicitly accepts ancestor/path context, rather than only the molecule being expanded. Required: target, frozen starting-material inventory and matching policy, context-aware predictor, and search limits. Model weights, tokenizer and representation-fusion implementation must already be available; the instructions do not turn a product-only predictor into FusionRetro.

## Usage

Maintain each partial route with pending molecules and their ancestor paths. Pop one pending molecule. If it matches the inventory, record a leaf; otherwise provide that molecule and its own ancestors to the model using its actual encoder/decoder interface. Do not include unrelated alternative routes as context.

Each predicted reactant set is an alternative reaction (OR choice); all reactants within that set are required (AND children). Create a separate route branch per alternative. Extend each non-inventory reactant's path, and mark the branch solved only when all leaves are inventory members. Never union starting materials from mutually exclusive alternatives and call the union one solved route.

Reject ancestor cycles, retain failed/invalid expansions, and stop explicitly on configured depth/expansion limits. An exhausted pending queue containing failures is not a solved route. Deduplicate with the same chemistry policy used for inventory matching.

Output: solved routes and their individual starting-material sets, plus unresolved branches with reasons and the actual model/search settings. Example branch record:

```json
{"target":"T", "pending":[{"molecule":"I", "ancestors":["T"]}],
 "inventory_leaves":["A"], "steps":[{"product":"T","reactants":["I","A"]}]}
```

IDs above illustrate bookkeeping, not a callable molecular model. Source: [FusionRetro framework and inference](https://arxiv.org/html/2209.15315v3).
