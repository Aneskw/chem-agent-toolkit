---
name: scipy-compare-transition-state-ensemble-selectivity
description: Calculate competing reaction-channel fractions from supplied transition-state Gibbs energies with SciPy, and compare results as the transition-state ensemble expands.
---

# Selectivity from a transition-state ensemble

Sum the contributions of all supplied distinct transition states in each channel, then normalize across channels. This implements Boltzmann weighting with equal per-state kinetic prefactors. It requires validated transition states and comparable Gibbs energies; geometry search, energy calculations and connectivity validation are external preparation.

## Environment

Use Python 3.12 or later and **SciPy 1.18.1**, with NumPy available. Follow the official [SciPy installation guide](https://scipy.org/install/) to create and activate a virtual environment, then install the pinned release:

```sh
python -m pip install "scipy==1.18.1"
```

The calculation uses the verified [release-tag logsumexp interface](https://github.com/scipy/scipy/blob/v1.18.1/scipy/special/_logsumexp.py). No electronic-structure program is needed once the energy table is prepared.

## Prepare comparable records

| Input | Contract |
|---|---|
| `records` | List of `(ts_id, channel, dG_kcal)` tuples; one row per distinct transition state. IDs and channel labels are nonempty strings. |
| `dG_kcal` | Finite Gibbs barrier in thermochemical kcal/mol relative to **one common reactant reference** across every channel. |
| `channels` | Ordered tuple of expected channels; every channel must have supplied states. |
| `T` | Positive finite temperature in kelvin, matching the Gibbs energies. |

Before calculating, confirm the energy method, solvent model, temperature, standard state and reactant reference are consistent. Do not combine separately zeroed channel barriers or electronic energies with Gibbs energies. Changing `T` also requires appropriate Gibbs energies at that temperature.

Remove duplicate representations of the same state. The template assigns each row one contribution and does not infer symmetry multiplicities, reactant populations or channel-dependent transmission factors. If such factors are required, resolve them before using this equal-prefactor model.

## Calculate and compare ensembles

The following data are illustrative. Replace them with the prepared records. The helper below leaves the input list unchanged and returns arrays in the requested channel order.

```python
import numpy as np
from scipy.special import logsumexp

R_KCAL = 8.31446261815324 / 4184.0  # kcal mol^-1 K^-1

def channel_fractions(records, channels, T):
    channels = tuple(channels)
    if (len(channels) < 2 or len(set(channels)) != len(channels)
            or any(not isinstance(c, str) or not c for c in channels)):
        raise ValueError("Provide at least two distinct, nonempty channel labels")
    if not np.isfinite(T) or T <= 0:
        raise ValueError("T must be positive and finite, in kelvin")
    if not records:
        raise ValueError("No transition states supplied")
    ids, labels, energies = zip(*records)
    if any(not isinstance(s, str) or not s for s in ids):
        raise ValueError("Each transition state needs a nonempty string ID")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate transition-state IDs")
    if any(c not in channels for c in labels):
        raise ValueError("Unexpected channel label")
    if any(c not in labels for c in channels):
        raise ValueError("Missing states for an expected channel")
    labels = np.asarray(labels)
    dG = np.asarray(energies, dtype=float)
    if dG.shape != (len(records),) or not np.all(np.isfinite(dG)):
        raise ValueError("Each Gibbs energy must be a finite scalar in kcal/mol")

    # A common energy shift cancels in normalized fractions and ratios.
    x = -(dG - dG.min()) / (R_KCAL * T)
    if not np.all(np.isfinite(x)):
        raise ValueError("Energy/temperature scale exceeds floating-point range")
    log_weights = np.array([logsumexp(x[labels == c]) for c in channels])
    log_fractions = log_weights - logsumexp(log_weights)
    return {
        "channels": channels,
        "n_ts": np.array([np.count_nonzero(labels == c) for c in channels]),
        "fraction": np.exp(log_fractions),
        "log_fraction": log_fractions,
    }

channels = ("C4", "C3")
T = 298.0
base_records = [
    ("a1", "C4", 18.0), ("a2", "C4", 18.6),
    ("b1", "C3", 18.4), ("b2", "C3", 19.1),
]
# An expanded set retains the original rows and adds distinct supplied states.
expanded_records = base_records + [
    ("a3", "C4", 19.3), ("b3", "C3", 19.0),
]
base = channel_fractions(base_records, channels, T)
expanded = channel_fractions(expanded_records, channels, T)

print("channel  n_base  n_expanded  base_percent  expanded_percent  delta_pp")
for i, channel in enumerate(channels):
    print(channel, base["n_ts"][i], expanded["n_ts"][i],
          100 * base["fraction"][i], 100 * expanded["fraction"][i],
          100 * (expanded["fraction"][i] - base["fraction"][i]))
# Natural-log ratio of the first channel to the second, here C4/C3:
ln_ratio = expanded["log_fraction"][0] - expanded["log_fraction"][1]
print("ln(C4/C3):", ln_ratio)
```

For each channel, the calculation evaluates
`L_c = log(sum(exp(-dG_i/(R*T))))`, then normalizes with
`p_c = exp(L_c - logsumexp(L))`. The shared shift in the example changes neither fractions nor ratios. NumPy and SciPy receive dimensionless exponents; temperature is not an optional scaling parameter independent of the supplied thermochemistry.

## Read the results

- `fraction` contains dimensionless channel fractions; multiply by 100 for percent. `n_ts` records how many states contributed to each channel.
- `log_fraction` retains natural-log fractions when exponentiating would underflow to a displayed zero. `ln_ratio > 0` favors the first named channel; the ordinary ratio is `exp(ln_ratio)` when representable.
- `delta_pp` is the signed change in percentage points after adding states, not a relative percent change. Report both ensemble sizes and the change; there is no universal acceptance threshold here.

An empty ensemble or missing expected channel is incomplete input. Although `logsumexp` can return negative infinity for an empty reduction, that does not establish physical exclusion of a reaction channel. The example raises `ValueError` instead. Nonfinite energies and invalid temperatures also stop calculation. A finite calculation cannot detect inconsistent references or two differently named copies of the same transition state; those require inspection of the supplied data.

These are model-based kinetic channel fractions under the declared equal-prefactor assumption, not measured product yields or absolute rates. A small change after expanding the ensemble shows insensitivity to those particular additions; it does not prove that important pathways have all been found. This ensemble comparison follows the analysis described in the [study's mechanistic section, pp. 8986-8987](https://doi.org/10.1002/chem.202001236).
