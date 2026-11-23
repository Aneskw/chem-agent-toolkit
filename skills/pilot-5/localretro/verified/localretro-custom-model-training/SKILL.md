---
name: localretro-custom-model-training
description: Derive LocalRetro templates from curated atom-mapped reaction splits, label a custom corpus, train a model and decode held-out retrosynthesis predictions.
---

# Train and decode a custom LocalRetro model

Start with curated, atom-mapped train/validation/test reactions. Collection and atom mapping are external preparation. Template classes are dataset-specific: preserve the template tables, configuration and checkpoint together.

## Runtime environment

Use the preconfigured Docker image:

```bash
docker pull ghcr.io/jinselw/chem-tools:retroknn-v2
```

After preparing the writable corpus below, run template extraction (Bash):

```bash
docker run --rm \
  --mount "type=bind,source=$(pwd),target=/work" \
  --workdir /work/LocalRetro/preprocessing \
  ghcr.io/jinselw/chem-tools:retroknn-v2 \
  python Extract_from_train_data.py -d my_reactions
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).

The image supplies CPU execution and author source at `/opt/localretro/src`, pinned to `eba83e72efabeb854fec86c865e8743c295a8a1e`. Official acquisition/setup: [kaist-amsg/LocalRetro](https://github.com/kaist-amsg/LocalRetro/tree/eba83e72efabeb854fec86c865e8743c295a8a1e). Use that author script tree, separate from the installed Syntheseus adapter. The prepared source replaces the two removed pandas `DataFrame.append` calls in `combine_preprocessed_data` with `pd.concat`, preserving operand order and `ignore_index=True`. A local checkout using pandas 2 needs those same replacements.

LocalRetro is CC BY-NC-SA 4.0; commercial use requires prior written approval from the copyright holder. Custom training needs no pretrained checkpoint or benchmark bundle.

## Prepare a writable corpus

Inside the environment, copy the prepared source into a fresh writable directory. Here `/work/inputs/` contains caller-supplied CSVs and `my_reactions` is an example dataset name.

```bash
cd /work
cp -R /opt/localretro/src LocalRetro
cd LocalRetro
mkdir -p data/my_reactions data/saved_graphs
cp /work/inputs/raw_train.csv /work/inputs/raw_val.csv /work/inputs/raw_test.csv data/my_reactions/
```

Each CSV must contain the exact column `reactants>reagents>production`, including that spelling. Cells contain atom-mapped `reactants>>products` strings, with dot-separated components within either side. Do not supply three-field reagent-separated strings. Preserve row order: test IDs refer to zero-based rows of `raw_test.csv`.

Use a fresh dataset name when changing reactions/settings. Preprocessing reuses existing `preprocessed_<split>.csv`; graph loading independently reuses `data/saved_graphs/<dataset>_dglgraph.bin` and `<dataset>_test_dglgraph.bin`. For a deliberate rebuild under the same name, remove the affected generated split files and both graph caches, then regenerate preparation and downstream artifacts. Existing checkpoints prompt for overwrite/continue/new name. Continue loads model weights with a newly initialized optimizer and scheduler. The normal path assumes no existing checkpoint.

## Extract templates and label reactions

Working directories matter because upstream resolves paths relative to them.

```bash
cd /work/LocalRetro/preprocessing
python Extract_from_train_data.py -d my_reactions
python Run_preprocessing.py -d my_reactions
```

Defaults are retrosynthesis, stereo-aware extraction, minimum template frequency 1 and maximum 8 edits for labeling. Keep extraction and labeling settings consistent. Integer `--min-template-n` exists in both scripts: it filters exported template classes during extraction and controls the labeling mask.

Inspect logged reaction IDs, exceptions, template problems and coverage before training. Coverage is the labeling success counter divided by split length, not a guarantee of correct nonempty labels. Too many edits may indicate wrong mapping. Exceptions may be caught while processing continues; inspect generated rows as well as exit status.

| File under `data/my_reactions/` | Meaning |
| --- | --- |
| `atom_templates.csv`, `bond_templates.csv` | SMARTS templates, occurrence counts and separate one-based `Class` IDs. Model class 0 means no edit. |
| `template_infos.csv` | Edit-site, hydrogen, charge and stereochemistry change metadata used by decoding. |
| `preprocessed_train.csv`, `preprocessed_val.csv`, `preprocessed_test.csv` | `Reactants`, `Products`, `Reagents`, serialized `Labels` and training-template `Frequency`. Empty labels/frequency 0 can indicate failed or uncovered reactions. |
| `labeled_data.csv` | Concatenated train/val/test rows with `Split` and `Mask`. `Mask=1` when frequency meets the threshold; `Mask=0` assigns all sites no-edit labels rather than dropping rows. |

Labels are `('a' or 'b', site_index, template_class)`. Site indices are zero-based in the processed product: RDKit atom order for atoms; bond iteration order with both directed pairs for bonds. Do not independently reorder products or labels. Upstream uses `eval` on several generated literal fields; use trusted locally generated artifacts.

## Train, predict and decode

```bash
cd /work/LocalRetro/scripts
python Train.py -d my_reactions --batch-size 16 --num-epochs 50 --patience 5 --learning-rate 0.0001
python Test.py -d my_reactions
python Decode_predictions.py -d my_reactions
```

These training values are upstream defaults. Validation-loss early stopping saves `models/LocalRetro_my_reactions.pth`; Train reloads the best checkpoint for its final test-loss report. The default architecture is `data/configs/default_config.json`, using GeLU. If changing `--config`, provide a filename under `data/configs/` and use the same configuration for Train and Test.

Avoid one-batch toy corpora: epoch loss reporting divides by the zero-based last batch index. Each train/validation/test loader needs at least two batches; training also skips singleton batches. The default test writer assumes at least 100 nonzero-class atom-site candidates and 100 bond-site candidates for every product. Small template vocabularies/products can violate this assumption, causing incorrect edit-type assignment or indexing failures. Check corpus suitability before a long run. Test and Decode numeric override arguments lack integer conversion in this revision; leave their defaults unchanged on this path.

Decode uses eight worker processes and returns up to 50 candidates from the 100 raw predictions. Files are relative to `/work/LocalRetro`:

- `outputs/raw_prediction/LocalRetro_my_reactions.txt`: test ID, canonical unmapped product SMILES and ranked `(edit_type, site_index, template_class, score)` records.
- `outputs/decoded_prediction/LocalRetro_my_reactions.txt`: no header; tab-separated zero-based test ID followed by Python-literal `(reactant_smiles, score)` tuples.

Read decoded results from the source-tree root:

```python
import ast
from pathlib import Path

path = Path('outputs/decoded_prediction/LocalRetro_my_reactions.txt')
with path.open() as handle:
    for line in handle:
        fields = line.rstrip('\n').split('\t')
        test_id = int(fields[0])
        candidates = [ast.literal_eval(value) for value in fields[1:]]
        # Each candidate is (reactant SMILES, unitless score).
```

Scores are per-site softmax values over template classes, merged across atom/bond predictions, rounded to three decimal places by Test and retained during decoding. They are not normalized probabilities over complete reactant sets. Decode omits `None` results and repeated identical SMILES-score tuples; different scores can retain the same SMILES. An ID-only row means no candidate survived decoding. Some decoder errors occur outside its exception handler and terminate execution; missing/truncated output is not an empty prediction result.

Optional class filtering requires row-aligned `class_train.csv` and `class_test.csv`, each with a `class` column using supported integer classes 1–10. Extraction produces `template_rxnclass.csv`; Decode writes class-filtered candidates to `outputs/decoded_prediction_class/LocalRetro_my_reactions.txt`. Without class inputs, that file contains IDs only. Precursor suggestions and losses are model outputs; assess held-out chemical accuracy separately.
