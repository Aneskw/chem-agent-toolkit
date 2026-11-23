---
name: retrostar-route-planning
description: Plan multistep retrosynthetic routes with Retro* from target SMILES, supplied building blocks and matching pretrained model assets.
---

# Plan routes with Retro*

Use Retro* to propose a route whose terminal molecules occur in a supplied stock collection. This capability covers inference and route inspection; model training and laboratory validation are separate tasks.

## Prepare inputs

The runtime uses [Retro*](https://github.com/binghong-ml/retro_star/tree/60e7a24213810706a7075d113704c9320158d726) commit `60e7a24213810706a7075d113704c9320158d726` and its bundled `mlp_retrosyn` and `rdchiral`. The [official README](https://github.com/binghong-ml/retro_star/blob/60e7a24213810706a7075d113704c9320158d726/README.md) supplies local setup instructions. Use the declared runtime for the historical checkpoint interface.

Model assets are external. Obtain them through the README's [author-provided data archive](https://www.dropbox.com/s/ar9cupb18hv96gj/retro_data.zip?dl=0), or supply compatible local assets:

| Input | Required format or relationship |
|---|---|
| Target | Valid SMILES string, including intended stereochemistry. |
| Stock | `.csv` with a `mol` column of SMILES, or `.pkl` containing a membership-testable collection of SMILES. CSV rows become a set. |
| One-step model | `template_rules_1.dat` and matching `saved_rollout_state_1_2048.ckpt`; keep template ordering and checkpoint paired. |
| Value model | `best_epoch_final_4.pt` in `save_folder` when `use_value_fn=True`; default fingerprint width is 2048. |

Stock membership is exact string membership; the loader does not canonicalize stock or target strings. Prepare stock with conventions compatible with the supplied templates and chemistry runtime. Equivalent alternative SMILES may fail to match. Load only trusted pickle/checkpoint files.

The example uses explicit paths under the mounted working directory. Alternatively, place `dataset/`, `one_step_model/` and `saved_models/` under the installed `retro_star/` package for its default paths. The archive is an acquisition entrypoint; its payload and checkpoints must be supplied and readable by the runtime.

## Runtime environment

Use the preconfigured Docker image:

```bash
docker pull ghcr.io/jinselw/chem-tools:edbo-v2
```

Execution example (Bash; replace the example filename or arguments for the task):

```bash
docker run --rm \
  --mount "type=bind,source=$(pwd),target=/work" \
  --workdir /work \
  ghcr.io/jinselw/chem-tools:edbo-v2 \
  python plan_routes.py
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).

## Plan and save a route

Adapt the target and asset paths in this ordinary Python code. The search settings below are example choices. Construct the planner once to reuse loaded models across targets.

```python
import json
from pathlib import Path
from retro_star.api import RSPlanner

assets = Path("assets").resolve()
planner = RSPlanner(
    gpu=-1,
    starting_molecules=str(assets / "stock.csv"),
    mlp_templates=str(assets / "one_step_model/template_rules_1.dat"),
    mlp_model_dump=str(assets / "one_step_model/saved_rollout_state_1_2048.ckpt"),
    use_value_fn=True,
    save_folder=str(assets / "saved_models"),
    value_model="best_epoch_final_4.pt",
    iterations=100,
    expansion_topk=50,
    viz=False,
)
target = "CCCC[C@@H](C(=O)N1CCC[C@H]1C(=O)O)[C@@H](F)C(=O)OC"
result = planner.plan(target)

if result is None:
    print("No route found within this search.")
else:
    print(result["routes"])
    print("Reaction count:", result["route_len"])
    print("Route cost:", result["route_cost"])
    print("Search seconds:", result["time"])
Path("route-result.json").write_text(
    json.dumps({"target": target, "result": result}, indent=2),
    encoding="utf-8",
)
```

| Option | Meaning and default |
|---|---|
| `gpu=-1` | CPU. The API's one-step model is explicitly loaded on CPU. |
| `iterations` | Search-loop limit, default 500; it is not a wall-time limit. Search can end earlier. |
| `expansion_topk` | Number of highest-scoring templates attempted per expansion, default 50; not a route count. Must fit the loaded model's template count. |
| `use_value_fn` | Default False: zero heuristic, with no value checkpoint needed. True loads the learned value model. |
| `viz`, `viz_dir` | Default False and `"viz"`. True renders Graphviz PDFs for the search tree and, on success, route. Use a distinct directory per target/call: this API uses molecule ID 0 for filenames and repeated calls can overwrite them. |

## Interpret the result

A successful call returns a dictionary; an unsuccessful search returns `None`. Missing files, invalid model assets or invalid inputs can raise exceptions and should be corrected before treating a run as a search failure.

| Key | Meaning |
|---|---|
| `succ` | True when a complete stock-terminating route is found. |
| `time` | Elapsed planning-call time in seconds; excludes planner construction/model loading. Includes visualization when enabled. |
| `iter` | Search-loop iterations entered, including an iteration that terminates for no open nodes; 0 when target already belongs to stock. |
| `routes` | One serialized route string, despite the plural name. |
| `route_len` | Number of reaction nodes in the route, including branches; not longest-path depth. |
| `route_cost` | Unitless sum of reaction costs, each `-ln(clip(score, 0.001, 1))`. Lower means lower model-derived cost. |

Each reaction is serialized as `product>score>reactant1.reactant2`, with reactions joined by `|`. Its score is `exp(-reaction_cost)`, printed to four decimal places, so it reflects clipping and rounding. The one-step model normalizes scores over its returned reactant proposals after merging duplicates; these are not calibrated experimental success probabilities. The serialization omits template identifiers and does not encode stoichiometric multiplicity: expansion deduplicates identical reactant strings.

If the target is already in stock, a successful zero-reaction result contains the target SMILES alone, with zero cost and length. Handle this before splitting reaction fields.

For `None`, review stock-string compatibility and asset pairing, then consider increasing iterations or template top-k within model limits. Failure can reflect exhausted nodes or restricted expansion as well as the iteration bound. A found route is a computational proposal, and bounded search does not establish global optimality, experimental feasibility or reaction conditions.
