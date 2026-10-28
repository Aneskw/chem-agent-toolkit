---
name: gln-constrained-retrosynthesis-search
description: "Run GLN single-step retrosynthesis with its real RetroGLN interface, compatible cooked data/checkpoint, optional reaction class, and explicit no-support handling."
license: undetermined
---


# GLN constrained single-step retrosynthesis

Environment: [GLN source and setup](https://github.com/Hanjun-Dai/GLN/tree/b5bd7b181a61a8289cc1d1a33825b2c417bed0ef), its compiled chemistry/GNN extensions, compatible legacy RDKit/PyTorch environment and CUDA GPU. At this revision `RetroGLN` calls `.cuda()` unconditionally; this interface has no CPU switch. Follow the pinned README rather than mixing current PyTorch with historical binary extensions.

Input: single-product SMILES, GLN `dropbox` data root with its matching cooked templates/features, checkpoint directory containing `args.pkl` and `model.dump`, positive beam size/top-k, optional reaction class from the checkpoint's vocabulary (`UNK` when unknown). Use trusted model files.

## Usage

From the installed/accessible source environment:

```python
from gln.test.model_inference import RetroGLN

model = RetroGLN(dropbox='/data/gln/dropbox', model_dump='/data/gln/checkpoint')
result = model.run('CCOC(=O)c1ccccc1', beam_size=50, topk=10, rxn_type='UNK')
if result is None or not result['reactants']:
    print('No supported proposal returned')
else:
    for reactants, template, score in zip(
        result['reactants'], result['template'], result['scores']
    ):
        print(reactants, template, float(score))
```

The implementation matches product-center patterns, restricts templates by reaction class, applies compatible templates and ranks generated reactants. `beam_size` controls the search, while `topk` truncates returned proposals. Template matching is a support condition, not proof of reaction feasibility.

Output keys are `reactants`, `template`, and `scores` in aligned order. Handle both `None` and empty lists. Returned scores are softmax-normalized over the retained top-k proposals; they are not calibrated success probabilities and change when the retained candidate set changes. Invalid inputs or inconsistent artifacts may raise errors rather than return `None`.

Source: [actual inference interface](https://github.com/Hanjun-Dai/GLN/blob/b5bd7b181a61a8289cc1d1a33825b2c417bed0ef/gln/test/model_inference.py).
