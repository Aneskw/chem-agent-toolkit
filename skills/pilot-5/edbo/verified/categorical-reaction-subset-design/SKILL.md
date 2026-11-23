---
name: categorical-reaction-subset-design
description: Generate reduced experimental condition tables from ordered categorical reaction-factor levels using pyDOE2 generalized subset designs.
---

# Categorical reaction subset designs

Use pyDOE2 1.3.0 to select combinations from explicitly supplied factor-level lists. This produces experimental conditions; response modeling, optimization and laboratory execution are separate.

## Runtime environment

Use the preconfigured Docker image:

```bash
docker pull ghcr.io/jinselw/chem-tools:pydoe-v1
```

Execution example (Bash; replace the example filename or arguments for the task):

```bash
docker run --rm \
  --mount "type=bind,source=$(pwd),target=/work" \
  --workdir /work \
  ghcr.io/jinselw/chem-tools:pydoe-v1 \
  python design.py
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).

The official [pyDOE2 1.3.0 package](https://pypi.org/project/pyDOE2/1.3.0/) and [project source](https://github.com/clicumu/pyDOE2) provide acquisition and interface details. Use the declared Python 3.11 environment for the unmodified release.

## Prepare factors

Supply ordered, distinct identities for each factor, with at least two levels per factor. Keep factor order and level order fixed through generation and decoding. Reordering categorical identities changes which physical conditions the same integer design selects. GSD uses counts, not chemical similarity.

| Input | Meaning |
|---|---|
| `factors` | Ordered `(name, ordered_levels)` pairs; labels are unambiguous reagent or condition identities. |
| `levels` | Python integers giving level counts, in factor-column order. |
| `reduction` | Unitless Python integer greater than 1. Larger values request fewer runs; run count is approximately the full factorial size divided by this value, not an exact budget guarantee. |
| `n=1` | Return one design as a two-dimensional array. |

The call assumes combinations of supplied levels are available and has no forbidden-combination input. Resolve such constraints before using the table.

## Generate and save conditions

The labels and reduction below are illustrative caller inputs: three factors with 3, 4 and 6 levels, reduced by 4.

```python
import csv
import json
from pathlib import Path
from pyDOE2 import gsd

factors = [
    ("ligand", ["L1", "L2", "L3"]),
    ("base", ["B1", "B2", "B3", "B4"]),
    ("solvent", ["S1", "S2", "S3", "S4", "S5", "S6"]),
]
reduction = 4
names = [name for name, _ in factors]
if len(set(names)) != len(names):
    raise ValueError("Factor names must be unique")
if not factors or any(len(values) < 2 or
                      len(set(values)) != len(values)
                      for _, values in factors):
    raise ValueError("Each factor needs at least two distinct levels")

levels = [len(values) for _, values in factors]
design = gsd(levels, reduction, n=1)
conditions = [
    [values[int(row[j])] for j, (_, values) in enumerate(factors)]
    for row in design
]
output = Path("conditions.csv")
with output.open("w", newline="", encoding="utf-8") as stream:
    writer = csv.writer(stream)
    writer.writerow(names)
    writer.writerows(conditions)

# Keep the exact decoding map and generation settings with the table.
Path("design-inputs.json").write_text(
    json.dumps({"factors": factors, "reduction": reduction, "n": 1},
               indent=2), encoding="utf-8",
)
print(f"{design.shape[0]} conditions saved to {output.resolve()}")
```

Both files overwrite existing files at those paths. The CSV has one row per selected condition, one column per factor and no added row index. Keep the JSON with it to preserve the original ordering.

## Interpret results and failures

- `design.shape` is `(number_of_runs, number_of_factors)`. Entries are unitless, zero-based indices into each factor's original level list. CSV cells are corresponding identities, with no yield, ranking or probability.
- Inspect the actual row count before committing an experimental budget. A smaller reduction generally requests more runs.
- Invalid integer parameters or failed construction can raise `ValueError`; excessive reduction can produce `reduction too large compared to factor levels`. Correct inputs or choose a smaller reduction and regenerate.
- For complementary designs, `gsd(levels, reduction, n=k)` with `k > 1` returns a list of available matrices sliced to the requested count. Decode each separately with the same ordering; inspect the number returned.

For method details see [Generalized Subset Designs in Analytical Chemistry](https://doi.org/10.1021/acs.analchem.7b00506). Release documentation flags [US9746850B2](https://patents.google.com/patent/US9746850B2/en) for certain commercial processing-facility applications; assess applicability for that use.
