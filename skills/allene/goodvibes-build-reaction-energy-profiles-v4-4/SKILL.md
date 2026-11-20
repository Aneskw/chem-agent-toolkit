---
name: goodvibes-build-reaction-energy-profiles-v4-4
description: Build conformer-resolved reaction-energy tables and figures with the released GoodVibes 4.4.0 API from validated frequency outputs and supplied stoichiometric pathways.
---

# Reaction-energy profiles with consistent conformer treatment

Use GoodVibes **4.4.0** to aggregate conformers within each species, sum the species at each stoichiometric point, and subtract a declared pathway reference. The pathway, species identities, and conformer membership must be supplied. Geometry optimization, conformer searches, frequency validation, and IRC connectivity checks are external preparation.

## Environment and prepared inputs

Use Python >=3.9 and the [official GoodVibes release](https://github.com/patonlab/GoodVibes/releases/tag/v4.4.0). In the execution environment, setup is:

```sh
python -m pip install "goodvibes[full]==4.4.0"
```

The full extra supplies PyYAML and matplotlib. Use the Python environment containing this installation for the example below. See the [tagged API](https://github.com/patonlab/GoodVibes/blob/v4.4.0/goodvibes/api.py) for thermochemistry parameters.

Supply completed frequency outputs (for example Gaussian `.log` or ORCA `.out`), with any higher-level single-point outputs paired to them. All compared structures need compatible electronic-energy methods, thermochemistry settings, and standard states. Assign only distinct conformers of the same chemical species to a species ensemble; duplicate calculations would change its statistical weight. Include free reagents, catalyst, and byproducts in each point as needed to keep the compared stoichiometry consistent. A TS file represents the specified transition structure, not an inferred connection.

Run from an analysis directory containing the calculation files and `pathway.yaml`; relative paths and all outputs below resolve from this working directory. Names, file counts, and numerical settings in this example are replaceable.

```yaml
species:
  R:   {files: "R_*_freq.log"}
  Cat: {files: "Cat_*_freq.log"}
  TS:  {files: "TS_*_freq.log"}
  P:   {files: "P_*_freq.log"}
pathways:
  main: ["R + Cat", "TS", "P + Cat"]
zero:
  main: "R + Cat"
format:
  units: kcal/mol
  decimals: 2
```

`TS` here contains both R and Cat; adapt the sums to the actual chemistry. Terms support positive integer coefficients such as `2*R + Cat`. Define every species used in points or zeros. Add pathways as additional mapping entries; set the same zero expression for branches you intend to compare directly. An omitted zero defaults to that pathway's first point. Units accept `kcal/mol` or `kJ/mol`.

Species `files` patterns select **only from the files passed to thermochemistry**, not files discovered relative to the YAML. They match basename stems, ignoring a trailing `.log`/`.out`; they do not distinguish identical basenames in different folders. Use `{files: ["R_01_freq.log", "R_02_freq.log"]}` for explicit membership or `{dir: "reactant"}` to match parent-directory basenames, and supply corresponding paths to the Python input list. Neither rule recursively discovers calculations. A species matching no supplied files raises an error.

## Choose the aggregation

| Treatment | Selection in the example | Meaning |
|---|---|---|
| Single conformer | Map each species to exactly one supplied file | Uses that structure; no ensemble correction |
| Lowest qh-G | `mode = "lowest"` | Selects each species' lowest corrected Gibbs-energy conformer; all its quantities come from that conformer |
| Boltzmann average | `mode = "average"` | Averages quantities with weights from qh-G at the chosen temperature; no mixing entropy |
| Gconf | `mode = "gconf"` | Boltzmann averages H and S, adds conformational mixing entropy, and recomputes G |

Lowest-only takes precedence over Gconf. Ensemble results are conditional on the supplied conformer coverage and membership. A Boltzmann-average G is not the Gconf ensemble free energy.

## Produce the table and figure from one model

Use this complete Python template, saved as `run_profile.py` in the analysis directory and run with `python run_profile.py`. It uses upstream thermochemistry, PES construction, serialization, and plotting; CSV extraction is formatting glue. GoodVibes 4.4.0's CLI synchronizes aggregation flags only when rendering its table, after JSON/figure creation. Explicit model options below keep all outputs consistent for every mode.

```python
import csv
import json
from glob import glob
from pathlib import Path
from types import SimpleNamespace
import matplotlib.pyplot as plt
from goodvibes.api import compute_batch
from goodvibes.pes_loader import load_pes
from goodvibes.output import write_json_results
from goodvibes.plot import plot_pes

# Replace these settings with the intended physical model.
mode = "gconf"                 # "gconf", "average", or "lowest"
T = 298.15                     # K
settings = dict(
    temperature=T, concentration=1.0,  # mol/L; None means 1 atm gas
    QS="grimme", QH=False,
    s_freq_cutoff=100.0, h_freq_cutoff=100.0,  # cm^-1
    freq_scale_factor=None, zpe_scale_factor=None,
    spc=None,                  # e.g. "TZ" or "link"
)
patterns = ["R_*_freq.log", "Cat_*_freq.log",
            "TS_*_freq.log", "P_*_freq.log"]
files = sorted({p for pattern in patterns for p in glob(pattern)})
if not files:
    raise ValueError("No frequency inputs matched")
if mode not in {"gconf", "average", "lowest"}:
    raise ValueError("Unknown aggregation mode")
results = compute_batch(files, **settings)
for r in results:
    if not r.has_thermo:
        raise ValueError(f"No thermochemistry: {r.file}")
    if settings["spc"] is not None:
        sp = getattr(r.bbe, "sp_energy", None)
        if not isinstance(sp, (int, float)):
            raise ValueError(f"Missing or unreadable SPC: {r.file}")
thermo = {r.file: r.bbe for r in results}
pes = load_pes("pathway.yaml", thermo, temperatures=[T])
pes.options.gconf = mode == "gconf"
pes.options.lowest_only = mode == "lowest"
pes.options.QH = settings["QH"]
pes.options.spc_used = settings["spc"] is not None
options = SimpleNamespace(
    **settings, conc=settings["concentration"],
    S_freq_cutoff=settings["s_freq_cutoff"],
    H_freq_cutoff=settings["h_freq_cutoff"],
)
write_json_results(thermo, options, "profile.json", pes_result=pes)

payload = json.loads(Path("profile.json").read_text(encoding="utf-8"))
# Preserve API settings and aggregation omitted by the upstream serializer.
payload["profile_settings"] = dict(settings, aggregation=mode)
Path("profile.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
with open("profile.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["pathway", "temperature_K", "zero", "units",
                     "point", "relative_qh_G"])
    for path in payload["pes"]["pathways"]:
        for point in path["points"]:
            writer.writerow([path["name"], path["temperature"],
                             path["zero_label"], path["units"],
                             point["label"], point["relative"]["qh_g"]])
# Separate figures also support pathways with unequal point counts.
for i, path in enumerate(pes.pathways):
    ax = plot_pes(pes, pathway_index=i, label_points=True,
                  title=f"{path.name}: {mode}, {T:g} K")
    ax.figure.savefig(f"profile-{i + 1}.png", dpi=200,
                      bbox_inches="tight")
    plt.close(ax.figure)
```

Use `QS="truhlar"` for frequency raising instead of Grimme's low-frequency interpolation. `QH=True` additionally applies Head-Gordon enthalpy correction; it is separate from the entropy-method choice. The example's 1 M concentration and 298.15 K are illustrative, not universal. Concentration controls the translational standard state; it does not introduce an electronic solvation calculation. Solvation energies must already be represented by the supplied calculations. With scale factors `None`, GoodVibes looks up the calculation's level of theory and falls back to 1.0 when unavailable. An explicit `freq_scale_factor` is also inherited by ZPE unless `zpe_scale_factor` is separately supplied. Record the factors used rather than assuming automatic lookup found the intended method.

For a higher-level electronic-energy correction, set `spc="TZ"` when each frequency file has a companion with exactly the same path stem plus `_TZ.log` or `_TZ.out`: `R_01_freq.log` pairs with `R_01_freq_TZ.log`. Supply only the frequency parents in `files`; companions are read through `spc`. Use `spc="link"` for a linked calculation containing the single-point job. GoodVibes combines that electronic energy with thermal corrections from the frequency calculation. The example rejects a missing/unreadable SPC sentinel rather than treating it as a valid corrected profile. Check that the paired jobs describe the same geometry and electronic state during input preparation.

## Read and interpret the outputs

- The template adds `profile_settings` to record the API settings and aggregation. `profile.json` retains per-file thermochemistry and resolved membership under `pes.pathways[].points[].species` (`coefficient`, `name`, `files`). Check these assignments before interpreting a profile; broad globs can silently include the wrong conformers.
- Each pathway carries `temperature`, `units`, and `zero_label`. Its `points[].relative.qh_g` is the corrected Gibbs-energy difference against that zero. `g`, `h`, `qh_h`, `scf`, and `zpe` are other relative quantities; `ts` and `qh_ts` are **T times entropy differences**, in the same energy units. Per-file `results[].thermo` energies remain Hartree and entropies Hartree/K. Do not convert the already converted PES values again. Interpret `spc` only when a single-point correction was requested and verified; its presence alone does not prove SPC use.
- `profile.csv` tabulates the same relative qh-G values used in `profile-1.png`, `profile-2.png`, etc., in pathway order. Retain the JSON and YAML with the figures to preserve assignments and settings. For an overlay, replace the per-pathway loop with `plot_pes(pes)` only when all selected pathways have equal point counts and their x positions are chemically comparable.

For each temperature, rebuild thermochemistry and the PES with the same T, using distinct output names. Passing several temperatures to the PES loader does not recompute temperature-dependent molecular quantities; the plot uses its first temperature. Do not use the CLI's temperature-interval route as a substitute for this JSON/figure workflow.

An activation free energy is the TS value minus the chemically appropriate preceding reactant/intermediate value on a common reference; a plotted TS height relative to a remote pathway zero is not automatically a local barrier. Curved plot connectors are graphical guides, not computed reaction coordinates or evidence of connectivity. These are calculated profiles conditional on the electronic-structure method, correction settings, reference state, and conformer coverage; they do not establish mechanism or experimental uncertainty.

Unknown species, empty pathways, unmatched species patterns, and invalid units are input errors, not zero energies. Missing thermochemistry/SPC in the template stops the calculation. A successful write also needs the intended membership and reference: independent pathway zeros can hide offsets between branches. Correct the input or settings and regenerate the JSON, table, and figures together.
