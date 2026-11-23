---
name: batch-reaction-optimization
description: Use EDBO to select successive batches of reaction conditions from component grids and measured responses, with optional precomputed descriptors.
---

# Batch reaction optimization with EDBO

Use `edbo.bro.BO_express` to maximize one measured response over a finite combinatorial reaction space. Experimental execution and measurement happen externally. The workflow uses EDBO 0.1.0 on CPU. Official acquisition and interface entrypoints are [PyPI 0.1.0](https://pypi.org/project/edbo/0.1.0/), the [upstream setup instructions](https://github.com/b-shields/edbo#installation), and [documentation](https://b-shields.github.io/edbo/index.html).

## Runtime environment

Use the preconfigured Docker image:

```bash
docker pull ghcr.io/jinselw/chem-tools:edbo-v1
```

Execution example (Bash; replace the example filename or arguments for the task):

```bash
docker run --rm \
  --mount "type=bind,source=$(pwd),target=/work" \
  --workdir /work \
  ghcr.io/jinselw/chem-tools:edbo-v1 \
  python optimize.py
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).

## Prepare the search space

| Input | Contract |
|---|---|
| `reaction_components` | Dictionary of component names to discrete choices; all combinations are enumerated. Include only combinations suitable for experimental execution. Numeric grids use caller-defined, consistent units. |
| `encoding` | Matching component keys: `ohe` for categories, `numeric` for numerical grids. Unspecified keys default to one-hot encoding. |
| `descriptor_matrices` | Optional dictionary of pandas DataFrames. First column contains unique component identifiers; subsequent columns contain numerical features. A matrix overrides that component's encoding and its rows define the choices used. The component key must still appear in `reaction_components`. |
| `target` | Response column name. EDBO maximizes it; use a consistently transformed response if the physical objective is minimization. EDBO assigns no physical units. |
| `batch_size` | Number of initial and subsequent experiments. Keep within the available distinct encoded conditions. |

BO_express cleans and decorrelates features (default correlation threshold 0.95), scales retained features to the unit hypercube, and selects model priors automatically. Check the resulting space when descriptors remove distinctions between choices. Keep the same component order, descriptor tables and grids throughout a campaign.

For molecular encoding, `smiles` computes Mordred descriptors from SMILES using RDKit/Mordred in the runtime. `resolve` additionally contacts the NIH name resolver; failed resolution or descriptor generation can trigger interactive prompts. The normal path below uses local encodings and requires no resolver access.

## Initialize and export a batch

These choices and units are illustrative. Replace them with the user's actual experimental domain.

```python
from edbo.bro import BO_express

components = {
    'base': ['DBU', 'potassium carbonate'],
    'solvent': ['THF', 'toluene'],
    'temperature_C': [25, 40, 60],
    'concentration_M': [0.1, 0.2],
}
encoding = {
    'base': 'ohe', 'solvent': 'ohe',
    'temperature_C': 'numeric', 'concentration_M': 'numeric',
}

# Optional: descriptors = {'base': pandas.read_csv('base_descriptors.csv')}
# That CSV has an identifier first, then numerical descriptor columns.
descriptors = {}
bo = BO_express(
    reaction_components=components, encoding=encoding,
    descriptor_matrices=descriptors,
    target='yield_percent', batch_size=4,
    init_method='rand', acquisition_function='EI',
)
bo.init_sample(seed=0)
bo.export_proposed('init.csv')
print(bo.get_experiments())
bo.save('campaign.pkl')
```

`init.csv` contains readable component values, a first-column experiment index, and final-column `<Enter Response>` placeholders. Indices are zero-based positions in the constructed domain, not laboratory run numbers. Preserve them exactly; do not renumber rows or rebuild a changed domain. Replace placeholders with numeric measured yields in percent for this example. Keep the response as the final column and retain the exported headings. Do not append laboratory annotations after the response.

## Import measurements and propose the next batch

After external experiments, continue with the same object, or restore its state in a later session:

```python
from edbo.bro import BO_express

bo = BO_express()
bo.load('campaign.pkl')  # Load only a trusted campaign state (dill/pickle).
bo.add_results('init.csv')  # Now contains actual measurements.
bo.run()                  # Fits the model and selects the next batch.
bo.export_proposed('next.csv')
print(bo.get_experiments())
bo.acquisition_summary().to_csv('next_predictions.csv')
bo.best().to_csv('best_observed.csv')
bo.save('campaign.pkl')
```

Repeat `add_results('next.csv')`, `run()`, export to a new batch filename, and save after each measured batch. Import each batch once: `add_results` appends to existing observations without deduplicating imports. It drops rows containing missing values, uses the first column as positional indices to recover encoded conditions, and takes only the final column as the response. Edited condition labels do not remap those indices. Remove unmeasured rows or leave missing responses; never import placeholder strings as measurements. Confirm that the imported observation count matches the intended measured rows before fitting (`len(bo.obj.results)`).

Call `init_sample()` only at campaign initialization: non-external initialization clears accumulated results. `run()` defaults to `append=False`, appropriate for laboratory handoffs; it proposes experiments without manufacturing observations. Previously observed encoded conditions are excluded by default. Stop or reduce the batch size before exhausting the remaining distinct domain; a selection error or undersized batch is not a scientific convergence criterion.

## Read the results

- `get_experiments()` returns the current proposed batch in original categories, SMILES or numerical values, indexed by domain position.
- `acquisition_summary()` is available after `run()`. It contains encoded, scaled features plus `predicted <target>` (mean in the supplied response units) and `variance` (model posterior variance in squared response units). For this example these are percent and percent squared. The default GP variance comes from the latent model posterior; it is not a measured error bar or a laboratory result. Join readable conditions by the shared proposal index if needed.
- `best()` returns up to five observations ranked by descending response, with encoded features and responses in original units. Its observation labels are not the exported domain indices; retain the measured CSVs as the readable experimental record.

A prediction does not establish yield or chemical feasibility. Failed imports, missing measurements, empty observations, or non-finite model outputs require inspecting the data and fit before another experimental handoff.
