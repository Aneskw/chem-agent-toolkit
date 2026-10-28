---
name: pca-doe-initial-batch
description: Select an initial batch of valid reactions by applying a numerical DOE to one scaled coordinate per component, mapping coordinates back to available levels, and retrieving encoded rows. Use with a prepared EDBO reaction-space Data object when initializing optimization across its full indexed component set.
---

# PCA-coordinate DOE initialization for EDBO

The EDBO DOE example uses an `edbo.utils.Data` reaction space, commonly `BO_express.reaction`: encoded rows are in `.data`, component identifiers in `.base_data`, and the complete component index fields in `.index_headers`. The example module is [`examples/DOE/DOE.py`](https://github.com/b-shields/edbo/blob/9b41eac3f6d9e520547702fd5b0c7ef6441625a4/examples/DOE/DOE.py); retrieve that pinned file and put it on the Python import path as `DOE.py`. It is example code, not an exported `edbo` API.

The pinned EDBO package version is 0.1.0. Follow the pinned [README installation section](https://github.com/b-shields/edbo/blob/9b41eac3f6d9e520547702fd5b0c7ef6441625a4/README.md#installation): create the Python 3.7.5 conda environment, install RDKit, Mordred and PyTorch as shown, then run `pip install edbo`. `DOE.py` additionally imports `pyDOE2`, which EDBO setup metadata does not declare; use the installation instructions in the [official pyDOE2 project README](https://github.com/clicumu/pyDOE2/blob/master/README.md#installation-and-download).

## Inputs and component contract

Pass component keys, not index-header names. The reaction-space builder stores component descriptors in `reaction.descriptors` keyed by the original `component_dict` keys, while it creates index headers from each descriptor base-data column name plus `_index`. In the matching naming convention, use `components = list(reaction.descriptors)` to preserve builder order. Confirm each key uniquely matches its descriptor columns and corresponding index header by substring, as `component_submatrix()` uses substring matching for both. If descriptor names differ from component keys, use the original component keys in the same order as the generated index fields.

Include every indexed component for encoded-row retrieval. Although design construction accepts a subset, `encoded()` compares each selected tuple with the complete `reaction.index_headers` tuple; omitted component values cannot be inferred. The normal path below uses all components in matching source order.

The module selects descriptor columns containing each key, deduplicates component levels, and uses the first principal component when a component has multiple descriptors; with one descriptor it uses that coordinate directly. Coordinates are min-max scaled by default. Each design column represents one component on a 0–1 coordinate, and mapping uses nearest absolute distance to an available level.

## Representative workflow

```python
from DOE import init_design

# reaction is the prepared edbo.utils.Data object.
components = list(reaction.descriptors)  # original component keys, builder order
# Confirm each key matches its intended descriptor columns and index header.
doe = init_design(reaction, components)

doe.lhs(samples=12, seed=7)
# Alternatives: doe.pbd(), or hybrid central-composite/LHS:
# doe.ccd_lhs(ccd_factors=[components[0]], lhs_factors=components[1:],
#             add_samples=5, seed=7, center_fill=False)

doe.get_closest_principles()
selected_levels = doe.experiment_design
doe.encoded()
initial_rows = doe.encoded_design
```

`selected_levels` contains actual component identifiers. `initial_rows` is the corresponding slice from `reaction.data`, suitable as proposed starting rows for optimization; it contains no experimental outcomes. Inspect the identifiers before handing off to the experimental workflow.

For `ccd_lhs`, list every component exactly once across `ccd_factors` and `lhs_factors`. The former receive central-composite axes; the latter receive LHS or midpoint fills. `center_fill=True` fixes the latter at 0.5 for the central-composite portion; `add_samples` adds a separate full-factor LHS block. `pbd()` uses the number of selected components as its factor count and has no sample-count or seed argument.

Nearest-level mapping can assign the same available level to multiple numeric points, yielding duplicate combinations; inspect `selected_levels` for duplicates. `encoded()` uses exact full-index equality and takes the first matching row. Ensure the prepared reaction space has one row per complete index tuple; the example does not disambiguate duplicate full-index matches or guard a missing match.

