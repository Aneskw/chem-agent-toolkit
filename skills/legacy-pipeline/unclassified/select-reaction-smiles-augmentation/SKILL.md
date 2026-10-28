---
name: select-reaction-smiles-augmentation
description: "Select training versus product-only inference augmentation, preserving molecular identity and keeping canonical copies and split groups intact."
license: undetermined
---


# Select reaction SMILES augmentation

Environment: RDKit and the configured reaction model's tokenizer/decoder. Input: product/reactant pairs for training, or product-only inputs for retrosynthesis inference, plus a desired augmentation count. Output: equivalent representations with original reaction IDs, suitable for that model's preprocessing.

## Usage

```python
from rdkit import Chem

mol = Chem.MolFromSmiles('CCOC(=O)c1ccccc1')
if mol is None:
    raise ValueError('Invalid product')
canonical = Chem.MolToSmiles(mol, isomericSmiles=True)
encodings = {canonical}
for _ in range(20):  # finite example budget, not a unique-count guarantee
    encodings.add(Chem.MolToSmiles(mol, canonical=False, doRandom=True,
                                  isomericSmiles=True))
print(sorted(encodings))
```

Keep a canonical copy. For training, randomize both sides and optionally permute reactant component order under the chosen protocol. Group and split equivalent reactions **before** augmentation. Retain original IDs so multiple encodings count as one chemical example at evaluation.

For retrosynthesis inference, randomize only the product; target reactants are unavailable. Small/symmetric molecules may yield fewer unique strings; bound retries and report actual unique counts. Preserve stereo, isotopes, charges and the checkpoint's atom-map convention. Text diversity must not become chemical-identity diversity.

Choose augmentation counts on validation data for the actual top-1/top-k objective. Mixed forward/reverse training needs the model's trained direction marker; do not add an arbitrary marker to an existing checkpoint. Aggregate predictions only under a declared canonicalization/counting policy.

Sources: [augmentation study](https://www.nature.com/articles/s41467-020-19266-y), [associated data and evaluation code](https://github.com/bigchem/synthesis), [RDKit SMILES interface](https://www.rdkit.org/docs/source/rdkit.Chem.rdmolfiles.html).
