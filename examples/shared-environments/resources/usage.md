# RDKit molecular descriptors

Source entrypoints: https://www.rdkit.org/docs/GettingStartedInPython.html and
https://www.rdkit.org/docs/source/rdkit.Chem.Descriptors.html .
Read the official current documentation and relevant version before writing or selecting an environment.

A candidate workflow accepts user SMILES, reports parse failures, and calculates molecular weight
with the RDKit API. It should explain input/output meaning without inventing scientific screening
thresholds. Typical invocation to investigate:

```python
from rdkit import Chem
from rdkit.Chem import Descriptors
mol = Chem.MolFromSmiles("CCO")
if mol is None:
    raise ValueError("Invalid SMILES")
print(Descriptors.MolWt(mol))
```

No RDKit version has been pinned by this input; the environment Agent must resolve and cite one.
