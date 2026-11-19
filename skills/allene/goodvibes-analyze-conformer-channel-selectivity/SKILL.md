---
name: goodvibes-analyze-conformer-channel-selectivity
description: Use GoodVibes to calculate labeled conformer populations and competing-channel selectivity from prepared quantum-chemistry outputs, compare ensemble and lowest-conformer predictions, and examine sensitivity to temperature and conformer inclusion.
---

# Conformer populations and channel selectivity with GoodVibes

Use this workflow for scientifically comparable conformer or transition-state calculations with user-defined channel labels. It sums conformer Boltzmann weights within each channel and compares that ensemble prediction with one lowest-energy conformer per channel. It does not discover missing conformers or establish whether an equilibrium or kinetic interpretation applies. Interpreting TS populations as product selectivity requires a justified competing-channel model and, where applicable, conformational equilibration.

## Prepare the environment and inputs

Use Python ≥3.10 and [GoodVibes](https://github.com/patonlab/GoodVibes) at commit `a3e5c6f1353735db8ff142584372b78e97bb3f3e`. Install that source revision into the execution environment:

```bash
python -m pip install "goodvibes @ git+https://github.com/patonlab/GoodVibes.git@a3e5c6f1353735db8ff142584372b78e97bb3f3e"
```

This VCS installation requires Git. It provides the `goodvibes` command. The optional sweep example below uses plain records and does not require pandas. See the [pinned setup documentation](https://github.com/patonlab/GoodVibes/blob/a3e5c6f1353735db8ff142584372b78e97bb3f3e/README.md) for other installation choices; retain the commit pin for this interface.

External inputs are completed frequency-calculation output files, for example Gaussian `.out` or `.log` files. Supply comparable composition, charge/spin, computational treatment, energy reference and thermochemical settings across the competing groups. Confirm intended stationary points and conformer coverage before using the prediction.

For the normal path, work in the directory containing the prepared files, named for example `DA_exo_12_i.out`, `DA_exo_12_ii.out`, `DA_endo_12_i.out`, and so on. These are external inputs, not files created by this skill. A shipped demonstration set is available from the [pinned Diels–Alder example directory](https://github.com/patonlab/GoodVibes/tree/a3e5c6f1353735db8ff142584372b78e97bb3f3e/goodvibes/examples/selectivity); examples are not included in the installed wheel.

Before calculation, audit the input list and label patterns:

- Patterns use `fnmatch` against the file basename **or its immediate parent directory basename**. They do not search directories for additional files.
- Each file goes to the first matching label, in label order. Unmatched files are silently excluded. Use disjoint patterns and verify that every intended conformer belongs to exactly one channel.
- Remove redundant copies from the prepared set. CLI duplicate detection is off by default. If needed, add `--dedup`: with labels it compares within each channel. `--dedup-global` additionally compares across channels and can remove structures from competing groups; use only when that is scientifically intended. Detection flags duplicate/enantiomeric structures, so inspect the reported pairs rather than assuming every removal is appropriate.
- Preserve a consistent label order: it sets the sign of two-channel excess.

## Calculate and inspect the comparison

Run from the input directory, choosing a new results path because JSON output overwrites an existing file:

```bash
goodvibes DA_*.out --label 'exo=*_exo_*' --label 'endo=*_endo_*' --temp 298.15 --json results.json
```

The values here are example choices. Relevant defaults and controls:

| Setting | Meaning |
|---|---|
| `--temp` | Temperature in K; default 298.15. |
| Default selectivity key `gibbs` | Weights **quasi-harmonic Gibbs free energies**, not uncorrected Gibbs energies. |
| `--qs grimme`, `--fs 100` | Default entropy method and cutoff in cm⁻¹; quasi-harmonic enthalpy correction is off unless requested. |
| `--conc C` | Solution concentration in mol/L; without it the default is gas phase at 1 atm. Choose the appropriate common standard state. |
| `--boltz energy` | Alternative electronic-energy weighting; changes the quantity and interpretation. |

Review the terminal's **Boltzmann-averaged** and **Lowest conformer only** tables, then inspect the saved assignments and numeric results:

```python
import json
from pathlib import Path

data = json.loads(Path("results.json").read_text(encoding="utf-8"))
for method in ("selectivity", "selectivity_lowest"):
    block = data[method]
    print(method, block["labels"], block["key"])
    for result in block["results"]:
        print("T / major:", result["temperature"], result["major"])
        print("assigned files:", result["files_per_label"])
        print("populations (%):",
              {k: 100 * v for k, v in result["populations"].items()})
        print("excess / signed excess (%):",
              result["ee"], result["ee_signed"])
        print("major/runner-up ratio:", result["ratio"])
        print("ddG (Hartree):", result["ddG"])
        print("ensemble energies (Hartree):", result["ensemble_energies"])
```

Inspect per-file thermochemistry in the top-level `results` list as well. The ensemble `files_per_label` records assignments, including files later skipped for duplicate status or unusable energy; it is not a guarantee that every listed file contributed. The lowest-only block records the selected file per label.

Interpretation:

- `populations` are fractions summing to one across labels. Each label's weight is the **sum**, not the mean, of its conformer weights. `ensemble_energies` are −RT ln Σ exp(−Gᵢ/RT), in Hartree for the default workflow.
- `major` is the largest-population label; an exact tie chooses the first listed. For two labels, `ee` is the unsigned excess in percent and `ee_signed = 100(p₁ − p₂)`. “Excess” is enantiomeric excess only when the labels represent enantiomeric channels.
- `ratio` compares the major with the runner-up. Two-label `ddG = RT ln(p_major/p_minor)` is nonnegative: JSON stores Hartree, while terminal summaries display kcal/mol.
- Lowest-only selects the conformer with the minimum of the chosen weighting quantity in each label: quasi-harmonic Gibbs energy at the selected temperature by default, or electronic energy with `--boltz energy`. Changes in population or major channel between the two blocks show the effect of the supplied conformer ensemble.
- For more than two labels, `ee`, `ee_signed` and `ddG` are null; compare populations and the major/runner-up ratio. To separate regio- and stereochemistry, replace the two labels with `exo_12=*_exo_12*`, `endo_12=*_endo_12*`, `exo_14=*_exo_14*`, `endo_14=*_endo_14*`.

A missing label match or no usable energies raises an error. Missing energies may be skipped in ensemble sums, and the lowest-only calculation fails if a channel has no usable conformer. A zero population can also reflect numerical underflow; `ratio` and two-label `ddG` are null when the runner-up population is zero. Do not interpret absent/zero contributions as evidence that a chemical pathway is impossible. Resolve input or parsing problems before reporting selectivity.


## Optional sensitivity sweep

Use this when the question includes robustness to temperature, entropy treatment or conformer inclusion. Pass the same audited, nonredundant groups: this API does not automatically apply CLI duplicate detection. Keep labels in the same order as the CLI.

```python
import json
from pathlib import Path
from goodvibes import compute_selectivity_batch, summarize_selectivity

jobs = {"DA": {"exo": "DA_exo_*.out", "endo": "DA_endo_*.out"}}
rows = compute_selectivity_batch(
    jobs,
    temperatures=[298.15, 353.15],
    s_freq_cutoffs=[50, 150],
    conformer_windows=[0, 1.0, 3.0],
    records=True,
)
for summary in summarize_selectivity(rows, decimals=1):
    print(summary["job"], summary["temperature"], summary["text"])
Path("selectivity-sweep.json").write_text(
    json.dumps(rows, indent=2), encoding="utf-8"
)
```

These are illustrative sensitivity settings, not prescribed scientific thresholds. Every condition recomputes thermochemistry from parsed inputs at its temperature. Default quantity is `qh_gibbs`. Cutoffs are cm⁻¹; the nominal cutoff (100 unless `s_freq_cutoff` is supplied) is always included. Windows are kcal/mol above **each label's own minimum at that condition**; the all-conformer window `None` is always included. Zero keeps minima, including numerical ties, so it can differ from the CLI's single-lowest comparison.

Rows contain `job`, `temperature`, `s_freq_cutoff`, `conformer_window`, `nominal`, `major`, signed `ee` (%), `ddG` (kcal/mol), `ratio`, and `population[label]` (fraction) / `n[label]` (retained conformer count). `nominal` means nominal cutoff and all conformers. Unlike JSON `ee` above, batch `ee` is signed. For N-way jobs use `summarize_selectivity(rows, value="ratio")` or a population column; the default `ee` summary yields no entries when excess is undefined. Unavailable nominal values can also leave a summary empty; inspect the rows.

Report the nominal prediction with its major label, label order, energy quantity, temperature, thermochemical settings, conformer counts, lowest-only comparison and observed sweep range. A sensitivity range describes these chosen conditions, not a statistical confidence interval or a validation of the chemical model.
