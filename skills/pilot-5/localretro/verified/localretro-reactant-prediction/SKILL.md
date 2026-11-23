---
name: localretro-reactant-prediction
description: Predict ranked reactant sets for valid product SMILES with the pretrained LocalRetro model through Syntheseus; use for single-step retrosynthesis without reaction-class conditioning.
---

# Predict reactants with LocalRetro

Use Syntheseus 0.9.0 with its `syntheseus-local-retro==0.5.0` adapter. This workflow returns single-step structural hypotheses, without atom-mapping preparation, reaction conditions, training, or multistep route search.

## Prepare the model and inputs

The image supplies the software. For a compatible local environment, the official [installation guide](https://microsoft.github.io/syntheseus/stable/installation/) documents selecting model extras: `pip install "syntheseus[local-retro]==0.9.0"`. The [versioned setup files](https://github.com/microsoft/syntheseus/tree/v0.9.0) provide the upstream environment baseline; use the runtime contract below for this CPU environment.

Obtain the [LocalRetro USPTO-50K bundle](https://figshare.com/ndownloader/files/42287319) linked in the official [single-step model documentation](https://github.com/microsoft/syntheseus/blob/v0.9.0/docs/single_step.md). It is not included in the image. Extract it and set `model_dir` to the directory with this layout (names of the checkpoint and configuration may vary):

```text
localretro-model/
  checkpoint.pth          # exactly one *.pth
  config.json             # exactly one *.json
  data/
    atom_templates.csv
    bond_templates.csv
    template_infos.csv
```

Keep weights, configuration and template tables together as a compatible bundle. The default bundle was trained by the Syntheseus maintainers on USPTO-50K. Supply valid product SMILES, one product per `Molecule`; no reaction-class input is accepted by this adapter.

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
  python predict_reactants.py
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).

## Run batched prediction

Place the extracted bundle under the mounted directory, or adapt the model path. This example requests ten candidates for each illustrative product and writes JSON without assuming that ten results exist:

```python
import json
from pathlib import Path

from syntheseus.interface.molecule import Molecule
from syntheseus.reaction_prediction.inference.local_retro import LocalRetroModel

product_smiles = ["CC(=O)Oc1ccccc1C(=O)O"]  # replace with your products
products = [Molecule(smiles) for smiles in product_smiles]
model = LocalRetroModel(model_dir=Path("localretro-model"), device="cpu")
results = model(products, num_results=10)

records = []
for supplied_smiles, candidates in zip(product_smiles, results):
    records.append({
        "product_smiles": supplied_smiles,
        "candidates": [
            {
                "rank": rank,
                "reactants_smiles": reaction.reactants_str,
                "reaction_smiles": reaction.reaction_smiles,
                "probability": float(reaction.metadata["probability"]),
            }
            for rank, reaction in enumerate(candidates, start=1)
        ],
    })
Path("predictions.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
```

Alternatively, `LocalRetroModel(device="cpu")` downloads and caches the default bundle on first use. This requires network access and writable cache storage. Set `SYNTHESEUS_CACHE_DIR` before model construction to choose a persistent cache directory; otherwise the default is `$HOME/.cache/torch/syntheseus`. A cache outside `/work` in the example container does not persist after removal.

## Read results

`results[i]` is the candidate sequence for input `products[i]` (Python indices start at zero). The JSON preserves this association, including empty candidate lists.

| Field | Meaning |
|---|---|
| `rank` | Example-generated, one-based position in returned order. |
| `reactants_smiles` | Reactant structures as dot-separated SMILES components. |
| `reaction_smiles` | Structural reaction string, `reactants>>product`. |
| `probability` | Unitless model ranking value from metadata, not a normalized probability distribution over candidates. Do not interpret its sum as one or as a calibrated success probability. |

`num_results` is a requested count per product (default 100 when omitted), not a guarantee. Duplicate reactions are removed by default while preserving order; product-containing reactant sets are not filtered by default. Decoding and filtering can leave fewer candidates or none. The adapter converts certain RDKit decoding `RuntimeError`s into an empty list, so emptiness does not establish chemical impossibility. Other input, loading or inference exceptions should be reported as failures rather than converted to an empty prediction.

Use returned order for ranking and inspect the proposed reactant structures. These are model predictions, not validated synthesis procedures or evidence that a reaction will succeed.