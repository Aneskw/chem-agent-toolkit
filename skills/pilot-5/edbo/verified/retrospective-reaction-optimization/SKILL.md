---
name: retrospective-reaction-optimization
description: Simulate and compare EDBO reaction optimization campaigns using a prepared numerical domain and a complete table of measured outcomes.
---

# Retrospective reaction optimization with EDBO

Use EDBO to maximize a measured response over a finite, numerically encoded reaction domain. Each selected configuration retrieves an existing measurement; this workflow neither generates missing outcomes nor calculates descriptors.

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

The interface below uses [EDBO 0.1.0](https://pypi.org/project/edbo/0.1.0/). The official [setup entry](https://github.com/b-shields/edbo#installation) documents its Python 3.7.5/PyTorch 1.3.1 environment; consult the [API documentation](https://b-shields.github.io/edbo/index.html) for other modes. This workflow uses CPU execution.

## Prepare the tables

Supply two CSV files without serialized index columns:

| Input | Required content |
| --- | --- |
| `domain.csv` | N rows of unique candidate configurations, with d finite numerical feature columns; no response column. |
| `outcomes.csv` | The same feature columns and exact values, plus a finite numerical `yield` response for every domain row. One outcome per configuration. |

Keep feature order, encoding and scaling identical across tables. Feature units follow the supplied encoding; EDBO does not prepare or scale these features here. Response units are inherited from the input: percentage yield remains percentage yield, and a fractional yield remains a unitless fraction. Do not standardize the response yourself; EDBO standardizes it internally.

Lookup merges on feature values, not row identity or approximate numerical similarity. Reconcile missing/duplicate configurations before simulation; unmatched proposals can disappear from the acquired batch and duplicate matches can expand it. Reset both row indices to consecutive zero-based integers: the lookup uses index labels as positional indices. Keep any human-readable reaction identifiers in a separate mapping keyed by the feature tuple.

## Run a campaign

This example uses random initialization, expected improvement (EI), a batch of five, and four optimization rounds after initialization. These are illustrative settings. The required budget is `batch_size * (iterations + 1)` unique configurations; choose settings within the available domain.

```python
from pathlib import Path
import matplotlib
matplotlib.use("Agg")  # file output without an interactive display
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from edbo.bro import BO

# External inputs: already encoded domain and measured response lookup.
domain = pd.read_csv("domain.csv").reset_index(drop=True)
outcomes = pd.read_csv("outcomes.csv").reset_index(drop=True)
features = list(domain.columns)
assert domain.columns.is_unique and outcomes.columns.is_unique
assert "yield" not in features
assert set(outcomes.columns) == set(features + ["yield"])
outcomes = outcomes[features + ["yield"]]
assert np.isfinite(domain.to_numpy(dtype=float)).all()
assert np.isfinite(outcomes.to_numpy(dtype=float)).all()
assert not domain.duplicated(features).any()
assert not outcomes.duplicated(features).any()
coverage = domain.merge(outcomes[features], on=features, how="left",
                        indicator=True, validate="one_to_one")
assert coverage["_merge"].eq("both").all(), "Missing measured outcomes"

batch_size, iterations = 5, 4
assert len(domain) >= batch_size * (iterations + 1)
output = Path("campaign-output")
output.mkdir(exist_ok=True)

# Fresh optimizer per independent campaign; vary settings here to compare policies.
for seed in [0, 1, 2]:
    bo = BO(domain=domain.copy(), exindex=outcomes.copy(), target="yield",
            acquisition_function="EI", init_method="rand",
            batch_size=batch_size, duplicate_experiments=False, gpu=False)
    bo.simulate(iterations=iterations, seed=seed)
    acquired = bo.obj.results_input()
    assert len(acquired) == batch_size * (iterations + 1), "Incomplete campaign"
    acquired.to_csv(str(output / ("acquired-%d.csv" % seed)), index=False)
    bo.best().to_csv(str(output / ("best-%d.csv" % seed)), index=False)
    bo.plot_convergence(export_path=str(output / ("convergence-%d" % seed)))
    plt.close("all")
```

`simulate()` mutates the optimizer and returns no campaign table. With random initialization it clears previous acquired results, draws the initial batch, then fits and acquires one batch per iteration. `seed` controls initialization; it is not a guarantee of seeding every stochastic operation. Keep fresh instances for separate campaigns. By default, prior updating is disabled; model fitting uses zero restarts, learning rate 0.1 and 100 training iterations. Change simulation settings explicitly when comparing campaigns.

## Read and compare results

| Output | Meaning |
| --- | --- |
| `acquired-*.csv` | Feature rows and measured `yield` acquired during initialization and optimization, restored to input response units. These are lookup measurements, not predictions. |
| `best-*.csv` | Up to five acquired rows sorted by descending measured response; the first row is the best acquired configuration. |
| `convergence-*.svg` | Cumulative maximum measured response by batch (one-based; batch 1 is initialization), plus its successive batch-to-batch increase. Maximum uses input response units; the increase is in those units per batch step. |

Compare the best acquired response at equal measurement budgets across campaigns. When changing batch size, account for the initialization batch as well as optimization rounds. An empty or short acquired table is not evidence of poor chemistry: check lookup coverage, duplicate feature tuples and remaining domain capacity. EDBO has no missing-outcome interpolation in this lookup path. The best acquired value need not be the best value in the full supplied table.