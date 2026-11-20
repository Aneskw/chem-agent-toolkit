---
name: goodvibes-compare-labeled-populations-v4-4
description: Calculate two-way or multiway labeled populations with the released GoodVibes 4.4.0 CLI, audit conformer membership and compare ensemble with lowest-member results.
---

# Labeled ensemble populations and selectivity

Use GoodVibes to compute thermochemistry and sum Boltzmann contributions within chemically assigned labels. The result describes the supplied ensemble: conformer discovery, optimization, frequency validation and chemical assignment must already be supplied. Product-selectivity interpretation also needs an independently justified kinetic model; the calculation alone does not establish it.

## Environment and prepared inputs

Use **GoodVibes 4.4.0**, Python **3.9 or newer**. Official setup and documentation: [tagged project README](https://github.com/patonlab/GoodVibes/blob/v4.4.0/README.md). In the execution environment, acquire the pinned release with:

```sh
python -m pip install goodvibes==4.4.0
```

The installed console entrypoint is `goodvibes`. The workflow below needs no plotting or YAML extras.

Prepare completed frequency outputs, for example Gaussian 09/16 `.log` or `.out`, or ORCA 5/6 `.out`. Supply at least two labels, their chemical meanings and the intended members. Compare like-composition structures on a common electronic-energy reference with consistent calculation methods, solvation, temperature, standard state and correction choices. Raw absolute energies of different stoichiometries are not comparable by this workflow.

Validate structures externally: minima and transition structures must have the intended vibrational character, and transition structures must represent the assigned competing channels. Supply distinct conformers without accidental duplicate files; each included file contributes once, with no user-specified degeneracy weight in this route. Ensemble completeness and any physical multiplicities require chemical justification. Do not enable automatic `--dedup` casually for stereochemical labels: the tool can classify enantiomers as duplicates across the input set.

## Choose thermochemistry once for the whole comparison

Use the same options in every label. The following are choices to establish from the intended analysis, not values to infer from filenames:

| Choice | Interface and consequence |
|---|---|
| Temperature | `--temp T` in K; default 298.15. Use a positive physical temperature. |
| Standard state | `--conc C` in mol/L; omission uses gas-phase 1 atm. A concentration correction does not supply a solvent electronic-energy calculation. |
| Low-frequency entropy | `--qs grimme` (default) or `--qs truhlar`; `--fs N` sets its cutoff in cm^-1, default 100. The default `gibbs` population key uses quasi-harmonic G even without `-q`. |
| Enthalpy correction | `--qh` adds Head-Gordon enthalpy correction; `-q` enables it with the entropy treatment. `--fh N` sets the enthalpy cutoff, default 100 cm^-1. Use `--fs` and `--fh` directly when setting separate cutoffs. |
| Frequency scaling | Automatic lookup uses the recognized method/basis, falling back to 1.0. `-v X` overrides vibrational scaling and also ZPE unless `--zpe-vscal Y` is supplied. Record the factors actually used. |
| Higher-level energy | Optional `--spc TZ` pairs `TS_R_001.log` with `TS_R_001_TZ.log`/`.out`. Supply the matching SPC for every frequency file; keep SPC files out of the conformer list. `--spc link` uses a linked single-point job instead. |

`--imag` displays imaginary frequencies. Leave inversion off unless a justified treatment of small spurious modes is supplied; inversion does not validate a transition structure.

## Run from the results directory

For illustrative files `TS_R_001.log`, `TS_R_002.log`, `TS_S_001.log`, etc., run this single-line command from their directory:

```sh
goodvibes "TS_*.log" --temp 298.15 --conc 1.0 --qs grimme --fs 100 --qh --fh 100 --imag --label "R=*_R_*" --label "S=*_S_*" --json selectivity.json
```

Here 298.15 K, 1.0 M, correction settings, filenames and labels are replaceable example choices. Add a justified scaling override or `--spc` to this same invocation when needed. Quoting file globs lets GoodVibes expand them, including on Windows. Relative input paths and `selectivity.json` resolve from the current working directory. Use a distinct JSON path for each comparison or temperature; writing the same path replaces it.

Patterns use `fnmatch` against **either the basename or the immediate parent-directory name**, not the full path. A file goes to the **first matching label** in command order; unmatched files do not contribute to the labeled sums. Use disjoint patterns and inspect assignments rather than relying on ordering to resolve chemical ambiguity.

Choose these modes without changing the common thermochemistry procedure:

- **Directory labels:** from a parent directory containing `R/*.log` and `S/*.log`, replace the positional glob and labels with `"R/*.log" "S/*.log" --label "R=R" --label "S=S"`. GoodVibes does not recursively discover all subdirectories from the original glob.
- **Three or more labels:** for filenames such as `TS_A_001.log`, `TS_B_001.log`, `TS_C_001.log`, use the same command with `--label "A=*_A_*" --label "B=*_B_*" --label "C=*_C_*"` instead of the two R/S labels. Retain all intended competing labels in one run.
- **Lowest-conformer comparison:** every labeled run also selects one minimum-energy file per label using the chosen energy key: qh-G for the default `gibbs`, or raw SCF energy with `--boltz energy`. Read `selectivity_lowest`; no second run or `--lowest-only` flag is needed. That flag controls PES tables, not this comparison.

Use the default `gibbs` key for the corrected-free-energy workflow. `--boltz` is optional for per-file display; `--boltz energy` changes the labeled calculation to raw SCF-energy weighting and therefore changes the meaning. For temperature-dependent thermochemistry, rerun the complete single-temperature command with each desired `--temp` and a separate output file. In 4.4.0, the labeled `--ti` branch reweights the already computed base-temperature energies instead of recalculating them at every temperature.

## Read and audit the output

The JSON contains per-file `results` plus separate `selectivity` and `selectivity_lowest` blocks. This complete readout example uses only Python's standard library; execute it from the same directory after GoodVibes has produced the file:

```python
import json
from pathlib import Path

payload = json.loads(Path("selectivity.json").read_text(encoding="utf-8"))
print("GoodVibes:", payload["goodvibes_version"])
for mode in ("selectivity", "selectivity_lowest"):
    block = payload[mode]
    result = block["results"][0]  # one result for this single-temperature run
    print(mode, block["key"], result["temperature"])
    print("Members:", result["files_per_label"])
    print("Fractions:", result["populations"])
    print("Preferred:", result["preferred"])
    print("Unsigned excess (%):", result["ee"], "Gap (Hartree):", result["ddG"])
for entry in payload["results"]:
    thermo = entry["thermo"]
    print(entry["file"], thermo["qh_gibbs_free_energy"], thermo["sp_energy"])
```

Before interpreting populations, compare `files_per_label` with the intended membership and the per-file `results` (whose `file` paths are absolute). Account for unmatched, missing and repeated members. Every intended member needs a finite numeric `thermo.qh_gibbs_free_energy`. Assigned file lists are not proof that all members contributed: missing energies are skipped. If SPC was requested, also require a finite numeric `thermo.sp_energy` for every member. A failed parse can leave `'!'` there while retaining uncorrected thermochemistry; fix the pairing/calculation and rerun before using the comparison.

Populations are normalized over the included, usable members of the labeled set. For label L the calculation sums `exp(-(G_i - G_min)/(R*T))` over its members, with consistent energy units, then divides by the sum over all labels. It does not average conformer G values before exponentiating.

| Result | Meaning |
|---|---|
| `populations` | Fractions summing to 1 across labels; multiply by 100 for percentages. Report ordered ratios using these fractions, not rounded console ratios. |
| `preferred` | Largest population. At an exact tie the first maximal label is returned; this does not demonstrate preference. |
| `ee` | With exactly two labels, `100 * abs(p_A - p_B)`: unsigned percent excess. Call it enantiomeric excess only when the labels are justified enantiomeric outcomes. |
| `ddG` | With two positive populations, `R*T*ln(p_major/p_minor)`, positive by convention, stored in Hartree. Multiply by 627.509541 for kcal/mol. This ensemble gap need not equal a gap between two individual structures. |
| N-way `ee`, `ddG` | Both null. Report all fractions or pairwise `p_A/p_B` when the denominator is positive; do not assign an N-way ee. |
| `selectivity_lowest` | Same calculation using only each label's lowest member. Its file lists identify those members. Differences from the ensemble result expose the contribution of the included additional conformers. |

A two-label zero population makes `ddG` null; it may reflect numerical underflow or unusable members and is not evidence of a measured infinite gap. An empty label, fewer than two labels, wholly unusable energies or zero total weight causes failure. A label with assigned files but no usable energies can produce a zero sum in the core calculation; the lowest-only calculation then fails on that label. Resolve the input defect rather than reporting partial output.

Hand off the JSON, the exact command/settings, audited membership, temperature, populations in label order and both ensemble and lowest-only estimates. These are conditional calculated population estimates without calibrated uncertainty. State the supplied justification before treating transition-state ratios as predicted product selectivity; without it, report only labeled Boltzmann population ratios. Differences between ensemble and lowest-only results do not measure uncertainty from missing conformers, electronic-structure errors or kinetic assumptions.
