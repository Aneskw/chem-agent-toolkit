---
name: gaussian-log-descriptor-extraction
description: Extract molecular and atom-level descriptors from existing completed Gaussian logs with auto-QChem, preserving atom order and reporting parser failures and missing fields.
---

# Gaussian logs to descriptor tables

Use auto-QChem 1.3.16 to parse local Gaussian output. Start with completed logs containing the geometry, frequency and population sections expected by the parser. Gaussian execution, cluster submission, conformer generation and Boltzmann aggregation are outside this workflow. No Gaussian executable, database or credentials are needed to parse existing files.

Official acquisition and setup: [auto-QChem 1.3.16](https://github.com/doyle-lab-ucla/auto-qchem/releases/tag/1.3.16), [installation instructions](https://github.com/doyle-lab-ucla/auto-qchem/blob/1.3.16/INSTALL.md). The supplied runtime includes OpenBabel and the Python dependencies. For local setup with the declared dependency stack, apply the import-order compatibility change in [runtime.json](runtime.json) before importing the parser; upstream does not confirm Windows support.

## Runtime environment

Use the preconfigured Docker image:

```bash
docker pull ghcr.io/jinselw/chem-tools:autoqchem-v1
```

Execution example (Bash; replace the example filename or arguments for the task):

```bash
docker run --rm \
  --mount "type=bind,source=$(pwd),target=/work" \
  --workdir /work \
  ghcr.io/jinselw/chem-tools:autoqchem-v1 \
  python extract_descriptors.py molecule.log results/molecule
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).

## Prepare the log

The parser splits Gaussian tasks using route blocks whose first word becomes the task key: it expects `freq`, optionally `opt` and `td`. A successful Gaussian calculation with a differently arranged route/output layout may still be incompatible. It takes labels from the first charge/multiplicity geometry block and coordinates from the **last Standard orientation** block. Use logs whose task geometries preserve atom identity and order.

Required frequency-section patterns include harmonic frequencies, thermochemistry, stoichiometry, orbital populations and Mulliken charges. APT, NPA and NMR fields may be missing; inspect them explicitly. A present TD section requires additional excited-state scalar, Mulliken and NPA patterns. Do not strip sections or rewrite output text to force parsing.

## Extract and export

This adaptable Python example accepts a log path and a new output directory. The caller supplies the log. It writes the complete returned mapping plus one molecular row and one row per atom; the additional zero-based `atom_index` is an export convention. The new-directory requirement avoids overwriting previous results.

```python
import json
import sys
from pathlib import Path
import pandas as pd
from autoqchem.gaussian_log_extractor import gaussian_log_extractor

log_path = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=False)

try:
    parser = gaussian_log_extractor(str(log_path))
    parser.check_for_exceptions()
    result = parser.get_descriptors()

    # Keep all returned sections. pandas serializes NaN/None as JSON null.
    pd.Series(result, dtype=object).to_json(out / "descriptors.json", indent=2)
    labels = result["labels"]
    atoms = pd.DataFrame(result["atom_descriptors"])
    if len(atoms) != len(labels) or not all(isinstance(c, str) for c in atoms.columns):
        raise ValueError("Malformed atom table; inspect descriptors.json and source log")

    # Upstream population fields can be numeric strings. Conversion is explicit;
    # unexpected text raises rather than silently becoming a missing number.
    atoms = atoms.apply(pd.to_numeric, errors="raise")
    atoms.insert(0, "label", labels)
    atoms.insert(0, "atom_index", range(len(labels)))
    molecular = pd.DataFrame([result["descriptors"]])
    molecular.insert(0, "source_log", str(log_path))
    atoms.to_csv(out / "atoms.csv", index=False)
    molecular.to_csv(out / "molecular.csv", index=False)

    status = {
        "status": "extracted",
        "missing_molecular_fields": [
            k for k, v in result["descriptors"].items() if pd.isna(v)
        ],
        "missing_atomic_counts": atoms.isna().sum().to_dict(),
        "absent_sections": [
            k for k in ("transitions", "modes", "mode_vectors")
            if result.get(k) is None
        ],
    }
