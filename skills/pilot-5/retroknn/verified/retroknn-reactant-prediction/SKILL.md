---
name: retroknn-reactant-prediction
description: Predict ranked single-step reactant sets from product SMILES with pretrained RetroKNN in Syntheseus, including bundle loading, batched inference and score interpretation.
---

# Predict reactants with RetroKNN

Use Syntheseus 0.9.0's RetroKNN wrapper to combine LocalRetro template predictions, atom/bond nearest-neighbor retrieval and a learned adapter. This workflow starts with product SMILES and a compatible pretrained bundle; training, datastore construction and multistep planning are outside its scope.

## Runtime environment

Use the preconfigured Docker image:

```bash
docker pull ghcr.io/jinselw/chem-tools:retroknn-v1
```

Execution example (Bash; replace the example filename or arguments for the task):

```bash
docker run --rm \
  --mount "type=bind,source=$(pwd),target=/work" \
  --workdir /work \
  ghcr.io/jinselw/chem-tools:retroknn-v1 \
  python predict.py
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).

The runtime uses Syntheseus 0.9.0 with syntheseus-local-retro 0.5.0 and CPU inference. For a local setup, consult the [official tagged installation instructions](https://github.com/microsoft/syntheseus/blob/v0.9.0/docs/installation.md) and the runtime contract for compiled dependencies; the model extra is `syntheseus[retro-knn]==0.9.0`.

## Prepare the model and products

Weights and retrieval stores are external inputs. Obtain the [maintainer-trained USPTO-50K RetroKNN bundle](https://figshare.com/ndownloader/files/45662430), linked in the [official checkpoint table](https://github.com/microsoft/syntheseus/blob/v0.9.0/docs/single_step.md). Extract it and point `model_dir` to the directory containing both `local_retro/` and `knn/`, adjusting any enclosing archive directory. Preserve the matched configuration, templates, weights and stores together:

```text
retroknn-model/
  local_retro/
    <one checkpoint>.pth
    <one configuration>.json
    data/
      atom_templates.csv
      bond_templates.csv
      template_infos.csv
  knn/
    <one adapter checkpoint>.pt
    datastore/
      data.atom_idx
      data.bond_idx
      data.npz
      <any external index payload files>
```

The loader requires exactly one matching checkpoint/configuration file at each indicated level. Keep external FAISS payload files beside their indices; the loader uses same-directory on-disk index resolution. `data.npz` must contain matching `atom_output_label` and `bond_output_label` arrays. Do not substitute a standalone LocalRetro checkpoint for this coupled bundle.

Provide one valid product SMILES per `Molecule`. Its defaults parse with RDKit and canonicalize the SMILES; invalid inputs raise `ValueError`. Reaction classes are not required (`rxn_class_given=False` in the wrapper).

## Run a batch and save results

The following caller code assumes the extracted bundle is under the mounted working directory. Product strings and the requested count are illustrative choices. Instantiate once and reuse the model for subsequent batches.

```python
import json
from pathlib import Path

from syntheseus.interface.molecule import Molecule
from syntheseus.reaction_prediction.inference.retro_knn import RetroKNNModel

product_smiles = ["CC(=O)Oc1ccccc1C(=O)O", "CCOC(=O)c1ccccc1"]
products = [Molecule(smiles) for smiles in product_smiles]
model = RetroKNNModel(model_dir=Path("retroknn-model"), device="cpu")
batch_results = model(products, num_results=50)

records = []
for supplied_smiles, product, reactions in zip(product_smiles, products, batch_results):
    records.append({
        "input_smiles": supplied_smiles,
        "product_smiles": product.smiles,
        "predictions": [
            {
                "rank": rank,
                "reactants_smiles": reaction.reactants_str,
                "reaction_smiles": reaction.reaction_smiles,
                "probability": float(reaction.metadata["probability"]),
            }
            for rank, reaction in enumerate(reactions, start=1)
        ],
    })
Path("predictions.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
```

`batch_results` has one sequence of `SingleProductReaction` objects per input, in input order. `num_results` requests a candidate count per product; it defaults to 100 if omitted. The example writes `predictions.json`, replacing an existing file of that name, and retains products with no predictions as empty lists.

If automatic acquisition is preferred, omit `model_dir`: `RetroKNNModel(device="cpu")` downloads and caches the default checkpoint. Set `SYNTHESEUS_CACHE_DIR` before loading to choose a persistent writable cache, for example a directory under `/work`; otherwise the documented default is `$HOME/.cache/torch/syntheseus`. An uncached load requires network access.

## Interpret and troubleshoot

| Output | Meaning and convention |
|---|---|
| `rank` | Example-generated 1-based position in the returned sequence; preserve model order. |
| `reactants_str` | Dot-separated canonical molecule SMILES from a reactant multiset, serialized in deterministic sorted order; component order is not a ranking. |
| `reaction_smiles` | `reactants>>product`, oriented in the forward chemical direction even though inference starts from the product. |
| `metadata['probability']` | Unitless probability-like prediction score. Scores need not sum to one across reactions; do not interpret them as calibrated synthesis success probabilities. |

The retrieval neighborhood is fixed at 32 in this wrapper; `num_results=50` controls decoded candidates, not neighbor count. Duplicate reactions are removed by default while preserving order. Product-containing-reactant filtering is off by default.

Short or empty sequences can result from failed template decoding, invalid predicted SMILES being discarded, or duplicate removal. Rare decoder `RuntimeError`s become empty results. These outcomes do not establish that synthesis is impossible. Returned candidates are proposed single-step reactant sets, not validated procedures or complete routes.

For initialization failures, first check `model_dir` depth, unique file matches, complete FAISS files and bundle consistency. Missing files, incompatible checkpoints and dependency/import failures are loading errors rather than empty chemical predictions. Keep `device="cpu"` for this runtime; its FAISS package does not supply GPU retrieval.