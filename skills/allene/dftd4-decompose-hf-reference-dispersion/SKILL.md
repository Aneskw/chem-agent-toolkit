---
name: dftd4-decompose-hf-reference-dispersion
description: Calculate HF-reference DFT-D4 dispersion energies and additive contributions between supplied atom groups when comparing noncovalent contacts in prepared molecular geometries.
---

# HF-reference dispersion and atom-group contributions

Use DFT-D4 on fixed geometries to obtain a dispersion correction and resolve its additive contribution between selected groups. Here `hf` selects HF damping parameters; this API call does not run a Hartree-Fock electronic-structure calculation. Geometry optimization and transition-state validation are external.

## Environment and inputs

Use **DFT-D4 4.3.1**, its Python bindings and NumPy in Python 3. Follow the official [4.3.1 installation and Python API setup](https://github.com/dftd4/dftd4/blob/v4.3.1/README.md#installing). The documented Conda packages are `dftd4` and `dftd4-python`; obtain version 4.3.1, or use the tagged source-build instructions with Python support enabled. A standalone CLI installation alone is insufficient for the imports below.

Prepare these inputs without changing atom order:

| Input | Contract |
|---|---|
| `numbers` | Integer array of atomic numbers, shape `(N,)`. |
| `positions` | Cartesian coordinates, shape `(N, 3)`, **in bohr**. Convert angstrom coordinates before calling the API. |
| `charge` | Total molecular charge in elementary-charge units; supply it explicitly, especially for ions. |
| `A`, `B` | Nonempty, disjoint lists of unique, zero-based atom indices within this same geometry. Include hydrogens when defining complete fragments. |

This normal path uses a finite molecule, `model="d4"` and HF parameters with the ATM three-body contribution enabled. Groups may be selected moieties within a larger complex; unselected atoms remain part of the calculation.

## Calculate and save results

The following adaptable example uses the two-ammonia geometry from the upstream pairwise API example. Replace the geometry, charge and groups together with the prepared system of interest. This is a demonstration geometry; supply the structures needed for the intended comparison.

```python
import numpy as np
from dftd4.interface import DampingParam, DispersionModel

numbers = np.array([7, 7, 1, 1, 1, 1, 1, 1], dtype=int)
positions = np.array([  # bohr; preserve this atom order
    [-2.983345508575, -0.088082052767,  0.000000000000],
    [ 2.983345508575,  0.088082052767,  0.000000000000],
    [-4.079203605652,  0.257751166821,  1.529856562614],
    [-1.605268001556,  1.243804812431,  0.000000000000],
    [-4.079203605652,  0.257751166821, -1.529856562614],
    [ 4.079203605652, -0.257751166821, -1.529856562614],
    [ 1.605268001556, -1.243804812431,  0.000000000000],
    [ 4.079203605652, -0.257751166821,  1.529856562614],
])
charge = 0.0
A = np.array([0, 2, 3, 4], dtype=int)
B = np.array([1, 5, 6, 7], dtype=int)

model = DispersionModel(numbers, positions, charge=charge, model="d4")
param = DampingParam(method="hf", atm=True)
total_Eh = float(model.get_dispersion(param, grad=False)["energy"])
pairs = model.get_pairwise_dispersion(param)
E2 = pairs["additive pairwise energy"]
E3 = pairs["non-additive pairwise energy"]

# Each off-diagonal entry holds half the additive pair energy.
AB_Eh = float(E2[np.ix_(A, B)].sum() + E2[np.ix_(B, A)].sum())
print("Total D4 dispersion / Eh:", total_Eh)
print("Additive dispersion / Eh:", float(E2.sum()))
print("ATM dispersion / Eh:", float(E3.sum()))
print("Additive A-B contribution / Eh:", AB_Eh)

np.savez(
    "d4-hf-analysis.npz",
    numbers=numbers, positions_bohr=positions, charge=charge,
    group_a=A, group_b=B, model="d4", method="hf", atm=True,
    total_Eh=total_Eh, additive_pair_Eh=E2,
    nonadditive_pair_Eh=E3, additive_AB_Eh=AB_Eh,
)
```

The API returns results in memory and leaves the input geometry unchanged. The final NumPy call writes `d4-hf-analysis.npz` in the working directory and replaces a file of the same name. Use a distinct path for each structure. Read it later with `data = np.load("d4-hf-analysis.npz")`; for example, `data["additive_AB_Eh"].item()` retrieves the group contribution. Retain the saved indices and geometry alongside any reported value.

For another geometry, construct another model; changes to charge, atom identities or atom count require reconstruction. Use corresponding chemical group definitions when comparing structures.

## Interpret the decomposition

- `total_Eh` is the full D4 dispersion correction in hartree. The two `(N, N)` matrices separate additive dispersion from the pairwise representation of non-additive ATM dispersion; their full sums together recover the correction.
- For additive A-B attribution, sum both directional blocks as shown. Summing only one gives half the contribution; halving the complete symmetric matrix again also loses half.
- `E3` is a distribution of three-body terms over pairs. Keep it separate rather than interpreting each entry as an independent two-atom interaction.
- The group contribution uses the full complex's environment. It is not the result of recomputing isolated fragments, a total binding energy, or an activation free energy. A more negative additive contribution indicates greater modeled dispersion stabilization under this partition, not a complete explanation of selectivity.
- An all-zero contribution means no contribution was returned for that selection under the model and its cutoffs; it is not proof of no physical interaction. Confirm indices, coordinate units and geometry before interpreting it.

Malformed coordinate dimensions or an unknown model can raise `ValueError`; unavailable damping parameters or a failed library calculation can raise `RuntimeError`. Treat these as failed calculations, not zero energies. The [tagged Python interface](https://github.com/dftd4/dftd4/blob/v4.3.1/python/dftd4/interface.py) documents these contracts.
