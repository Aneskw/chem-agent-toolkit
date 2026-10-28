---
name: check-mismatched-retrosynthesis-with-forward-prediction
description: "Check alternative reactant proposals against a target using supplied forward predictions, distinguishing model round-trip support from experimental validity."
license: undetermined
---


# Forward-check alternative reactants

Use when proposed reactants differ from the recorded reaction but may still be plausible. Input: target product, candidate reactant sets, and a configured forward predictor or its already generated product predictions. Preserve candidate IDs, predictor version, reagent assumptions, and rank. This Skill does not provide the forward model.

## Usage

For each candidate, prepare the reactants/reagents using that predictor's documented preprocessing and retain its predicted products. Compare them with the target after the same atom-map removal and stereochemistry-preserving canonicalization:

```python
from rdkit import Chem

def product_key(smi):
    mol = Chem.MolFromSmiles(smi)
    if mol is None or mol.GetNumAtoms() == 0:
        return None
    for atom in mol.GetAtoms():
        atom.SetAtomMapNum(0)
    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)

target = product_key('CCO')
predicted = product_key('OCC')  # replace with the forward model's product
verdict = 'unassessed' if target is None or predicted is None else (
    'round_trip_match' if target == predicted else 'round_trip_mismatch')
print(verdict)
```

Declare whether the test uses forward top-1 or any of top-k; checking more predictions changes the test. Do not silently discard salts, select the largest product, or ignore stereo to obtain a match. If such a policy is required, report it separately from exact matching.

Output per candidate: predicted product(s), comparison policy, and match/mismatch/unassessed. A match is support from another model, not proof of a feasible reaction. A mismatch can reflect missing conditions or forward-model error and does not prove the route invalid. Keep this evidence separate from benchmark exact-match accuracy.

Source: [G2Gs discussion of forward checking](https://arxiv.org/abs/2003.12725).
