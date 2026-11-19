---
name: psi4-compare-sapt0-interaction-components
description: Use Psi4 SAPT0 to decompose and compare electrostatic, exchange, induction and dispersion interaction energies for supplied, chemically validated pairs of molecular fragments at fixed geometries.
---

# Compare fragment interactions with Psi4 SAPT0

## Prepare the environment and inputs

Obtain **Psi4 1.11.0** from the [official installation selector](https://psicode.org/installs/v111/): select your platform, stable release and an installer or conda route. Use the Python environment provided by that installation for the PsiAPI example below. Windows users can select native Windows or the Linux route under WSL.

Supply two-fragment Cartesian coordinates, fragment charges and spin multiplicities, and a suitable orbital/auxiliary basis specification. Keep fragment membership and computational settings consistent across compared structures. Fragment assignment, geometry optimization, transition-state searches and distortion energies are separate inputs/workflows.

Create one UTF-8 geometry file per structure, such as `pair_A.geom` and `pair_B.geom`. These contain the body accepted by `psi4.geometry`, without a `molecule { ... }` wrapper or XYZ atom-count/comment header. Example format, using the manual's water dimer:

```text
0 1
O  -1.551007  -0.114520   0.000000
H  -1.934259   0.762503   0.000000
H  -0.599677   0.040712   0.000000
--
0 1
O   1.350625   0.111469   0.000000
H   1.680398  -0.373741  -0.758561
H   1.680398  -0.373741   0.758561
units angstrom
no_reorient
symmetry c1
```

Each `charge multiplicity` line describes the following fragment; `--` separates the two fragments. Replace the coordinates and electronic states with the supplied validated inputs for both structures. Declare `units angstrom` or `units bohr` explicitly. Cartesian coordinates, fixed orientation and C1 symmetry avoid SAPT geometry/symmetry problems.

## Choose consistent settings

The example uses the manual's light-element `aug-cc-pVDZ` basis family as an illustrative choice. Substitute the supplied suitable basis specification, including auxiliary bases, as a unit.

| Setting | Operational meaning |
| --- | --- |
| `basis` | Orbital basis; ensure coverage for every element. A larger basis does not automatically improve SAPT0: the manual recommends jun-cc-pVDZ for general closed-shell SAPT0 and cautions against large bases such as aug-cc-pVTZ. |
| `df_basis_sapt` | RI auxiliary basis for SAPT density fitting. |
| `df_basis_elst` | JKFIT auxiliary basis for electrostatics/exchange in current SAPT0. Before v1.6 this default was RI; mixing these choices can change components. |
| `freeze_core=True` | Explicitly follows the SAPT0 recommendation; the documented default is false. Affects dispersion/exchange-dispersion correlation. |
| `reference="rhf"` | Closed-shell singlet example. For open-shell inputs use UHF or ROHF; UHF retains coupled induction. ROHF uses uncoupled induction without orbital relaxation. |
| `scf_type="df"` | Density-fitted SCF; density fitting is also used by SAPT. |

Two open-shell monomers are coupled to the high-spin state by SAPT0. A requested low-spin pair requires a different, independently justified workflow. Keep the default dimer-centered basis and unscaled SAPT0 recipe for this comparison; sSAPT0 is a distinct result. For elements requiring custom basis/ECP treatment, establish method compatibility and all fitting bases before applying this template.

See the versioned [SAPT manual](https://psicode.org/psi4manual/1.11.x/sapt.html) for conditional settings and basis guidance.

## Run the decomposition and retain results

Save the following as `compare_sapt.py` beside the two supplied geometry files. Run `python compare_sapt.py` from that directory in the Psi4 environment. The code performs single-point calculations, writes `sapt-components.json` (overwriting that path), and prints the component differences in kcal/mol. The 2 GB memory allocation is an example; adjust it to available resources.

```python
import json
from pathlib import Path
import psi4

psi4.set_memory(2_000_000_000)
options = {
    "basis": "aug-cc-pvdz",
    "df_basis_sapt": "aug-cc-pvdz-ri",
    "df_basis_elst": "aug-cc-pvdz-jkfit",
    "freeze_core": True,
    "reference": "rhf",
    "scf_type": "df",
}
psi4.set_options(options)

names = {
    "electrostatic": "SAPT ELST ENERGY",
    "exchange": "SAPT EXCH ENERGY",
    "induction": "SAPT IND ENERGY",
    "dispersion": "SAPT DISP ENERGY",
    "total": "SAPT TOTAL ENERGY",
}
results = {}
for label, filename in [("A", "pair_A.geom"), ("B", "pair_B.geom")]:
    geometry_text = Path(filename).read_text(encoding="utf-8")
    dimer = psi4.geometry(geometry_text)
    psi4.energy("sapt0", molecule=dimer)
    # Capture now: the next energy() clears the PSI variable table.
    energies = {key: float(psi4.variable(var)) for key, var in names.items()}
    results[label] = {
        "input": filename,
        "geometry": geometry_text,
        "hartree": energies,
    }

factor = psi4.constants.hartree2kcalmol
delta = {
    key: (results["B"]["hartree"][key] - results["A"]["hartree"][key]) * factor
    for key in names
}
report = {
    "method": "SAPT0",
    "target_version": "1.11.0",
    "options": options,
    "structures": results,
    "B_minus_A_kcal_mol": delta,
}
Path("sapt-components.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8"
)
for key, value in delta.items():
    print(f"{key:14s} B-A = {value: .6f} kcal/mol")
```

The [PsiAPI guide](https://psicode.org/psi4manual/1.11.x/psithoninput.html#psi-variables) documents variable access, lifetime and unit conversion.

## Interpret and inspect

The five retrieved values are in **Hartree**. The four aggregate components sum to `SAPT TOTAL ENERGY`, the electronic **interaction** energy. Use these aggregates rather than substituting isolated low-order terms such as `SAPT IND20,R ENERGY`. Their definitions are listed in the [PSI variable glossary](https://psicode.org/psi4manual/1.11.x/glossary_psivariables.html#psivar-SAPT-TOTAL-ENERGY).

Negative interaction contributions are stabilizing; positive ones are destabilizing at the supplied geometry. With the defined B−A subtraction, a negative component difference favors B for that component. Compare signed differences alongside the total, since components can cancel. Check the sum against the reported total within numerical precision.

Inspect Psi4's calculation output for SCF and SAPT/CPHF convergence and actual orbital/fitting bases before interpreting a comparison. A calculation exception, nonconvergence or missing result variable is a failed calculation, not a zero component. Correct the input or convergence problem and rerun the affected comparison.

These are fixed-geometry electronic interaction energies. They alone do not establish an activation barrier, free-energy difference or stereoselectivity; those conclusions require the corresponding structures and other energy contributions.
