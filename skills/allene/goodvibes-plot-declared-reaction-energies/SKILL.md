---
name: goodvibes-plot-declared-reaction-energies
description: Plot supplied relative-energy tables as labeled GoodVibes reaction profiles, export editable SVG/PDF figures, and preserve values in reusable YAML and tables. Use when numerical levels and pathway assignments are already established, without QC output parsing.
---

# Plot declared reaction energies

Use `goodvibes-profile` to turn established relative energies into figures and reusable reaction-profile documents. Inputs must already establish quantity, units, temperature, energy reference, pathway membership and point roles. This workflow neither calculates energies nor extracts numbers from paper figures. Declared values are never thermochemically re-evaluated; changing temperature metadata does not calculate new energies.

## Prepare the tool

Use Python ≥3.10 and the official [GoodVibes project](https://github.com/patonlab/GoodVibes), pinned to commit `a3e5c6f1353735db8ff142584372b78e97bb3f3e` for the interface below. Its package metadata identifies version 4.4.0; use the commit pin rather than assuming the same published release has these interfaces. Install into the execution environment:

```sh
python -m pip install "goodvibes[profile] @ git+https://github.com/patonlab/GoodVibes.git@a3e5c6f1353735db8ff142584372b78e97bb3f3e"
```

The `profile` extra supplies matplotlib ≥3.5. The installed console entrypoint is `goodvibes-profile`; run commands in a working directory containing your input table. Paths below are relative to that directory. Choose output names deliberately: figure, document and table writers replace existing files at those paths.

## Prepare the levels

Save a UTF-8 `levels.csv`. This small template uses **illustrative choices**, not measured or published results; replace the values and metadata with the supplied data:

```csv
point,role,display,A,B
R,reactant,R,0.0,0.0
TS_A,ts,TS A‡,18.4,
TS_B,ts,TS B‡,,20.0
P,product,P,-12.1,-10.0
```

| Input | Meaning |
| --- | --- |
| `point` | Stable point ID; the same ID aligns across pathways. Distinct branch states need distinct IDs even if their display labels match. |
| `role` | `reactant`, `minimum` (default), `ts`, or `product`. TS value labels appear above bars; other value labels below. |
| `display` | Printed point label; defaults to the ID. |
| `A`, `B` | Pathway columns, in the desired sequence of points by row order. Each cell is a relative energy. |
| Empty wide cell | Point is absent from that pathway. Use `null`, `none`, or `—` for a member whose value is unknown; it has no bar. Never substitute zero for missing data. |

The first member of each imported pathway becomes its reference point. Supply values already relative to the intended reference. The importer does **not** subtract the first value: a nonzero value there produces a warning and is still drawn as given. For direct comparisons, establish compatible energy references before preparing the table.

Pathways may have different lengths. Shared point IDs align on the merged x axis; labels alone do not establish identity. YAML can explicitly set `order: [R, TS_A, TS_B, P]` to control global x order; include every pathway point. Empty cells mean consecutive remaining members become connected, so use an explicit YAML edge with `kind: none` if a connection should be suppressed.

## Plot, preserve and recover

For the example, assume the supplied numbers are Gibbs relative energies at 298.15 K in kcal/mol. Carry these choices through every direct CSV read:

```sh
goodvibes-profile validate levels.csv --quantity gibbs --temperature 298.15 --units kcal/mol
goodvibes-profile plot levels.csv -o fig.svg -o fig.pdf --quantity gibbs --temperature 298.15 --units kcal/mol --label-points --preset single-column
goodvibes-profile convert levels.csv -o levels.yaml --quantity gibbs --temperature 298.15 --units kcal/mol
goodvibes-profile table fig.svg --long -o plotted-levels.csv
goodvibes-profile table levels.yaml -o levels.md --decimals 2
```

Select metadata from the input, not the example:

- `--quantity`: commonly `electronic` (ΔE), `e_zpe` (ΔE+ZPE), `enthalpy` (ΔH), `gibbs` (ΔG), or `qh_gibbs` (quasi-harmonic ΔG).
- `--units`: `kcal/mol`, `kJ/mol`, `eV`, or `hartree`; describes the supplied values, not a request to convert a table from another unstated unit.
- `--temperature`: kelvin; the CSV CLI defaults to 298.15. Quantity and units default to `gibbs` and `kcal/mol`. For temperature-independent data, edit the converted YAML series to `temperature: null` and update its `label` to omit the temperature.
- `--preset single-column`: about 85 mm wide; `double-column` is about 178 mm, and `slide` is 16:9. Repeat `-o` for additional formats, including PNG. Use `--layout panels` to separate crowded pathways.

`fig.svg` retains editable text and element IDs and embeds the profile data by default. Keep this original for data recovery; `--no-embed` disables recovery. Editing visible SVG artwork does not itself update the embedded numerical profile. `fig.pdf` is the figure export; use YAML or SVG for subsequent data reads.

`levels.yaml` is the editable data document. CSV tables retain full numeric precision; Markdown tables use rounded display values. Long tables include pathway, series, quantity, temperature, method, units and uncertainty; wide tables omit much of this metadata. Preserve YAML or long CSV for handoff rather than relying on a wide table alone.
## Optional annotations and supplied uncertainty

For richer figures, edit `levels.yaml`. The CSV importer creates series ID `table`. Add this top-level block for the example, then validate and replot the document:

```yaml
annotations:
  - {type: barrier, pathway: A, from: R, to: TS_A, series: table, label: "ΔG‡"}
```

```sh
goodvibes-profile validate levels.yaml --strict
goodvibes-profile plot levels.yaml -o annotated.svg -o annotated.pdf --label-points --preset single-column
```

An annotation marks `to − from` within the named pathway and series. Use IDs from the converted document, not printed labels. To record the source/method, use the document's `methods` and `provenance` fields; see the pinned [format specification](https://github.com/patonlab/GoodVibes/blob/a3e5c6f1353735db8ff142584372b78e97bb3f3e/docs/source/reaction_profile.md) when those details are needed.

If uncertainties were supplied, use a **long-layout replacement input** such as `levels-uncertain.csv`:

```csv
pathway,point,role,display,value,uncertainty
A,R,reactant,R,0.0,
A,TS_A,ts,TS A‡,18.4,1.5
A,P,product,P,-12.1,1.0
```

These uncertainty numbers are illustrative too. Add B's rows to include that pathway. Plot or convert this file with the same commands and metadata flags, replacing `levels.csv`. Columns `pathway` and `value` trigger long-layout detection. Uncertainty must be nonnegative and in the same units as the corresponding value; it is drawn as a symmetric ± uncertainty error bar. A blank uncertainty means none was supplied. The tool does not infer a confidence level or estimate uncertainty; preserve its supplied definition in document provenance. Default plotting includes error bars; `--no-uncertainty` hides them without deleting the stored values.

## Inspect and deliver

Inspect the figure against the input: pathway membership, point ordering, references, unit/quantity labels and TS roles. Return the SVG/PDF, editable YAML and requested tables. The bars visualize declared data; connectors are drawing aids, not calculated energy scans. Blank/unknown values do not establish barrierless chemistry.

Successful writers print `wrote PATH`. Treat `goodvibes-profile: error:` and nonzero exit status as failures; address the reported input, missing matplotlib, invalid IDs or unsupported output extension before using artifacts. Structural validation does not establish scientific correctness. A missing bar can indicate an absent or unknown value, while `(no levels: evaluate the document first)` indicates a document without evaluated levels, not zero energies. A PES recipe without numerical values cannot satisfy this workflow. Declared-only tables have no embedded conformers, so `evaluate` or temperature scans cannot supply missing thermochemistry.
