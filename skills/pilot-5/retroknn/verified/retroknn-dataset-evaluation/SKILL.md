---
name: retroknn-dataset-evaluation
description: Evaluate a pretrained RetroKNN bundle on labeled single-product reactions with Syntheseus 0.9.0, saving ranked predictions, top-k exact-match accuracy and mean reciprocal rank.
---

# Evaluate RetroKNN on a labeled reaction fold

Use a prepared, nonempty labeled fold and a compatible pretrained bundle. This workflow evaluates single-step retrosynthesis; it does not obtain benchmark splits or train the model. Record the fold provenance and its overlap with checkpoint training data when interpreting benchmark performance.

## Prepare inputs

The runtime provides Syntheseus 0.9.0 with its RetroKNN integration on CPU. Official interface and setup references are the [versioned evaluation guide](https://github.com/microsoft/syntheseus/blob/v0.9.0/docs/cli/eval_single_step.md) and [installation guide](https://github.com/microsoft/syntheseus/blob/v0.9.0/docs/installation.md).

Place one uniquely discoverable `test.smi`, `test.csv` or `test.jsonl` in a data directory. Discovery uses filename suffixes `*{train,val,test}.{smi,csv,jsonl}` directly within that directory. Keep one format across discovered folds and at most one matching file per fold. Only TEST needs to be present.

| Format | Required content |
|---|---|
| SMI | One reaction SMILES per line: `reactant1.reactant2>reagents>product`; use `>>` for an empty reagent field. No header or blank records. Atom mapping is removed and molecules canonicalized during loading. |
| CSV | Header must include exactly named column `reactants>reagents>production`, containing reaction SMILES handled as for SMI. Other columns are not evaluation labels. |
| JSONL | One JSON object per line with `reactants` and `products` arrays of molecule objects containing `smiles`. Remove atom mapping beforehand; molecules are canonicalized on loading. This loader restores molecule SMILES but discards molecule identifiers. |

Each record must contain exactly one product molecule. Reagent fields are not part of the target reactant comparison. Evaluation reconstructs target reactions without their dataset reaction identifiers. Keep a separate row-to-record-ID mapping to associate saved predictions with the original records; identifiers are not preserved in the prediction output. For example, this is a format illustration, not a benchmark fold:

```json
{"reactants": [{"smiles": "Cc1ccc(Br)cc1"}, {"smiles": "Cc1ccc(B(O)O)cc1"}], "products": [{"smiles": "Cc1ccc(-c2ccc(C)cc2)cc1"}]}
```

Supply an extracted compatible bundle as `model_dir`; weights and retrieval stores are external to the image. The official [USPTO-50K RetroKNN bundle](https://figshare.com/ndownloader/files/45662430) is linked in the [model guide](https://github.com/microsoft/syntheseus/blob/v0.9.0/docs/single_step.md). Point at the directory containing both subdirectories, preserving all index payloads:

```text
model/
  local_retro/
    <unique checkpoint>.pth
    <unique config>.json
    data/atom_templates.csv
    data/bond_templates.csv
    data/template_infos.csv
  knn/
    <unique adapter>.pt
    datastore/data.atom_idx
    datastore/data.bond_idx
    datastore/data.npz
    <any external FAISS index payload files>
```

The `data.npz` includes `atom_output_label` and `bond_output_label`. Keep the checkpoint, adapter, templates and stores together as a compatible bundle. Alternatively, omitting `model_dir` downloads and caches the default checkpoint; cache location defaults to `$HOME/.cache/torch/syntheseus` and can be changed with `SYNTHESEUS_CACHE_DIR`.

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
  syntheseus eval-single-step data_dir=/work/data fold=TEST model_class=RetroKNN model_dir=/work/model num_top_results=50 num_gpus=0 results_dir=/work/results
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).

## Run evaluation

With `data/test.jsonl` (or a supported alternative) and the bundle at `model/`, run from their parent directory:

```bash
syntheseus eval-single-step \
  data_dir=data fold=TEST \
  model_class=RetroKNN model_dir=model \
  num_top_results=50 num_gpus=0 \
  results_dir=results \
  save_outputs=true include_predictions=true resumable=false
```

Paths are relative to the current working directory. The command creates the results directory and saves `results/RetroKNN_<timestamp>.json` after completion. Ordinary mode saves at the end, so an interrupted run has no guaranteed partial prediction artifact.

| Setting | Operational meaning |
|---|---|
| `num_top_results=50` | Request up to 50 ranked reactions; the upstream default is 100. Keep `print_idxs` at or below this value if changing it; default printed ranks are 1, 3, 5, 10, 20, 50. |
| `num_gpus=0` | Required for this CPU image; upstream defaults to one GPU. |
| `batch_size` | Defaults to 16; lower it if memory is insufficient. |
| `skip_repeats=true` | Default: remove repeated predicted reactions, not repeated dataset records. Fewer than the requested predictions may remain. |
| `include_results_modulo_stereo=true` | Optional additional stereo-agnostic metrics; ordinary exact-match metrics remain separately available. |

## Inspect results

Use the saved path from this run. This example reads metrics and the first ranked list; replace the example result filename with the actual timestamped file:

```python
import json
from pathlib import Path

result = json.loads(Path("results/RetroKNN_<timestamp>.json").read_text())
print("samples:", result["num_samples"])
for k in (1, 3, 5, 10, 50):
    print(f"top-{k}:", result["top_k"][k - 1])
print("MRR:", result["mrr"])
first_ranked_list = result["predictions"][0]
for rank, reaction in enumerate(first_ranked_list, start=1):
    print(rank, reaction["reactants"], reaction["products"],
          reaction["metadata"]["ground_truth_match"])
```

| Result field | Meaning and convention |
|---|---|
| `num_samples` | Number of evaluated reaction records. |
| `top_k[k-1]` | Unitless fraction of all records whose first exact match occurs at rank at most k; multiply by 100 for percent. Ranks are one-based; array indices are zero-based. |
| `mrr` | Unitless mean of 1/r for the first matching rank r, with zero contribution if no match exists among returned predictions. Thus it is truncated by the requested prediction limit. |
| `predictions[i][j]` | Reaction at rank j+1 for dataset record i (zero-based). Contains reactants/products as molecule objects and metadata including `ground_truth_match`. Preserve input order to associate predictions with labels. |
| `min_num_predictions`, `max_num_predictions`, `mean_num_predictions`, `median_num_predictions` | Counts of returned reactions per record, including empty lists; mean and median can be fractional. |
| `match_modulo_stereo_top_k`, `match_modulo_stereo_mrr` | Optional metrics after removing stereochemistry from both predictions and labels; null unless enabled. |

Exact equality compares canonicalized reactant and product multisets, including molecule multiplicity and stereochemistry. Reactant order is immaterial. A prediction absent from the supplied label is a benchmark mismatch, not evidence of chemical impossibility. An empty prediction list contributes zero to top-k and MRR; decoding failures can produce such lists. Any retained `metadata.probability` is a model score and is not a normalized distribution over reactions.

Treat exceptions for malformed SMILES, multiple products, ambiguous files, missing bundle members or index-loading errors as failed evaluations. An empty fold is not a valid zero-accuracy run. Check process completion, sample count and prediction-count summaries before comparing runs.
