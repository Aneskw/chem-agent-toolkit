---
name: scipy-calculate-boltzmann-channel-weights
description: Use SciPy to convert supplied competing-state free energies into normalized Boltzmann weights and Z/E channel fractions at an explicit temperature. Select when energies and channel assignments are already available.
---

# Boltzmann weights and Z/E selectivity with SciPy

Use one common free-energy reference for all included states. This workflow calculates a conditional distribution over the supplied states; it does not calculate energies or determine whether Boltzmann weighting describes a reaction network. For transition-state inputs, interpreting the result as product selectivity requires the supplied states to be comparable competing pathways with the assumed common kinetic prefactors.

## Prepare the environment and inputs

Use **SciPy 1.18.1**, with a compatible Python **3.12–3.15** environment and NumPy **>=2.0,<2.8**. Follow the [official installation guide](https://scipy.org/install/) to prepare and activate a virtual environment, then install the pinned release:

```sh
python -m pip install "scipy==1.18.1"
```

The package resolver supplies NumPy. No molecular software or energy-generation step is included here.

| Input | Contract |
| --- | --- |
| `G` | Nonempty, finite, real 1-D array of free energies in **kcal/mol**, one entry per distinct included state. |
| `channels` | Same-length 1-D array containing only `"Z"` or `"E"`; both channels must have at least one supplied state for this comparison. Assign channels externally. |
| `T` | Finite positive scalar temperature in **kelvin**, consistent with the supplied free energies. |
| `reference` | Text describing the shared energy zero, e.g. a named common reactant or relative state-energy convention. |

Convert other units before calling. Do not mix electronic energies with Gibbs free energies or independently zero the two channels. Each row contributes once with equal prior weight: resolve duplicate structures and any required degeneracy or unequal prefactors before using this unweighted workflow; do not invent multiplicities.

## Normalize and aggregate

The adapted Python template below uses [SciPy's tagged `logsumexp` interface](https://github.com/scipy/scipy/blob/v1.18.1/scipy/special/_logsumexp.py). With `a_i = -(G_i - min(G))/(R*T)`, it computes `w_i = exp(a_i - logsumexp(a))`, then sums weights by the supplied labels. Subtracting the global minimum preserves the relative weights. `logsumexp` uses all elements by default (`axis=None`); no signed scaling or extra weights are used.

```python
import numpy as np
from scipy.constants import R, calorie
from scipy.special import logsumexp


def boltzmann_ze(G, channels, T, reference):
    G = np.asarray(G, dtype=float)
    channels = np.asarray(channels)
    T = float(T)
    if G.ndim != 1 or G.size == 0 or not np.isfinite(G).all():
        raise ValueError("G must be a nonempty finite 1-D energy array")
    if channels.shape != G.shape or not np.isin(channels, ["Z", "E"]).all():
        raise ValueError("Supply exactly one Z/E label per energy")
    if not all(np.any(channels == c) for c in ("Z", "E")):
        raise ValueError("Supply at least one state in each channel")
    if not np.isfinite(T) or T <= 0:
        raise ValueError("T must be finite and positive in kelvin")
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("Describe the common free-energy reference")

    # R is J/(mol K); calorie is 4.184 J (thermochemical).
    R_kcal = R / (1000.0 * calorie)
    try:
        with np.errstate(over="raise", divide="raise", invalid="raise"):
            a = -(G - G.min()) / (R_kcal * T)
    except FloatingPointError as exc:
        raise ValueError("Energy/temperature scale exceeds float range") from exc
    log_w = a - logsumexp(a)
    with np.errstate(under="ignore"):
        weights = np.exp(log_w)
    fractions = {c: float(weights[channels == c].sum()) for c in ("Z", "E")}
    log_ratio = float(logsumexp(a[channels == "Z"])
                      - logsumexp(a[channels == "E"]))
    with np.errstate(over="ignore", under="ignore"):
        ratio = float(np.exp(log_ratio))
    return {
        "weights": weights,
        "fractions": fractions,
        "Z_over_E": ratio,
        "ln_Z_over_E": log_ratio,
        "temperature_K": T,
        "energy_units": "kcal/mol",
        "reference": reference,
        "subtracted_min_kcal_per_mol": float(G.min()),
        "included_states": {c: int(np.sum(channels == c)) for c in ("Z", "E")},
    }
```

Use the function in a Python session or save it with this call in a `.py` file and invoke `python your_file.py` in the prepared environment. These are illustrative inputs, not reported study energies:

```python
import json

G = [0.0, 0.7, 1.1, 1.6]  # kcal/mol; replace with supplied values
channels = ["Z", "E", "Z", "E"]
result = boltzmann_ze(
    G, channels, T=298.15,
    reference="All entries relative to the same supplied energy zero",
)
print(json.dumps({**result, "weights": result["weights"].tolist()}, indent=2))
```

This prints the result to standard output. Inputs are not modified. Retain the input energies and labels beside the report so every weight remains traceable to its original row.

## Read the result

- `weights[i]` corresponds to input row `i`; weights sum to approximately one. `fractions["Z"]` and `fractions["E"]` sum to approximately one and become percentages after multiplication by 100.
- `Z_over_E` means Z divided by E, i.e. the ratio `Z_over_E : 1`. `ln_Z_over_E` is its natural logarithm, computed directly from channel log sums.
- At extreme energy separations, a weight or fraction can underflow to zero, and the exponentiated ratio can become zero or infinity. These are floating-point limits, not proof of an impossible channel. Use `ln_Z_over_E` for comparisons in that regime; avoid rounding fractions before computing ratios.
- Invalid shapes, missing channels, nonfinite energies or invalid temperature raise errors rather than producing a distribution. An empty state list has no normalized result.

Report temperature, units, shared reference, included states/channels and the assumed weighting convention with the fractions. These are calculated weights over the supplied state set, not measured product ratios; omitted pathways or unjustified population-to-product assumptions change their interpretation.