except Exception as exc:
    (out / "status.json").write_text(json.dumps({
        "status": "failed", "error_type": type(exc).__name__,
        "error": str(exc), "source_log": str(log_path)
    }, indent=2), encoding="utf-8")
    raise
else:
    (out / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
```

Read `status.json` before using the tables. A failed run can leave diagnostic or partial files; they are not a successful extraction. CSV missing cells are blank; JSON missing numbers are null. Preserve missingness rather than substituting zero. The schema check catches, among other mismatches, the upstream missing-NPA fallback that can create an integer-named column containing field names instead of measurements.

## Interpret results

`get_descriptors()` returns a dictionary; DataFrames are converted to dictionaries of column-name → list. Atom labels remain a separate list. Population values can remain strings in the complete JSON; the CSV example explicitly converts atomic values.

| Section / fields | Meaning and convention |
| --- | --- |
| `descriptors` | Molecular scalars. `E_scf` is SCF energy; `E_zpe` includes zero-point energy; `E`, `H`, `G` include thermal energy, enthalpy and free-energy contributions respectively. These and their correction fields are in Hartree. |
| `homo_energy`, `lumo_energy`, `electronegativity`, `hardness` | Hartree; electronegativity = −(LUMO + HOMO)/2 and hardness = (LUMO − HOMO)/2. Only multiplicities 1 and 3 have implemented orbital selection; others receive zero HOMO/LUMO placeholders. For triplets the implementation selects alpha HOMO and beta LUMO. |
| `dipole`, `molar_mass`, `molar_volume` | Debye, g/mol and Bohr³/mol respectively. |
| `converged` | Unitless fraction of parsed optimization criteria marked YES, or null; not an independent validation of the calculation. |
| `labels`, `atom_descriptors` | Parallel atom order; `X/Y/Z` are last-geometry coordinates in Å. Mulliken/APT/NPA charges use atomic units; NPA core, valence, Rydberg and total are electron populations. `NMR_shift` is parsed from Gaussian's isotropic shielding field (ppm), not a reference-corrected experimental chemical shift. |
| `VBur` | Unitless occupied volume fraction, not percent: a numerical grid within a 3 Å sphere around each atom, using van der Waals radii and default mesh density 30. The implementation includes the central atom in occupancy. |
| `transitions` | Optional TD rows in log order: `ES_transition` wavelength in nm, `ES_osc_strength` unitless oscillator strength and `ES_<S**2>` unitless spin expectation. This parser does not rank transitions by oscillator strength. |
| `modes`, `mode_vectors` | Optional vibration tables copied from Gaussian. Vector rows contain `mode_number` (one-based), `axis` and `value`, ordered by mode, axis and original atom order. Atom indices and the modes DataFrame index are discarded during dictionary conversion; preserve ordering when reconstructing them. |

The scalar extraction loop checks `freq` then `opt`; a matching value in `opt` overrides the frequency-section value. Retain the original log to trace values. See the [descriptor guide](https://github.com/doyle-lab-ucla/auto-qchem/blob/1.3.16/DESCRIPTOR.md) for less common fields, and the [versioned parser](https://github.com/doyle-lab-ucla/auto-qchem/blob/1.3.16/autoqchem/gaussian_log_extractor.py) for exact extraction behavior.

`check_for_exceptions()` raises `NoGeometryException` for missing geometry patterns, `NegativeFrequencyException` for any frequency below zero, and `OptimizationIncompleteException` when usable frequencies are absent. Other malformed/missing patterns may raise ordinary exceptions during either call. The check is not a general Gaussian normal-termination or convergence validator. Diagnose the source calculation or unsupported layout before retrying; this workflow does not rerun Gaussian.
