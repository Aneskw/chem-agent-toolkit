---
name: rdkit-compare-molecular-inertia-shapes
description: Calculate RDKit normalized principal moments from prepared 3D SDF conformers and compare molecular shape distributions across labeled collections.
---

# Compare molecular shapes with normalized inertia

## Prepare the environment and structures

Use RDKit **2026.9.1** with Python 3.11. Obtain the matching wheel from the [RDKit PyPI release](https://pypi.org/project/rdkit/2026.9.1/) following the [official installation instructions](https://www.rdkit.org/docs/Install.html#cross-platform-using-pip):

```sh
python -m pip install rdkit==2026.9.1
```

Supply consistently prepared 3D structures for every collection. Conformer generation, optimization, protonation, salt handling and ensemble selection are upstream inputs. Use the same preparation and hydrogen policy across collections: changing the atoms or selected geometry changes the inertia calculation.

For the normal path, export **one selected conformer per molecule as one SDF record**. Give each record a nonempty, unique title (`_Name`) within its collection. Keep the external preparation record linking that structure to its original molecule and selected conformer. An imported conformer's RDKit ID is local to the imported molecule; do not reuse a pre-export ensemble index as its ID.

| Input/setting | Meaning |
| --- | --- |
| `inputs` below | Collection labels mapped to externally supplied SDF paths; replace the illustrative names. |
| `sanitize=True`, `strictParsing=True` | Parse and sanitize structures; invalid records stop this example. |
| `removeHs=False` | Retain explicit hydrogens supplied in the SDF; no hydrogens or coordinates are generated. |
| `cid` | ID of the sole imported conformer; passed identically to every descriptor. |
| `useAtomicMasses=True` | Mass-weighted moments, also the upstream default. Keep fixed across collections. |

## Calculate and export

Run this template in the prepared Python environment after replacing the two input paths. It validates all records before writing a new `shape-ratios.csv`; an existing output file causes an error. It does not alter the input files. `Is3D()` checks a conformer's flag, not the quality of its preparation; finite coordinates and nonzero inertia are additional checks.

```python
import csv
import math
from pathlib import Path
from rdkit import Chem, rdBase
from rdkit.Chem import Descriptors3D

inputs = {"collection": Path("prepared/collection.sdf"),
          "reference": Path("prepared/reference.sdf")}
rows = []
for collection, path in inputs.items():
    seen = set()
    supplier = Chem.SDMolSupplier(str(path), sanitize=True,
                                  removeHs=False, strictParsing=True)
    count = 0
    for record, mol in enumerate(supplier, start=1):
        label = f"{path}: record {record}"
        if mol is None:
            raise ValueError(f"{label}: SDF parsing/sanitization failed")
        ident = mol.GetProp("_Name").strip() if mol.HasProp("_Name") else ""
        if not ident or ident in seen:
            raise ValueError(f"{label}: missing or duplicate molecule title")
        seen.add(ident)
        if mol.GetNumConformers() != 1:
            raise ValueError(f"{label}: supply exactly one selected conformer")
        conf = mol.GetConformer()
        cid = conf.GetId()
        if not conf.Is3D():
            raise ValueError(f"{label}: conformer is not flagged as 3D")
        for atom in range(mol.GetNumAtoms()):
            p = conf.GetAtomPosition(atom)
            if not all(math.isfinite(v) for v in (p.x, p.y, p.z)):
                raise ValueError(f"{label}: nonfinite coordinates")
        kw = dict(confId=cid, useAtomicMasses=True)
        pmi = [fn(mol, **kw) for fn in
               (Descriptors3D.PMI1, Descriptors3D.PMI2, Descriptors3D.PMI3)]
        if not all(math.isfinite(v) for v in pmi) or pmi[2] <= 0:
            raise ValueError(f"{label}: degenerate or nonfinite inertia")
        npr1 = Descriptors3D.NPR1(mol, **kw)
        npr2 = Descriptors3D.NPR2(mol, **kw)
        if not all(math.isfinite(v) for v in (npr1, npr2)):
            raise ValueError(f"{label}: nonfinite normalized ratios")
        rows.append(dict(collection=collection, molecule_id=ident,
                         source_sdf=str(path), record=record, conf_id=cid,
                         use_atomic_masses=True, rdkit_version=rdBase.rdkitVersion,
                         PMI1=pmi[0], PMI2=pmi[1], PMI3=pmi[2],
                         NPR1=npr1, NPR2=npr2))
        count += 1
    if count == 0:
        raise ValueError(f"{path}: no usable molecules")
    print(collection, count)

out = Path("shape-ratios.csv")
with out.open("x", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(out.resolve())
```

For an already loaded molecule with several conformers, the alternative handoff is an explicitly selected **conformer ID**. Validate it with `mol.GetConformer(cid)`, then use that same `cid` and mass setting for PMI1–3 and NPR1–2. Do not average conformers or choose one implicitly when comparing collections.

The [SDF reader reference](https://www.rdkit.org/docs/source/rdkit.Chem.rdmolfiles.html#rdkit.Chem.rdmolfiles.SDMolSupplier) documents reader settings and SDF properties. The [descriptor reference](https://www.rdkit.org/docs/source/rdkit.Chem.Descriptors3D.html) explains PMI/NPR arguments; the [2026.09.1 source](https://github.com/rdkit/rdkit/blob/Release_2026_09_1/rdkit/Chem/Descriptors3D.py) pins this interface.

## Compare and interpret the output

`shape-ratios.csv` contains one row per supplied molecule, its collection and input locator, the imported conformer ID, software/mass settings, optional retained raw moments, and the dimensionless pair:

- `NPR1 = I1 / I3`, where `I1` is the smallest principal moment.
- `NPR2 = I2 / I3`, where `I2` is the middle moment and `I3` the largest.

Import the CSV into a plotting application and overlay a scatter plot with **NPR1 on x, NPR2 on y**, coloring by `collection`. Use common axes spanning 0–1 for all sets. Ideal reference positions are rod-like `(0, 1)`, disk-like `(0.5, 0.5)`, and sphere-like `(1, 1)`; these are geometric landmarks, not class cutoffs. Compare where each collection occupies or overlaps this space and report each collection's molecule count. For unequal collection sizes, point counts alone do not establish enrichment; any density comparison needs consistent settings and normalization within each collection.

The shape-region orientation follows [Aoyama et al., Figure 6d](https://doi.org/10.1002/chem.202303027): rod-like at top-left, disk-like at bottom-middle, sphere-like at top-right. Coordinates describe the chosen conformer's mass distribution. They do not establish bioactivity, molecular size or the shape distribution of an unselected conformational ensemble.

A parsing failure, absent/ambiguous conformer, missing identity, nonfinite value or zero largest moment stops the example instead of silently changing the compared population. Resolve the identified input record through the upstream preparation workflow. An empty collection produces no comparison. If a legitimate planar structure loses its 3D flag on export, verify its coordinate provenance before adapting that flag check; a 3D flag alone cannot distinguish prepared geometry from a drawing.
