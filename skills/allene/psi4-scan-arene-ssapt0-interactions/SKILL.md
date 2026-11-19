---
name: psi4-scan-arene-ssapt0-interactions
description: Compute Psi4 sSAPT0/jun-cc-pVDZ distance scans for prepared neutral closed-shell arene pairs, collecting scaled interaction energies and their components.
---

# Arene-pair interaction scans with Psi4

Evaluate supplied probe geometries at prescribed separations and retain one row per conformer and distance. This workflow performs single-point calculations; probe design, geometry optimization, interpolation of equilibrium distances and conformer averaging are separate inputs or downstream tasks.

## Environment and prepared inputs

Use **Psi4 1.11**, obtained through the [official 1.11 installation selector](https://psicode.org/installs/v111/). Follow its platform-specific setup and use the Python interpreter in that environment. The [matching PsiAPI guide](https://psicode.org/psi4manual/1.11.x/psiapi.html) describes Python operation. Provide writable output and Psi4 scratch locations, with memory and disk capacity appropriate to the probe sizes.

Prepare a directory containing `scan.json` and the geometry files it names:

| Input | Contract |
|---|---|
| `conformer` | Identifier for a fixed relative orientation/conformer. |
| `distance_angstrom` | Numeric scan coordinate in angstrom; define its geometric meaning consistently, such as a specified interplanar separation. |
| `geometry_path` | Path relative to the manifest directory, containing the already placed two-fragment geometry at that distance. |

For example, the manifest structure is:

```json
[
  {"conformer": "edge-face-a", "distance_angstrom": 3.0, "geometry_path": "edge-face-a-3.0.dat"},
  {"conformer": "edge-face-a", "distance_angstrom": 3.5, "geometry_path": "edge-face-a-3.5.dat"}
]
```

These names and separations illustrate the input format; supply the actual geometries and grid for the intended investigation. The distance field labels the supplied coordinates: the code does **not** move atoms to that distance.

Each geometry file must be a Psi4 molecule specification in Cartesian form: `0 1`, atom lines `Element x y z` for the first neutral singlet probe, `--`, `0 1`, atom lines for the second probe, and `units angstrom`. Do not include a surrounding `molecule {...}` block or an XYZ atom-count/comment header. Keep internal geometries and relative orientation consistent within each scan. Use Cartesian coordinates because the SAPT manual documents problems with some highly symmetric Z-matrix inputs.

## Run the scan

Run the following Python example from the directory containing the prepared manifest. It reads the geometry files without modifying them and writes `scan.csv` and `scan.out` in the current directory, replacing existing files of those names. Use a fresh Python session so options from unrelated calculations do not carry over.

```python
import csv
import json
from pathlib import Path
import psi4

manifest = Path("scan.json").resolve()
points = json.loads(manifest.read_text(encoding="utf-8"))
if not points:
    raise ValueError("scan.json contains no scan points")

psi4.set_output_file("scan.out", False)
psi4.set_options({
    "reference": "rhf",
    "scf_type": "df",
    "freeze_core": True,
    "df_basis_elst": "jun-cc-pvdz-jkfit",
})

components = {
    "total_Eh": "SSAPT0 TOTAL ENERGY",
    "elst_Eh": "SSAPT0 ELST ENERGY",
    "exch_Eh": "SSAPT0 EXCH ENERGY",
    "ind_Eh": "SSAPT0 IND ENERGY",
    "disp_Eh": "SSAPT0 DISP ENERGY",
}
fields = [
    "conformer", "distance_angstrom", "geometry_path",
    *components, "total_kcal_mol",
]

with Path("scan.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for point in points:
        geometry_path = manifest.parent / point["geometry_path"]
        dimer = psi4.geometry(geometry_path.read_text(encoding="utf-8"))
        psi4.energy("ssapt0/jun-cc-pvdz", molecule=dimer)

        # Read immediately after this point succeeds.
        energies = {
            column: float(psi4.variable(key))
            for column, key in components.items()
        }
        writer.writerow({
            "conformer": point["conformer"],
            "distance_angstrom": float(point["distance_angstrom"]),
            "geometry_path": point["geometry_path"],
            **energies,
            "total_kcal_mol": (
                energies["total_Eh"] * psi4.constants.hartree2kcalmol
            ),
        })
        stream.flush()
```

The example explicitly chooses RHF monomers, density fitting and frozen-core correlation. Keep these settings consistent across comparisons; `freeze_core=True` is an example protocol choice, not an inferred setting from a particular dataset. Psi4 selects the matching auxiliary bases for the specified orbital basis; the explicit `df_basis_elst` selects the current JKFIT electrostatic fitting convention.

Use `ssapt0` and the **SSAPT0** output variables throughout. Requesting SAPT0 or setting `exch_scale_alpha=3` does not implement the same recipe. See the [SAPT manual's scaling discussion, equation 9](https://psicode.org/psi4manual/1.11.x/sapt.html) and [SAPT output-variable index](https://psicode.org/psi4manual/1.11.x/autodir_psivariables/module__sapt.html).

## Read the results

- `scan.csv` contains interaction energies in hartree (`*_Eh`) and the total in kcal/mol. `scan.out` contains the SCF/SAPT diagnostics and printed energy decomposition.
- Negative total interaction energy indicates attraction relative to noninteracting monomers. Electrostatics, exchange, induction and dispersion help interpret differences between geometries; they are calculated interaction components, not measured selectivities or reaction free energies.
- Compare points within each conformer using the declared distance definition. The lowest sampled energy is a grid minimum, not an interpolated equilibrium distance. A minimum at a grid endpoint does not locate an interior minimum.
- File/geometry errors, SCF failures or missing energy variables stop the example. A CSV left after failure can contain only the preceding successful points; check its rows against the manifest and inspect the log before treating it as a complete scan. An empty manifest is rejected.
- Keep the fitting convention fixed when comparing datasets. Psi4's SAPT manual documents a change from RI to JKFIT for `DF_BASIS_ELST` around v1.6 that affects sSAPT0 energies. For an explicitly required legacy RI protocol, consult that manual and set the specified RI auxiliary basis; do not assume equality with current-default energies.
