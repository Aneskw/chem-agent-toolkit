---
name: aggregate-augmented-reaction-predictions
description: "Merge predictions for equivalent randomized reaction inputs, canonicalize molecular agreement, and rank by occurrence without treating frequency as a calibrated probability."
license: undetermined
---


# Aggregate augmented reaction predictions

Use after a configured reaction predictor has produced beams for several SMILES representations of the same input. This Skill consumes predictions; it does not supply a trained predictor.

Input: records grouped by reaction ID and augmentation ID, each with an ordered beam of predicted SMILES. Require the same prediction direction and sampling settings across groups. Output: ranked canonical candidates, counts, invalid counts, and the counting convention.

## Usage

With RDKit installed, this example counts each molecule once per augmentation beam, preserving stereochemistry and fragment multiplicity while ignoring atom maps:

```python
from collections import Counter
from rdkit import Chem

def canonical(smi):
    mol = Chem.MolFromSmiles(smi)
    if mol is None or mol.GetNumAtoms() == 0:
        return None
    for atom in mol.GetAtoms():
        atom.SetAtomMapNum(0)
    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)

beams = [['CCO', 'OCC', 'CC=O'], ['OCC', 'CC=O']]
counts, invalid = Counter(), 0
for beam in beams:
    valid = [canonical(s) for s in beam]
    invalid += sum(s is None for s in valid)
    counts.update(set(s for s in valid if s is not None))
ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
print(ranked, {'augmentations': len(beams), 'invalid': invalid})
```

This is a declared aggregation convention, not a claim that all paper experiments used this denominator. Raw occurrence counting across all beams is another policy; record which was used and do not mix the two. Leave reactions with no valid predictions in evaluation denominators. Counts measure agreement under correlated sampling, not synthesis feasibility or calibrated probabilities. Do not invent confidence intervals or automatic stopping thresholds from counts alone.

Source: [augmentation and frequency-ranking study](https://www.nature.com/articles/s41467-020-19266-y).
