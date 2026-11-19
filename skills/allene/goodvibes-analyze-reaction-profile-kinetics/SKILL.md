---
name: goodvibes-analyze-reaction-profile-kinetics
description: Calculate Eyring step rates from evaluated GoodVibes reaction profiles and, for complete catalytic cycles, energy spans, turnover-determining states and TOF estimates. Use for ordered free-energy pathways, not concentration-versus-time microkinetics.
---

# Rates and energy spans from reaction profiles

## Environment

Use [GoodVibes](https://github.com/patonlab/GoodVibes) at commit `a3e5c6f1353735db8ff142584372b78e97bb3f3e`, with Python ≥3.10. Install this source revision into the intended Python environment:

```bash
python -m pip install "https://github.com/patonlab/GoodVibes/archive/a3e5c6f1353735db8ff142584372b78e97bb3f3e.zip"
```

The installed `goodvibes-profile` executable must be on PATH in that environment. This workflow needs no QC engine or plotting extras when the profile already contains energies. The [profile specification at this revision](https://github.com/patonlab/GoodVibes/blob/a3e5c6f1353735db8ff142584372b78e97bb3f3e/docs/source/reaction_profile.md) explains the document format.

## Prepare the supplied profile

Start with an evaluated `reaction-profile/1.x` YAML or JSON document. A declared series with supplied values also works. Check these fields before calculating:

| Field | Required meaning |
| --- | --- |
| `pathways.<name>` | Points in reaction order, with distinct point IDs. Select one pathway per analysis. |
| `points.<id>.role` | Explicit `ts` for each transition state; other roles are treated as intermediates by kinetics. Names containing “TS” alone do not establish the role. |
| `series[].id`, `quantity` | Select an explicit series ID whose quantity is `gibbs` or `qh_gibbs`. Kinetics does not reject electronic-energy or enthalpy series. |
| `series[].levels.<pathway>` | Complete numeric free energies for every point, relative to one common reference. Missing/null levels are silently omitted by kinetics. |
| `units` | One document-wide unit: `kcal/mol`, `kJ/mol`, `eV` or `hartree`; default `kcal/mol`. |
| `series[].temperature` | Positive temperature in K at which these free energies apply. If absent, kinetics uses `default_temperature`, default 298.15 K. |
| Standard state | Establish consistent standard states and stoichiometric bookkeeping across levels; record them in series/method metadata. Metadata does not convert the energies. |

For `--span`, confirm that the pathway describes **one complete catalytic turnover**. Its final point must represent the initial catalyst regenerated with products, with consistent reactant/product bookkeeping. The code sets `reaction_energy = G(last) - G(first)` and excludes that final point from the cycle-state sum. It does not verify chemical closure. An ordinary product endpoint or a partial mechanistic diagram does not establish this prerequisite. For an open pathway, omit `--span` and interpret only the steps.

Changing temperature metadata does not recalculate free energies. Supply energies evaluated at the desired temperature; upstream profile evaluation is a separate preparation step.

## Invoke and access results

Use the supplied document as `cycle.yaml`. The following is an illustrative declared-input template; its numbers and 350 K temperature are example choices:

```yaml
schema: reaction-profile/1.0
units: kcal/mol
points:
  I0:  {role: reactant}
  TS1: {role: ts}
  I1:  {role: minimum}
  TS2: {role: ts}
  P:   {role: product}
pathways:
  cycle: [I0, TS1, I1, TS2, P]
series:
  - id: G
    quantity: gibbs
    temperature: 350.0
    source: declared
    levels:
      cycle: {I0: 0.0, TS1: 15.0, I1: -10.0, TS2: 0.0, P: -5.0}
```

For span analysis of this template, `P` must mean regenerated `I0` plus products, rather than a separate catalyst-bound product intermediate. Replace IDs, energies, temperature and standard-state provenance with the supplied system's information.

Run in the directory containing the input (relative output paths resolve from the working directory):

```bash
goodvibes-profile validate cycle.yaml
goodvibes-profile kinetics cycle.yaml --pathway cycle --series G --span --json
goodvibes-profile kinetics cycle.yaml --pathway cycle --series G -o steps.csv
```

Validation checks document structure/references; it does not establish kinetic suitability or chemical closure. JSON goes to stdout with `steps` and, with `--span`, `energy_span`. The separate `-o` invocation writes the step table; `.md` selects Markdown instead of CSV. Output files are overwritten. Do not combine `--json` with `-o`: JSON takes precedence and the table file is not written. Input documents are read without rewriting.

For programmatic access to the same evaluated input:

```python
from goodvibes import load_profile

profile = load_profile("cycle.yaml")
steps = profile.step_table("cycle", "G")       # list of row dictionaries
span = profile.energy_span("cycle", "G")      # EnergySpan dataclass
print([(r["ts"], r["barrier"], r["k"]) for r in steps])
print(span.tdts, span.tdi, span.span, span.tof, span.control)
```

An alternative input convention uses only actual cycle states, without an appended regenerated endpoint. Supply the independently known turnover free energy explicitly through Python (the CLI has no corresponding flag):

```python
from goodvibes.kinetics import energy_span

# Insertion order is reaction order; no regenerated endpoint in this mapping.
span = energy_span(
    {"I0": 0.0, "TS1": 15.0, "I1": -10.0, "TS2": 0.0},
    ["TS1", "TS2"],
    reaction_energy=-5.0, temperature=350.0, units="kcal/mol",
)
print(span.tof, span.tof_span)
```

When `reaction_energy` is explicit, every mapping entry is retained as a cycle state. Do not also include the regenerated endpoint. These example values match the template's alternative representation.

## Interpret and check

| Result | Meaning |
| --- | --- |
| Step `from`, `ts`, `to` | Nearest preceding non-TS, current TS, nearest following non-TS. |
| `barrier`, `step_energy` | `G(ts)-G(from)` and `G(to)-G(from)`, in document units. |
| `barrier_from_lowest` | TS level minus the lowest earlier point. Highlights an earlier deep state; `k` still uses the local `barrier`. |
| `k`, `half_life` | Eyring rate with transmission coefficient 1; `ln(2)/k` is a first-order half-life in seconds. |
| Span `tdts`, `tdi`, `span` | Dominant TS/intermediate pair and energy span in document units. If TDTS precedes TDI, `span = G(TDTS)-G(TDI)+reaction_energy`; otherwise no correction is added. |
| `tof`, `tof_span` | Full energy-span-model TOF and single-span approximation `(kB*T/h)*exp(-span/RT)`, in s⁻¹. |
| `control` | Per-state shares of the span-model denominator; TS shares sum to 1, intermediate shares separately sum to 1. Distributed control makes the single-pair summary less complete. |

CLI labels `k` as s⁻¹. This applies to unimolecular steps. For bimolecular activation free energies at the 1 M standard state, the rate constant is interpreted in M⁻¹ s⁻¹; the printed first-order half-life is not the bimolecular half-life. The program does not infer molecularity or apply concentrations.

Check `reaction_energy` and `tdts_after_tdi` before comparing TOFs. Full `tof` is zero for a thermoneutral cycle and negative for an endergonic cycle in the chosen direction. `tof_span` remains a positive Eyring approximation; it does not demonstrate favorable net turnover. Report these as model estimates conditional on the supplied free energies and cycle, not measured rates. The [implemented model](https://github.com/patonlab/GoodVibes/blob/a3e5c6f1353735db8ff142584372b78e97bb3f3e/goodvibes/kinetics.py) identifies the Kozuch–Shaik energy-span formulation.

An empty `steps` list means no TS has an earlier non-TS on the retained pathway; inspect roles, ordering and missing values. A terminal TS produces `to: null` and `step_energy: null`. Span requires at least one TS and intermediate; the inferred-reaction-energy convention also requires a regenerated endpoint. Missing pathway/series values and malformed documents produce errors, normally exit status 1 and diagnostics on stderr. Repair the input before interpreting results. Nonfinite results or implausible negative activation barriers also warrant checking the energies and their interpretation.

This workflow does not solve species concentrations versus time or a branched reaction network.
