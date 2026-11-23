---
name: gaussian-log-descriptor-extraction
description: Extract molecular and atom-level descriptors, vibrational modes and optional TD data from existing Gaussian logs with auto-qchem, check parsing failures, and export tables.
---

# Extract descriptors from Gaussian logs

Use `auto-qchem==1.3.16` for completed local Gaussian logs with geometry, harmonic frequencies and population analysis. Gaussian calculation generation, submission and conformer averaging are external workflows. This extraction needs no Gaussian executable or cluster/database connection.

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
  python extract.py molecule.log extracted
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).

The tool is available from [official PyPI](https://pypi.org/project/auto-qchem/1.3.16/); [official setup](https://github.com/doyle-lab-ucla/auto-qchem/blob/master/INSTALL.md) installs Open Babel through conda-forge before the Python package. The image uses Open Babel 3.2.1 and includes a deferred-import repair for the release's circular import; a plain unpatched installation can fail while importing the extractor. For an equivalent local environment, move the module-level `gaussian_log_extractor` import in `autoqchem/rdkit_utils.py` into its two functions that instantiate that class. Leave the descriptor and parser implementations unchanged. Native Windows installation is untested upstream.

## Prepare the log

Keep the complete original text. The parser splits jobs using Gaussian route-section separators and takes the **first route keyword** as the task name (`freq`, `opt`, `td`). A frequency calculation whose first keyword is a method name may therefore be unrecognized. Repeated task names overwrite earlier sections in the parser's task dictionary. Geometry comes from the last `Standard orientation` block; labels come from the first charge/multiplicity geometry block. Confirm that these describe the same molecule and atom order.

The normal path needs a recognized `freq` section with a harmonic-mode table, thermochemistry, SCF population/orbital energies, stoichiometry and Mulliken charges. NPA, APT and NMR sections supply additional atom fields. TD is optional, but when present its parser also expects root dipole, molar volume, spatial extent, Mulliken and NPA sections; partial TD output can raise rather than produce partial results. Keep method, basis, solvent and calculation settings with the log for comparisons.

`check_for_exceptions()` raises `NoGeometryException`, `NegativeFrequencyException` or `OptimizationIncompleteException` for its geometry/frequency checks. Its negative-frequency check rejects transition-state logs too. It does not certify all Gaussian tasks completed: inspect termination messages and job completion separately. Parsing errors can also occur during construction or descriptor extraction.

## Extract and export

This caller-code example accepts a log path and a new output directory. Choose an unused directory: exports are deliberately kept separate from the input log. It keeps the returned dictionary in `data`, exports molecular and atom tables, and records missing values without replacing them with zero.

```python
import json
import logging
from pathlib import Path
import sys
import pandas as pd
from autoqchem.gaussian_log_extractor import gaussian_log_extractor

logging.basicConfig(level=logging.INFO)
log_path = Path(sys.argv[1])
out = Path(sys.argv[2])
try:
    extractor = gaussian_log_extractor(str(log_path))
    extractor.check_for_exceptions()
    data = extractor.get_descriptors()
except Exception as exc:
    raise RuntimeError(
        f"Extraction failed for {log_path}: {type(exc).__name__}: {exc}"
    ) from exc

molecular = pd.DataFrame([data['descriptors']])
atoms = pd.DataFrame(data['atom_descriptors'])
labels = data['labels']
if len(atoms) != len(labels):
    raise ValueError('Atom-table/label length mismatch; inspect population sections')
atoms.insert(0, 'label', labels)
atoms.insert(0, 'atom_index', range(len(labels)))  # zero-based export index
molecular.insert(0, 'source_log', str(log_path))
atoms.insert(0, 'source_log', str(log_path))

missing = {
    'molecular': molecular.columns[molecular.isna().any()].tolist(),
    'atomic': {str(c): atoms.index[atoms[c].isna()].tolist()
               for c in atoms.columns if atoms[c].isna().any()},
    'optional_absent': [k for k in ('transitions', 'modes', 'mode_vectors')
                        if data[k] is None],
}
out.mkdir(parents=True, exist_ok=False)
(out / 'missing.json').write_text(json.dumps(missing, indent=2), encoding='utf-8')
molecular.to_csv(out / 'molecular.csv', index=False, na_rep='NA')
atoms.to_csv(out / 'atoms.csv', index=False, na_rep='NA')
for key in ('transitions', 'modes', 'mode_vectors'):
    if data[key] is not None:
        table = pd.DataFrame(data[key])
        if key == 'modes':
            table.insert(0, 'mode_number', range(1, len(table) + 1))
        table.to_csv(out / f'{key}.csv', index=False, na_rep='NA')
print(json.dumps(missing, indent=2))
```

## Read the results

`get_descriptors()` returns six keys. DataFrames become dictionaries of column lists; numeric-looking population values may remain strings. Explicitly convert selected columns with `pd.to_numeric(..., errors='raise')` before numerical analysis.

| Result | Meaning and conventions |
| --- | --- |
| `labels` | Element labels in original input atom order; the example adds a zero-based `atom_index`. Do not join molecules by row number without a verified atom mapping. |
| `descriptors` / `molecular.csv` | One molecule's scalar fields. `dipole` is in Debye; `electronic_spatial_extent` retains Gaussian's atomic-unit convention. `converged` is the unitless fraction of matched convergence answers equal to `YES`, not a Boolean success certificate. `zero_point_correction`, thermal energy/enthalpy/free-energy corrections and `E_zpe,E,H,G` use Hartree per particle. Other parsed values retain the original Gaussian log units; inspect their source headers before conversion or combining tables. |
| `atom_descriptors` / `atoms.csv` | Per-atom `X,Y,Z` geometry (angstroms), `VBur`, and available population/NMR/TD columns. Charges and populations retain Gaussian's electron-charge/electron-count conventions. `NMR_shift` is the parsed `Isotropic` shielding value, not a referenced chemical shift. |
| `VBur` | Unitless fraction of mesh points inside an atom-centered sphere occupied by any atom's van der Waals sphere, including the central atom. Default sphere radius is **3 angstroms**, mesh density 30 ticks per Cartesian axis. It is neither a percentage nor a measured reaction response. |
| `transitions` | Optional rows with `ES_transition` wavelength in **nm**, `ES_osc_strength` unitless oscillator strength, and `ES_<S**2>` spin expectation in Gaussian's convention. Absent TD gives `None`; an empty table means no matching transition lines. |
| `modes` | Harmonic-mode properties copied from Gaussian's vibration table: `Frequencies` in cm^-1, `Red masses` in amu, `Frc consts` in mDyne/angstrom, `IR Inten` in km/mol, Raman activities in angstrom^4/amu and depolarization ratios unitless. Exported `mode_number` starts at **1**, reconstructing the index discarded by `get_descriptors()`. See Gaussian's [frequency output documentation](https://gaussian.com/freq/) for table headings and thermochemistry conventions. |
| `mode_vectors` | Long table with `mode_number`, `axis` and `value`, containing Gaussian normal-coordinate components, not Cartesian geometries or thermally sampled displacements. Mode numbers start at **1**. Upstream drops the atom-index column during reshaping; preserve row order and do not treat these rows as independently identified atoms. |

Review warnings, `missing.json` and exported columns before feature selection. Missing scalar matches become `None`; missing APT/NMR data can produce empty or null columns. Missing NPA has a malformed upstream fallback that can introduce column `0` containing field-name strings or extra rows: treat that table as a parsing defect and obtain a suitable population-analysis log rather than using the strings as descriptors. Successful extraction alone does not establish completeness.

For multiplicities other than 1 or 3, upstream sets HOMO and LUMO to zero and derives zero electronegativity/hardness; these are unsupported placeholders. For triplets it uses alpha HOMO and beta LUMO. For supported cases `electronegativity = -(LUMO + HOMO)/2` and `hardness = (LUMO - HOMO)/2`, in the same energy units as the parsed orbitals. Scalar fields are searched in `freq` and then `opt`, so an `opt` match can overwrite a `freq` value. Inspect the relevant source section when that distinction matters.

Use verified molecular fields and explicitly mapped atomic fields as downstream features. Keep optional tables separate, preserve missingness and record extraction failures; do not silently substitute zeros or average conformers in this workflow.
