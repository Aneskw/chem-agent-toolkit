---
name: goodvibes-calculate-thermochemistry-v4-4
description: Compute molecular thermochemistry with the released GoodVibes 4.4.0 API or CLI from frequency outputs, with optional single-point corrections, batches and temperature or standard-state changes.
---

# Correct molecular thermochemistry with GoodVibes

Use supplied, validated frequency calculations to obtain absolute electronic, enthalpic and Gibbs-energy quantities. Geometry optimization, conformer searching and transition-state connectivity checks must already be supplied. This workflow covers individual structures and batches; chemical population estimates and stoichiometric reaction profiles require their own analysis.

## Environment and inputs

Use **GoodVibes 4.4.0**, Python **3.9 or newer**. The [official tagged installation documentation](https://github.com/patonlab/GoodVibes/blob/v4.4.0/README.md#installation) provides acquisition instructions:

```bash
python -m pip install goodvibes==4.4.0
```

The examples need the base package only. Use the environment containing that installation for both Python imports and the `goodvibes` executable.

Supply completed frequency outputs supported by GoodVibes, such as Gaussian `.log`/`.out` or ORCA `.out`. For an optional single-point correction (SPC), supply an energy calculated for the corresponding geometry, charge and multiplicity. Check that the calculation's solvent/model choices implement the intended composite method. A standalone single-point file cannot supply the vibrational thermochemistry.

| Input arrangement | API `spc` / CLI `--spc` | Files supplied |
|---|---|---|
| Frequency calculation alone | `None` / omit flag | `structure.log` |
| Separate higher-level single point | `"TZ"` / `TZ` | `structure.log` and `structure_TZ.log` or `.out`, in the same directory |
| Linked frequency then single-point jobs | `"link"` / `link` | One linked output, e.g. `structure_spc.out` |

The suffix must match exactly: `structure_def2_TZVP.log` requires `spc="def2_TZVP"`. Pass base frequency files to computation; companion SPC files are resolved internally. Paths below are relative to the current working directory.

## Choose the correction and reference state

| Option | Meaning and default |
|---|---|
| `QS="truhlar"` or `"grimme"` | Entropy scheme. Truhlar raises low frequencies for entropy; Grimme interpolates toward free-rotor entropy. Default: Grimme. |
| `s_freq_cutoff=100.0` | Entropy cutoff, cm⁻¹; choose for the intended method. |
| `QH=False` | Keep harmonic enthalpy. `True` adds the Head-Gordon enthalpy correction, with `h_freq_cutoff` in cm⁻¹ (default 100). |
| `temperature=298.15` | Temperature in K. |
| `concentration=None` | 1-atm gas reference. Set an explicit mol/L value, e.g. `1.0`, for that solution standard state. |
| `freq_scale_factor=None`, `zpe_scale_factor=None` | Look up separate harmonic H/S and ZPE factors from the frequency calculation's level of theory. Unmatched levels fall back to 1.0 in this version. |

Scaling factors are dimensionless. Check the detected level against the intended scaling source; automatic lookup does not guarantee a calibrated factor exists. Setting only `freq_scale_factor` makes ZPE inherit it; set both factors when they should differ. Setting both to `1.0` disables scaling. Entropy-method selection and scaling-factor lookup are separate choices.

A solvent used in the electronic-structure calculation does not itself select a solution concentration here. Set the standard state explicitly. The examples use Truhlar entropy and harmonic enthalpy; temperature and cutoff values are adaptable examples.

## One structure through corrected output

Run from the directory containing `structure.log` and `structure_TZ.log`:

```python
from pathlib import Path
from goodvibes import compute_thermo

if not Path("structure_TZ.log").is_file():
    raise FileNotFoundError("Expected SPC companion: structure_TZ.log")

options = dict(
    QS="truhlar", QH=False, s_freq_cutoff=100.0,
    temperature=298.15, concentration=None,
    freq_scale_factor=None, zpe_scale_factor=None,
)
r = compute_thermo("structure.log", spc="TZ", **options)
if not r.has_thermo or r.qh_gibbs_free_energy is None:
    raise ValueError("Frequency output did not provide usable thermochemistry")
if r.sp_energy is None:
    raise ValueError("Requested SPC energy was not obtained")

print(r.name, r.program, r.level_of_theory)
print("E(freq), E(SPC), qh-G / Hartree:",
      r.scf_energy, r.sp_energy, r.qh_gibbs_free_energy)
print("Imaginary modes / cm-1:", r.im_frequency_wn)
```

For an `.out` companion, change the existence check accordingly. For no SPC, remove that check, omit `spc` and omit the SPC-result check. For linked jobs, use `compute_thermo("structure_spc.out", spc="link", **options)` and verify the supplied file contains the intended final single-point calculation.

GoodVibes combines the frequency calculation's thermal terms with the replacement electronic energy. **Do not add the SPC energy or a second thermal correction to `qh_gibbs_free_energy`.** A missing/unreadable separate SPC can leave thermal results based on the original energy; check the requested correction even when `has_thermo` is true. A populated `sp_energy` alone does not prove an SPC was requested or applied: retain the invocation options and file pairing.

## Batch and temperature modes

For multiple structures, select base frequency files explicitly. With the imports and `options` above:

```python
from goodvibes import compute_batch

paths = ["structure.log", "other.log"]  # both need matching *_TZ companions
results = compute_batch(paths, spc="TZ", jobs=1, **options)
for item in results:                   # same order as paths
    if not item.has_thermo or item.qh_gibbs_free_energy is None:
        raise ValueError(f"Missing thermochemistry: {item.file}")
    if item.sp_energy is None:
        raise ValueError(f"Missing requested SPC: {item.file}")
    print(item.file, item.qh_gibbs_free_energy)
```

An empty input list returns an empty list; it is not evidence that a directory contained usable calculations. For process-parallel batches, `jobs>1` selects worker count; put the calling code inside a `main()` invoked under `if __name__ == "__main__":` when using a script, especially on Windows.

For temperature-resolved values, recompute rather than reusing a result's Gibbs energy. This continuation produces a solution-standard-state value at each example temperature:

```python
for temp in (298.15, 313.15, 333.15):
    state = dict(options, temperature=temp, concentration=1.0)
    item = compute_thermo("structure.log", spc="TZ", **state)
    if not item.has_thermo or item.sp_energy is None:
        raise ValueError(f"Incomplete thermochemistry/SPC at {temp} K")
    print(temp, item.qh_gibbs_free_energy)  # K, Hartree
```

Use `concentration=None` in that loop for a constant-pressure 1-atm reference, whose molar concentration changes with temperature; an explicit concentration stays fixed. CLI `--ti START,END,STEP` prints a temperature scan, but in 4.4.0 `--json` still exports only the base `--temp` calculation. Use the API loop for machine-readable per-temperature values, or issue separate single-temperature CLI calls with distinct output paths.

## CLI and persistent JSON

The single-temperature equivalent of the first example is:

```bash
goodvibes structure.log --qs truhlar --fs 100 --temp 298.15 --spc TZ --json thermo.json
```

Add `--conc 1.0` for a 1 mol/L reference; `--qh` enables the enthalpy correction, and `--fh` sets its cutoff. `-v` sets harmonic H/S scaling and `--zpe-vscal` sets ZPE scaling. By itself, `-q` combines default Grimme entropy with Head-Gordon enthalpy; the entropy scheme still follows `--qs`. Use explicit options to make the intended combination clear.

Read the file in the command's working directory:

```python
import json
import math
from pathlib import Path

payload = json.loads(Path("thermo.json").read_text(encoding="utf-8"))
requested_spc = payload["options"].get("spc") is not None
for entry in payload["results"]:
    thermo = entry["thermo"]
    if requested_spc:
        energy = thermo.get("sp_energy")
        if not isinstance(energy, (int, float)) or not math.isfinite(energy):
            raise ValueError(f"Missing requested SPC: {entry['file']}")
    print(entry["file"], thermo.get("qh_gibbs_free_energy"))
```

JSON schema 1.0 carries `options`, per-file `results`, parsed `qcdata` and computed `thermo`. Preserve the options with the numbers. Null/missing values mean unavailable quantities, not zero. For requested SPC, require a finite numeric `thermo.sp_energy`: the raw JSON serializer can preserve `"!"` for an unreadable separate SPC, while the API maps that sentinel to `None`. Fix the pairing or calculation before using that correction. The CLI also writes a `GoodVibes_output.dat` report by default; use distinct `--output` names when keeping reports from several runs.

## Interpret and inspect results

| Result attribute / JSON thermo key | Meaning |
|---|---|
| `scf_energy`, `sp_energy`, `zpe` | Electronic energies and ZPE contribution, Hartree; record whether SPC was requested. |
| `enthalpy`, `qh_enthalpy` | Total enthalpies, Hartree; the API gives `qh_enthalpy=None` when the enthalpy correction is disabled. |
| `entropy`, `qh_entropy` | Entropies, Hartree/K. Console `T.S` columns already multiply by temperature. |
| `gibbs_free_energy`, `qh_gibbs_free_energy` | Total Gibbs energies, Hartree. With `QH=False`, corrected G uses harmonic H and corrected S; with `QH=True`, it uses corrected H and S. |
| `im_frequency_wn`, `inverted_freqs` | Reported imaginary modes and any inverted modes, cm⁻¹. Empty lists can be represented as `None` by the API. |

Inspect imaginary modes against the supplied minimum/transition-state assignment; their absence from the returned list does not independently validate the structure. Leave `invert=None` unless the scientific protocol explicitly justifies converting small imaginary modes. Parser success and `has_thermo` establish data availability, not stationary-point or mechanism validation.

When comparing outputs, retain the temperature, standard state, scaling, entropy/enthalpy scheme and SPC choice. These are calculated thermochemical estimates; changes in those choices change their meaning. Consult the [tagged API implementation](https://github.com/patonlab/GoodVibes/blob/v4.4.0/goodvibes/api.py) for exact argument/field definitions and the [tagged output schema](https://github.com/patonlab/GoodVibes/blob/v4.4.0/goodvibes/schema.py) for structured integration.
