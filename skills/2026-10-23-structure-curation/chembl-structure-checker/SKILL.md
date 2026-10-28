---
name: chembl-structure-checker
description: >
  Check one chemical structure supplied as a molblock for ChEMBL Structure Pipeline findings. Use when a user wants structure issues reported and explained, without changing the structure or deciding whether it should be accepted.
---

# ChEMBL Structure Checker

Use the ChEMBL Structure Pipeline checker to identify potential structure issues in one molblock. It reports findings; it does not correct the structure or set an acceptance policy.

## Input and output

Input is molblock text. The result is a tuple of `(penalty, description)` pairs. An empty tuple means the checker reported no findings for that input. Penalties indicate issue severity in this tool's scheme; review descriptions and scores as findings rather than a universal pass/fail decision.

## Usage

Install `chembl_structure_pipeline==1.2.4` with `pip install chembl_structure_pipeline`. The package declares RDKit `>=2022.09.01` as a dependency.

```python
from chembl_structure_pipeline import checker

molblock = """
  Mrv1810 02151908462D

  4  3  0  0  0  0            999 V2000
    2.2321    4.4196    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    3.0023    4.7153    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.4117    4.5059    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    1.9568    3.6420    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  1  0  0  0
  1  3  1  0  0  0  0
  1  4  1  0  0  0  0
M  END
"""

findings = checker.check_molblock(molblock)
for penalty, description in findings:
    print(penalty, description)
```

The package documents this example as returning `((5, 'InChi_RDKit/Mol stereo mismatch'),)`. A clean example returns `()`. An empty result means only that this checker reported no findings; it does not establish general scientific validity or determine whether a structure should be accepted.