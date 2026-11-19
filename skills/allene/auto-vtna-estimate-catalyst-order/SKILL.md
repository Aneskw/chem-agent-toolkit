---
name: auto-vtna-estimate-catalyst-order
description: Estimate catalyst reaction order from prepared concentration-time experiments with varying catalyst loading using Auto-VTNA; inspect normalized overlays and export order-search results.
---

# Catalyst-order estimation with Auto-VTNA

Use sequential VTNA to find the catalyst order that best overlays measured product concentration profiles. Compare experiments differing in initial catalyst concentration with other starting conditions controlled. Kinetic measurements and concentration calibration are supplied inputs; an overlay supports kinetic interpretation, not proof of a catalytic mechanism.

## Environment and inputs

Use **Auto-VTNA 1.2.4** from [official PyPI](https://pypi.org/project/auto-vtna/1.2.4/) and Python 3.11, a declared supported interpreter. The runtime installation entry is `python -m pip install auto-vtna==1.2.4`. Dependencies include pandas, openpyxl, matplotlib and fitting libraries; the example uses the Python API without launching the GUI. [Official project](https://github.com/ddalland/Auto-VTNA).

Prepare `kinetics.xlsx` with one experiment per sheet and no unrelated sheets. Each sheet becomes a pandas DataFrame, keyed by sheet name.

| Field | Preparation |
| --- | --- |
| First column, e.g. `time_s` | Numeric time, strictly increasing and starting at zero in each experiment. |
| `cat` | Catalyst concentration at every recorded time. A constant column requires a justified constant-concentration assumption; loading percentages are not concentrations. Use positive catalyst concentrations, with every adjacent-pair average above `1e-10` in the supplied numeric concentration unit for this combined search-and-export path. |
| `P` | Measured product concentration with a nonflat reaction-progress profile; zero initial product is allowed. |
| All sheets | Identical string column headings and column order; numeric finite values, no missing cells or negative concentrations. One concentration unit and one time unit throughout. Different numbers of time points are allowed. |

The names and units below are adaptable example choices: `cat`, `P`, mol/L and seconds. Plot labels do not convert units. Do not fabricate catalyst profiles from product measurements.

The interval-average threshold keeps the search and exported overlay consistent: in 1.2.4 automatic search replaces only exact-zero averages by `1e-10`, whereas `Normal_VTNA` floors every average at or below `1e-10`. The checker does not check this threshold; the calculation block below does. If needed, convert all concentration columns consistently to a suitable unit, update plot labels and saved unit metadata, and recheck the averages. Do not clip measured concentrations to pass the check.

## Load and validate

Run this block first. Resolve validation findings before continuing to the calculation block. The checker returns **text**, not a Boolean pass flag, and does not repair data.

```python
from pathlib import Path
import json
from copy import deepcopy
import matplotlib
matplotlib.use("Agg")  # Save figures without an interactive display.
import matplotlib.pyplot as plt
import pandas as pd
from auto_vtna import check_kinetic_data
from auto_vtna.Automatic_VTNA import Automatic_VTNA
from auto_vtna.Normal_VTNA import Normal_VTNA

data = pd.read_excel("kinetics.xlsx", sheet_name=None)
report = check_kinetic_data(data, bold_and_red=False, print_report=False)
print(report)
```

The report checks structure, headings, numeric/nonnegative values and increasing time. Also verify that the first column really is time, units agree, and the experiments satisfy the catalyst-variation design.

## Search and export

Continue with validated `data`. First check the interval-average threshold in the actual numeric input unit. The selection includes every experiment, omits no rows, searches order in `cat`, and overlays `P`. Its initial order value `1` is a placeholder for automatic search; use the estimated order for the subsequent fixed-order overlay.

```python
for name, table in data.items():
    cat_values = table["cat"].to_numpy(dtype=float)
    interval_averages = (cat_values[:-1] + cat_values[1:]) / 2
    if not (interval_averages > 1e-10).all():
        raise ValueError(
            f"{name}: catalyst interval averages must exceed 1e-10 "
            "in the supplied concentration unit for consistent search and overlay."
        )

selection = {
    "RM": {name: {"omissions": None} for name in data},
    "normalised_species": {"cat": 1},
    "output_species": "P",
}
settings = {
    "order_range": [-1.5, 2.5], "resolution": 7, "iterations": 7,
    "deg": 5, "fit_metric": "RMSE", "constraint": "monotonic",
    "score_interval": 0.15, "initial_mesh_denser": True,
}
analysis = Automatic_VTNA(data, selection, **settings)
order = float(analysis.best_orders[0])  # Only cat is searched here.

out = Path("vtna-results")
out.mkdir(exist_ok=True)
analysis.results.to_csv(out / "order-search.csv", index=False)
analysis.interval.to_csv(out / "score-interval.csv", index=False)
(out / "analysis.json").write_text(
    json.dumps({
        "software": "auto-vtna==1.2.4", "settings": settings,
        "selection": selection, "best_order_cat": order,
        "concentration_unit": "M", "time_unit": "s",
    }, indent=2), encoding="utf-8"
)
score_fig = analysis.plot_orders_vs_overlay(points=True, interval=True)
score_fig.savefig(out / "order-score.png", dpi=200, bbox_inches="tight")
plt.close(score_fig)

overlay_selection = deepcopy(selection)
overlay_selection["normalised_species"]["cat"] = order
overlay = Normal_VTNA(deepcopy(data), overlay_selection)
fig = overlay.plot_VTNA(y_unit="M", plt_show=False)
fig.savefig(out / "normalized-overlay.png", dpi=200, bbox_inches="tight")
plt.close(fig)
for number, (name, table) in enumerate(overlay.result.items(), start=1):
    table.to_csv(out / f"normalized-{number}.csv", index=False)
    print(name, "->", f"normalized-{number}.csv")
print("Estimated order in cat:", order)
```

These settings are the 1.2.4 class defaults, not experimentally determined settings. `order_range` defines the initial grid; `resolution` and `iterations` control refinement. `deg=5` and `constraint="monotonic"` fit a monotonic fifth-degree polynomial to all normalized profiles. Inspect both plots before accepting the minimum. A poorly resolved or edge minimum warrants a wider initial range or altered resolution and a recorded sensitivity comparison.

Outputs go to `vtna-results` relative to the working directory. Reusing this directory overwrites matching filenames; choose a new directory to retain earlier analyses.

## Interpret results

- `order-search.csv`: columns `order in cat` and `RMSE overlay score`. Lower RMSE means better overlay for this dataset and fitting setup. Automatic fitting shifts initial output concentrations to a common value and scales their pooled mean to one, so this RMSE is not an error in mol/L.
- `score-interval.csv`: sampled order limits with scores strictly below 1.15 times the minimum RMSE. This is a score-tolerance interval, not a statistical confidence interval or search-resolution error.
- `normalized-overlay.png` and `overlay.result[name]`: fixed-order transformed profiles. Added column `tT` is normalized time; for order n with inputs in seconds and mol/L, its units are s times M raised to n. Product concentrations are shifted to the largest initial product concentration across experiments. Exported tables therefore contain transformed data; retain the original workbook.
- `order-score.png`: assess whether the optimum is localized or broad. Persistent profile separation, an ill-defined minimum or sensitivity to fit choices limits the estimate; do not round it to a mechanistic integer automatically.

Resolve warnings, exceptions and nonfinite scores before interpretation. An all-zero output profile cannot be scaled meaningfully. An exactly zero best RMSE can leave the strict score-interval selection empty and fail interval construction; that failure is not evidence of an absent reaction order.
