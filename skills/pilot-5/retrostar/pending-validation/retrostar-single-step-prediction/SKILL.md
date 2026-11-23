---
name: retrostar-single-step-prediction
description: Generate ranked immediate reactant sets from a product SMILES using Retro*'s pretrained template-based MLP and matching ordered template file, without multistep planning or stock checking.
---

# Predict immediate precursors with Retro*

Use the bundled `mlp_retrosyn` and `rdchiral` implementation at [Retro* commit 60e7a24213810706a7075d113704c9320158d726](https://github.com/binghong-ml/retro_star/tree/60e7a24213810706a7075d113704c9320158d726). This workflow applies predicted reaction templates to one product; it does not establish experimental feasibility or availability of precursors.

## Prepare inputs

The image supplies the software. For compatible local setup, use the pinned repository's [setup instructions](https://github.com/binghong-ml/retro_star/blob/60e7a24213810706a7075d113704c9320158d726/README.md), including its bundled `mlp_retrosyn` and `rdchiral` packages.

Supply these external inputs in the mounted working directory:

| Input | Required convention |
| --- | --- |
| Product | One RDKit-readable product SMILES string; retain intended stereochemistry. |
| Checkpoint | Pretrained `saved_rollout_state_1_2048.ckpt` or a compatible checkpoint with the same architecture and fingerprint dimension. The loader expects a state dictionary whose keys have a seven-character DataParallel prefix, which it strips. |
| Templates | Matching `template_rules_1.dat`: one reaction SMARTS template per line, in the original training-label order. Do not sort, deduplicate, add or remove lines. |

The authors' [data archive](https://www.dropbox.com/s/ar9cupb18hv96gj/retro_data.zip?dl=0), linked from the setup instructions, is an acquisition entrypoint for pretrained models. The checkpoint and templates are not included in the image. This path starts with a locally obtained matching pair; if acquisition fails, obtain that pair before running. An arbitrary PyTorch checkpoint is not interchangeable.

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
  python predict.py
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).

## Predict and save candidates

Adapt the paths and product below. The example uses CPU execution (`device=-1`) and a 2048-bit radius-2 chiral Morgan fingerprint, matching the named checkpoint. `topk` counts selected templates, not returned reactant sets; `run` defaults to 10, while this example selects up to 50.

```python
import json
from pathlib import Path

import torch
from rdkit import Chem
from mlp_retrosyn.mlp_inference import MLPModel

checkpoint_path = Path("inputs/saved_rollout_state_1_2048.ckpt")
template_path = Path("inputs/template_rules_1.dat")
product_smiles = "CC(=O)NC1=CC=C(O)C=C1"  # illustrative product

if Chem.MolFromSmiles(product_smiles) is None:
    raise ValueError("Invalid product SMILES")

model = MLPModel(str(checkpoint_path), str(template_path),
                 device=-1, fp_dim=2048)
topk = min(50, len(model.idx2rules))
if topk < 1:
    raise ValueError("No templates loaded")

with torch.no_grad():
    result = model.run(product_smiles, topk=topk)

rows = []
if result is not None:
    for rank, (reactants, score, template) in enumerate(
        zip(result["reactants"], result["scores"], result["template"]), start=1
    ):
        rows.append({"rank": rank, "reactants": reactants,
                     "score": score, "template": template})

with open("precursors.json", "w") as handle:
    json.dump({"product": product_smiles, "candidates": rows},
              handle, indent=2)
print("Retained candidates:", len(rows))
```

Reuse the initialized model for additional products. Keep `1 <= topk <= len(model.idx2rules)`; template application can yield zero, one or multiple reactant sets, so candidate count need not equal `topk`.

## Read results

The successful return is a dictionary of three aligned lists, sorted by descending merged score:

| Field | Meaning |
| --- | --- |
| `reactants` | Each string is one precursor set, with component SMILES separated by dots. Components are lexically sorted before duplicate merging. |
| `scores` | Unitless relative weights summing to one across retained candidates. Each selected template's softmax weight is divided equally among its generated outcomes; weights for identical component-sorted sets are summed and then renormalized. These are not calibrated reaction-success probabilities. |
| `template` | Reaction SMARTS associated with the candidate. After merging, only the first contributing template is retained, not all contributors. |
| Saved `rank` | Example glue: one-based position in the returned ordering. |

`None` means no selected template produced a retained reactant set; the example saves an empty candidate list. It does not prove that no synthesis exists. Template-application `ValueError` exceptions are silently skipped upstream; invalid input, checkpoint mismatch, file errors and other exceptions can still propagate. Treat these as failures, not empty predictions. Inspect `precursors.json` for proposals and use separate chemical evaluation or planning for feasibility, stock availability and subsequent steps.
