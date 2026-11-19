---
name: goodvibes-build-computed-reaction-profiles
description: Assemble completed quantum-chemistry calculations into stoichiometric reaction energy profiles with GoodVibes, select conformer treatment, and export portable evaluated tables and figures. Use when species, pathway order and reference states are already supplied.
---

# Assemble computed reaction energy profiles

GoodVibes combines each species' corrected energies into ordered stoichiometric points and subtracts a chosen reference. Supply the species identities, coefficients, pathway order and reference states; this workflow does not discover a mechanism or verify reaction connectivity.

## Obtain GoodVibes and prepare calculations

Use Python >=3.10 and the [official GoodVibes source](https://github.com/patonlab/GoodVibes/tree/a3e5c6f1353735db8ff142584372b78e97bb3f3e) at commit `a3e5c6f1353735db8ff142584372b78e97bb3f3e`. The snapshot declares package version 4.4.0; pin the commit for the profile interfaces below. In an environment intended for this work:

```bash
git clone https://github.com/patonlab/GoodVibes.git GoodVibes
cd GoodVibes
git checkout a3e5c6f1353735db8ff142584372b78e97bb3f3e
python -m pip install ".[profile]"
```

This installs `goodvibes`, `goodvibes-profile`, YAML support and the plotting extra. The checkout also supplies example QC outputs; these are excluded from the wheel/sdist. The normal path below can be adapted to your own completed outputs or followed with the checkout's `goodvibes/examples/pes` files.

Prepare a working directory containing frequency outputs and, when applying separate single-point corrections, their companion outputs. For `--spc sp_tzpop`, `structure.log` pairs with `structure_sp_tzpop.log` (the companion may also use `.out`). GoodVibes uses the companion's electronic energy with thermochemical corrections from the frequency calculation. Use consistent electronic-energy, solvent and thermochemistry settings across species before comparing a pathway.

| Input choice | Operational meaning |
| --- | --- |
| Output-file arguments | Files to parse; the YAML mapping selects among these, rather than discovering additional frequency files. |
| Species `files` | A file-stem glob or list; omit extensions in glob patterns. Include only conformers belonging to that species. |
| Point expression | `A + B` adds species; `2*A + B` applies integer coefficients. Include free molecules consistently as association/dissociation changes molecular counts. |
| Pathway `zero` | Reference point for all relative values on that pathway; defaults to its first point. |
| Temperature/state | `--temp` is K, default 298.15; default gas standard state is 1 atm. `--conc` is mol/L when a concentration standard state is intended. |

## Define and evaluate a pathway

The following `pathway.yaml` adapts the official [azabor PES example](https://github.com/patonlab/GoodVibes/blob/a3e5c6f1353735db8ff142584372b78e97bb3f3e/goodvibes/examples/pes/azabor_PES_v2.yaml), making its first-point reference explicit. Save it beside the input logs; with the example checkout, work in `GoodVibes/goodvibes/examples/pes`.

```yaml
pathways:
  Ph:
    - "R1-An + Aza-Phos"
    - "R1-Comp + THF"
    - "AmTS + THF"
    - "Azir-Comp + THF"
    - "OpenTS + THF"
    - "Syn-P + THF"
zero:
  Ph: "R1-An + Aza-Phos"
species:
  R1-An:     {files: "r1-li-3thf-*"}
  Aza-Phos:  {files: "azaoxy-phosphine-full*"}
  THF:       {files: "thf*"}
  R1-Comp:   {files: "r1-phosphine-2thf-full*"}
  AmTS:      {files: "aminationTS-full-unfrz-*"}
  Azir-Comp: {files: "aziridinium-phos-full*"}
  OpenTS:    {files: "openTS-phos-full*"}
  Syn-P:     {files: "syn-product-phos-full*"}
format:
  units: kcal/mol
  decimals: 2
```

Choose the conformer model before evaluation:

| Model | CLI selection | Species contribution |
| --- | --- | --- |
| gconf | Default | Lowest conformer plus Boltzmann adjustment and conformational mixing entropy. |
| Boltzmann average | `--nogconf` | Weighted average without mixing entropy. |
| Lowest conformer | `--lowest-only` | Single conformer's full thermochemical vector, selected by lowest qh-G by default. Overrides `--nogconf`. |

The example invocation chooses lowest-only. Remove that flag when gconf is intended; these are different thermodynamic models.

```bash
goodvibes *.log --spc sp_tzpop --strict-spc --pes pathway.yaml --temp 298.15 --lowest-only --profile evaluated.json --with-conformers
```

`--strict-spc` requests an error for missing/unparseable correction energies; this CLI also checks for absent companion files while collecting inputs. Without strict handling, some SPC parsing failures can warn and fall back to the frequency-level energy. Resolve SPC errors rather than accepting a mixture of energy levels. Companion files matching the suffix are excluded from the frequency input set automatically. If no separate SPC is intended, omit both SPC options; linked-job corrections use `--spc link` instead.

Set the thermochemistry options required by the task on this same command. Defaults include Grimme quasi-harmonic entropy, a 100 cm^-1 cutoff, no Head-Gordon enthalpy correction, and level-dependent automatic frequency/ZPE scaling. `--qs truhlar` chooses frequency raising; `--qh` adds the enthalpy correction. Choose temperature, concentration and scaling explicitly when the intended method requires them.

For an explicit reaction-profile document instead of the compact PES YAML, use the official [aminoxylation example](https://github.com/patonlab/GoodVibes/blob/a3e5c6f1353735db8ff142584372b78e97bb3f3e/goodvibes/examples/gconf_ee_boltz/gconf_aminox_cat_profile.yaml). It declares `schema: reaction-profile/1.0`, maps `cat` to `aminox_cat_*`, `subs` to `aminox_subs_*` and `TS` to `Aminoxylation_TS1_R` under `goodvibes.sources.default`, and orders the points `cat+subs` (species `cat + subs`) then `TS`. Run it from its example directory without SPC options because the example's frequency files are the inputs. Its `goodvibes.rollup: {mode: gconf}` is honored unless overridden by `--nogconf` or `--lowest-only`. This form supports explicit point roles, labels and series; see the [profile format and computation recipe](https://github.com/patonlab/GoodVibes/blob/a3e5c6f1353735db8ff142584372b78e97bb3f3e/docs/source/reaction_profile.md#the-goodvibes-namespace) when those are needed.

## Inspect, export and re-evaluate

Read the printed PES relative-energy table and its mode/temperature/state header. Check that the reference point is zero and that each stoichiometric point includes the intended free species. A reaction energy is a difference between endpoints; a barrier from an intermediate is `level(TS) - level(intermediate)`, which need not equal the TS height relative to the pathway zero. Comparing pathways with different zeros requires deliberate reference alignment.

`evaluated.json` is a reaction-profile document with points, pathways, computed series, relative `levels` and provenance. Compact PES inputs are upgraded to this document format; by default they export the `qh_gibbs` plotting quantity per temperature. To export another quantity, use `--pes-plot-quantity`, e.g. `gibbs` for ordinary Gibbs energy. Inspect `series[].quantity` and `temperature` rather than inferring them from the filename. Levels have shape `series[].levels[pathway][point]` and use the document's `units`; entropy quantities are represented as T times the entropy difference in energy units.

```bash
goodvibes-profile validate evaluated.json
goodvibes-profile table evaluated.json -o profile.csv
goodvibes-profile plot evaluated.json -o profile.svg --label-points
goodvibes-profile evaluate evaluated.json -o hot.json --temperatures 298.15,373.15
goodvibes-profile table hot.json -o profile_temperatures.md
```

These commands read the evaluated document from the current working directory and write the named output files. Retain `evaluated.json` as the portable handoff: `--with-conformers` stores parsed structures and their thermochemistry options under `goodvibes.conformers`, enabling temperature re-evaluation without QC outputs. Stored levels alone support plotting/tabulation but cannot supply temperature re-evaluation. SVG embeds the plotted data without conformers, so it does not replace that JSON handoff.

A species pattern matching no parsed files is an error; inspect the reported available stems and the command's input glob. Validation errors identify unresolved points/species/zeros or malformed fields; validation checks the document, not chemical connectivity. An unevaluated PES recipe has no energy levels and must first pass through `goodvibes ... --pes ... --profile ...`. The table command can report `(no levels: evaluate the document first)`; `null` values mean unknown energies, and absent levels are not drawn. Do not interpret missing entries as zero or as an inaccessible chemical step. The profile expresses computed energies under the selected thermochemical model, not measured barriers or proof of a reaction mechanism.
