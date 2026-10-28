---
name: localretro-single-step-retrosynthesis
description: "Generate ranked one-step LocalRetro precursor candidates from a connected product SMILES using pinned source and a matching user-supplied model/template set."
license: CC-BY-NC-SA-4.0 (upstream README; see references)
---


# LocalRetro one-step prediction

Use the included CPU adapter with Python 3.11 and compatible RDKit, PyTorch, DGL, DGLLife, pandas and NumPy. The adapter uses `torch.load(..., weights_only=True)`; use a PyTorch version supporting that option and a matching DGL build. The [pinned upstream setup](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/README.md) supplies the original environment requirements; its older example environment is not a guarantee for every modern dependency combination.

Obtain source at `eba83e72efabeb854fec86c865e8743c295a8a1e` and the compatible templates/weights as described in [resource preparation](resources/RESTORE.md). No weights are bundled. Keep the upstream CC-BY-NC-SA-4.0 terms.

```bash
python <skill-dir>/scripts/predict_localretro.py --source-root /path/to/LocalRetro   --product 'CC(=O)Nc1ccccc1' --top-k 10
```

Input is one connected product containing a bond; `top-k` is 1–100. Atom-map labels are removed. The adapter verifies the source, configuration, template and weight hashes before loading the model.

Require exit **0** and `ok:true`. Read `candidates[*].reactants_smiles`, `rank`, `model_score` and `local_template`; retain commit, weight hash and elapsed time. The model's requested edit candidates may decode to fewer unique valid precursors. Scores are not calibrated probabilities or experimental success estimates. Empty, invalid, disconnected or resource-mismatched requests return exit **2** and a JSON error.

For an intentionally retrained model with the **same source/configuration interface**, use `--manifest /path/to/reviewed-assets.json`. It must have the same paths as `scripts/inference_manifest.json`; only the three template CSV digests and checkpoint digest may change. Register the coherent artifact set and training provenance first. Do not recompute hashes merely to hide a mismatch. Other source/config changes require adapting and reviewing the wrapper.

This is single-step generation, not route planning or chemical feasibility validation.
