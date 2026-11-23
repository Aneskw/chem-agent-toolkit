---
name: bayesian-reaction-batch-selection
description: Use EDBO to propose successive batches of reaction conditions from finite categorical choices and numerical grids, export designs, and import measured responses.
---

# Select reaction batches with EDBO

Use `edbo.bro.BO_express` for human-in-the-loop maximization over a finite Cartesian reaction space. Laboratory execution and generation of quantum descriptors are external handoffs. Choose grids containing only combinations that can actually be run; this interface enumerates their product and does not impose conditional feasibility constraints.

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
  python campaign.py
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).

The interface here is [EDBO 0.1.0](https://pypi.org/project/edbo/0.1.0/). Its [official setup entry](https://github.com/b-shields/edbo#installation) documents the legacy Python 3.7.5 / PyTorch 1.3.1 stack; modern Python compatibility is not established. The supplied runtime uses CPU computation. No external dataset is required for the example.

## Prepare the space

| Input | Contract |
|---|---|
| `reaction_components` | Dictionary of component names to finite choices. Maintain ordering and values throughout the campaign so experiment IDs retain their meaning. Space size grows as the product of choice counts. |
| `encoding` | Matching keys: `'ohe'` for categories, `'numeric'` for numerical grids. Omitted keys default to one-hot encoding. Numerical values have user-defined units; EDBO does not convert them. |
| `descriptor_matrices` | Optional dictionary of pandas DataFrames keyed by component. First column identifies choices; remaining columns contain descriptors. A table overrides that component's encoding **and supplies its choice list**, so filter it to the intended choices before construction. Keep identifiers unique, complete and stable; use distinct descriptor column names across components. |
| `target` | Response column name, here `'yield'`. EDBO maximizes it. Use one consistent response convention; this example defines yield as percent (0–100), not a fraction. |
| `batch_size` | Number of experiments per initialization/proposal, here 3 as an illustrative choice. Keep it within the remaining distinct encoded conditions. |

`BO_express` cleans nonnumeric/constant features, decorrelates component descriptors (default threshold 0.95), and min–max scales the encoded domain. These encoded coordinates are unitless; exported conditions retain original values. Distinct labels can become indistinguishable after preprocessing; duplicate exclusion operates on encoded conditions.

## Initialize and export

The choices below illustrate an interface, not a validated reaction recipe. Replace them with the caller's feasible choices and units.

```python
from edbo.bro import BO_express

components = {
    'base': ['K2CO3', 'Cs2CO3'],
    'solvent': ['DMF', 'DMSO'],
    'temperature_C': [60, 80, 100],
}
encoding = {'base': 'ohe', 'solvent': 'ohe', 'temperature_C': 'numeric'}

bo = BO_express(
    reaction_components=components,
    encoding=encoding,
    acquisition_function='EI',
    init_method='rand',
    batch_size=3,
    target='yield',
)
bo.init_sample(seed=0)
print(bo.get_experiments())
bo.export_proposed('init.csv')
bo.save('awaiting-init.pkl')
```

For precomputed descriptors, read the caller's CSV with `pandas.read_csv`, filter rows to the desired identifiers, then supply, for example, `descriptor_matrices={'base': base_descriptors}` in the same constructor. Keep `base` in `reaction_components`. The table's first column is data, not a pandas row index. Descriptor generation and physical units of each supplied descriptor must be documented by its producer.

`init_sample` returns encoded points and sets the current proposal. Call it once when starting: random initialization clears loaded results. `get_experiments()` maps the current proposal back to original conditions, with headers such as `base_index` and `temperature_C_index`. The DataFrame row index is the zero-based position in the fixed reaction domain; it is not the proposal's rank.

## Measure, import and propose again

Run the exported experiments externally. Replace every `<Enter Response>` in the final `yield` column with measured numeric percent yield, saving as `init-measured.csv`. Preserve the first CSV column of experiment IDs, the condition columns and the final response position. Do not regenerate sequential IDs or append notes after the response. `add_results` selects encoded rows by the IDs, not by validating the textual conditions.

Continue in the same session, or restore the checkpoint in a new compatible process:

```python
from edbo.bro import BO_express

bo = BO_express()
bo.load('awaiting-init.pkl')  # Load only a trusted campaign checkpoint.
bo.add_results('init-measured.csv')
print(bo.obj.results_input())  # Encoded features plus unstandardized responses.
bo.run()
print(bo.get_experiments())
bo.export_proposed('next.csv')
bo.save('awaiting-next.pkl')
```

After the next external measurements, load `awaiting-next.pkl` if needed, call `add_results('next-measured.csv')`, then `run()`, `get_experiments()`, `export_proposed('round2.csv')` and `save('awaiting-round2.pkl')`. Import each measured batch once: imports append to previous observations and do not deduplicate them. Use distinct round filenames; exports and saves overwrite their destinations. Keep checkpoints and measured CSVs together.

For an existing-data start, construct the same fixed space and call `add_results` on correctly indexed measurements, then `run`; skip `init_sample`. Keep `run()`'s default `append=False` for laboratory handoffs.

## Inspect the results

- `run()` fits the surrogate and replaces the current proposal. EI uses Kriging believer batching; its temporary predicted responses are not laboratory measurements. Proposals identify conditions to evaluate and do not establish an improvement.
- `export_proposed` writes an indexed CSV of original conditions plus a response placeholder. Neither it nor `run()` measures yield. Internal responses are standardized; `bo.obj.results_input()` returns observations in the input response scale, while its features remain encoded. Its internal row labels are not the original experiment IDs; retain the exported CSVs for that mapping.
- `add_results` drops rows with any missing field. Check the imported observation count before proposing again; unresolved placeholders or nonnumeric responses must be corrected. An out-of-range or altered ID can fail or silently map to the wrong condition.
- The default excludes previously observed encoded points and points already selected in the batch. Stop or reduce the batch when the eligible space is exhausted; EI batching can fail when no point remains rather than return a clean empty batch. Treat a short/empty proposal as a reason to inspect remaining distinct conditions before laboratory handoff.
- A printed `Defaulting to previous iterations hyperparameters...` message indicates a Kriging believer fit fallback. Inspect the accompanying exception and model fit before relying on that batch.
