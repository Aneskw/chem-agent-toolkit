---
name: retrostar-value-model-training
description: Train Retro*'s neural search-value model from prepared packed-fingerprint/value and alternative-reaction .pt datasets, inspect losses, and select a compatible checkpoint.
---

# Train a Retro* search-value model

Use this workflow when compatible training and validation tensors already exist. It trains the value network, not the one-step reaction expansion model; constructing routes or training tensors from raw reaction records is a separate upstream task.

The tool is [Retro* at commit 60e7a24213810706a7075d113704c9320158d726](https://github.com/binghong-ml/retro_star/tree/60e7a24213810706a7075d113704c9320158d726). The image supplies its installed Python package. For obtaining the source or setting up a compatible local environment, use the pinned repository's [official setup instructions](https://github.com/binghong-ml/retro_star/blob/60e7a24213810706a7075d113704c9320158d726/README.md#1-setup-the-environment). Training itself needs only the prepared datasets, not the downloadable planner weights or building-block collection. Use CPU with this runtime.

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
  python -m retro_star.train --gpu -1 --value_root /work/data --value_train train --value_val val --fp_dim 2048 --n_layers 1 --latent_dim 128 --n_epochs 10 --save_folder /work/checkpoints
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).

## Prepare and check inputs

Provide trusted `data/train.pt` and `data/val.pt`, each saved with `torch.save(dictionary, path)`. Both use the same fingerprint and cost conventions. The following is a compatible contract inferred from the loader and loss operations; inspect the supplied payloads before training.

Let `D=2048`, `P=D/8=256`, `N0` be the original value-pair count, `N` the number with strictly positive values, `M` the alternative-reaction count, and `R` the padded reactant-slot count.

| Dictionary key | Compatible representation | Meaning |
| --- | --- | --- |
| `fps` | NumPy `uint8`, shape `(N0,P)` | Packed molecule fingerprints. |
| `values` | Torch `float32`, `(N0,1)` | Target best-route costs; rows with `values[:,0] <= 0` are removed from this pair pool. |
| `reaction_costs` | Torch `float32`, `(M,1)` | Cost of each alternative reaction. |
| `target_values` | Torch `float32`, `(M,1)` | True product route value associated with that alternative reaction. |
| `reactant_fps` | NumPy `uint8`, `(M,R,P)` | Packed fingerprints of its reactants, including padded slots. |
| `reactant_masks` | Torch `float32`, `(M,R)` | Multipliers for reactant values: 1 for included reactants, 0 for padding or excluded contributions. |

Require `N>0`, `M>=N`, `R>=1`, matching leading dimensions within each pool, and finite floating-point values. Do not flatten scalar columns to `(M,)` or `(N0,)`: this breaks indexing or causes unintended broadcasting. These checks prevent shape failures; they do not establish that labels are scientifically correct.

Fingerprints must unpack to exactly `D` bits in NumPy's default `packbits`/`unpackbits` ordering (most significant bit first within each byte). For planner-compatible inputs, use radius-2 Morgan bit fingerprints as implemented in `retro_star.common.smiles_to_fp`, with 2048 bits. Do not pack already packed bytes a second time.

The value-pair pool and alternative-reaction pool are separate. Keep the four alternative-reaction arrays aligned with each other; their products need not match the corresponding row in `fps`. The loader independently permutes that pool and unpacks its first `N` reactant rows. It repeats this at each training epoch; validation alternatives are permuted once at loading. Fingerprints are unpacked into float tensors in memory, so size memory for expanded bits and reactant axes, not just file size.

Costs and values use the same dimensionless additive cost scale. For the study's likelihood objective, reaction cost is negative natural log probability and route value is total route cost; these are not yields or energies. A different cost scale changes the meaning of the fixed training margin and requires upstream justification.

## Train

From a writable working directory containing `data/`, run the installed module:

```bash
python -m retro_star.train \
  --gpu -1 \
  --value_root data --value_train train --value_val val \
  --fp_dim 2048 --n_layers 1 --latent_dim 128 \
  --batch_size 128 --lr 0.001 --seed 1234 \
  --n_epochs 10 --save_epoch_int 1 --save_folder checkpoints
```

Ten epochs and these filenames are example choices. Dataset arguments are stems: the loader appends `.pt`. Module execution runs the same entrypoint as upstream `python train.py` from its `retro_star` source directory, while keeping `train.log` in the writable working directory.

The architecture uses one 128-unit hidden layer, ReLU, dropout 0.1 during training, and scalar `log(1+exp(x))` output. Keeping `fp_dim=2048`, `n_layers=1`, and `latent_dim=128` permits the default planner handoff. Adam uses the supplied learning rate; the defaults shown above match the CLI. Use a fresh output directory and preserve the previous log before another run: `train.log` is overwritten, and matching checkpoint filenames are replaced. The entrypoint starts fresh training; these checkpoints do not contain optimizer state for resuming.

## Inspect results and select a checkpoint

Read `train.log` for `[Epoch E/N]`, training loss, and validation loss. `E` is zero-based. Each loss is an unweighted mean of minibatch losses, not a sample-weighted whole-dataset statistic. The implemented minibatch objective is:

```text
MSE(V(fps), values)
+ mean(max(0, target_values + 7 - reaction_costs
                - sum_over_reactants(mask * V(reactant_fp))) ** 2)
```

The literal margin is 7 and both terms have coefficient 1. This is a squared consistency penalty in the code. Loss is dimensionless on the declared cost scale, not a planning success rate. Nonfinite losses are a failure signal; verify finite labels and inspect model numerical behavior before using checkpoints. The model computes `log(1+exp(x))` directly, so extreme activations can overflow.

Checkpoints contain only `model.state_dict()`. Files are written when `(E+1) % save_epoch_int == 0`, as `checkpoints/epoch_E.pt`. With the example above, the final scheduled file is `epoch_9.pt`; no file is automatically named or selected as best. If the interval exceeds the epoch count, no checkpoint is written. Choose among saved epochs using the logged validation objective and the intended downstream evaluation; lower validation loss alone does not establish improved synthesis planning.

For direct inspection or inference, load a selected file with the identical architecture:

```python
import torch
from retro_star.model import ValueMLP

model = ValueMLP(n_layers=1, fp_dim=2048, latent_dim=128,
                 dropout_rate=0.1, device=torch.device('cpu'))
model.load_state_dict(torch.load('checkpoints/epoch_9.pt', map_location='cpu'))
model.eval()
# External input: unpacked_fps is a float32 tensor shaped (B, 2048).
with torch.no_grad():
    predicted_values = model(unpacked_fps)  # (B, 1), estimated route costs
```

For a separately configured `RSPlanner`, pass `use_value_fn=True`, `save_folder` pointing to this checkpoint directory, `value_model='epoch_9.pt'` (or your selected filename), and `fp_dim=2048`. Its API fixes one hidden layer of width 128; differently shaped checkpoints require a matching custom consumer. Planner use additionally requires the stock collection, template rules, and matching one-step checkpoint from the official README's data download; training does not produce them. An absent dataset, malformed payload, or incompatible checkpoint is an error, not a meaningful empty training result.