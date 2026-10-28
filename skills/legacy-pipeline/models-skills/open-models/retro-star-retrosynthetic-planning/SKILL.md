---
name: retro-star-retrosynthetic-planning
description: "Call Retro* with its existing one-step model and inventory to propose multistep routes, distinguishing bounded search success from optimality."
license: undetermined
---


# Plan with Retro*

Environment: [pinned Retro* repository and setup](https://github.com/binghong-ml/retro_star/tree/60e7a24213810706a7075d113704c9320158d726). Use its `environment.yml`; install `retro_star/packages/mlp_retrosyn`, `retro_star/packages/rdchiral`, then the repository with editable pip installs as documented. Obtain its linked data archive and place `dataset/`, `one_step_model/`, and `saved_models/` under the source's `retro_star/` package directory. These inventory/templates/weights are external assets, not supplied by this Skill.

Input: target product SMILES, compatible one-step templates/weights and inventory, search budget, optional learned value model. Defaults refer to the installed source's asset layout; pass `starting_molecules`, `mlp_templates`, `mlp_model_dump`, `save_folder` and `value_model` explicitly if using another layout.

## Usage

```python
from retro_star.api import RSPlanner

planner = RSPlanner(gpu=-1, use_value_fn=True, iterations=100, expansion_topk=50)
result = planner.plan('CCCC[C@@H](C(=O)N1CCC[C@H]1C(=O)O)[C@@H](F)C(=O)OC')
if result is None:
    print('No route found within this search')
else:
    print(result['routes'])
    print(result['route_cost'], result['route_len'], result['iter'], result['time'])
```

`gpu=-1` selects the API's CPU mode; nonnegative values select a CUDA device. `expansion_topk` limits single-step proposals per expansion; `iterations` limits search. `use_value_fn=True` requires the learned-value checkpoint. With `False`, the API uses a zero value heuristic.

Output is `None` on failed search, or a dictionary: `succ`, `routes` (serialized route), `route_cost`, `route_len`, `iter`, and `time` (seconds). Reaction AND nodes require all reactants; molecule OR nodes offer alternative reactions. Interpret routes relative to the exact inventory and one-step model used. A bounded run with a learned heuristic neither proves global minimum cost nor proves a failed target unsynthesizable. Verify actual routes/leaf availability before experimental planning.

Source: [RSPlanner constructor and return contract](https://github.com/binghong-ml/retro_star/blob/60e7a24213810706a7075d113704c9320158d726/retro_star/api.py).
