---
name: retroprime-two-stage-inference-check
description: "Run RetroPrime product-to-synthon and synthon-to-reactant stages using a complete configured checkout and explicit matching checkpoint paths."
license: undetermined
---


# Run RetroPrime's two stages

Use a complete [RetroPrime checkout](https://github.com/wangxr0526/RetroPrime/blob/a765b670b72fbfd512d0d437da8f27a95f9f0554/README.md) at `a765b670b72fbfd512d0d437da8f27a95f9f0554` and its configured legacy environment. The upstream setup uses OpenNMT-py 0.4.1 and an older Python/PyTorch stack; the launcher itself needs Python 3.10+ and calls that separate interpreter through `--python`. No Docker setup or model installation is performed by this package.

Obtain both model stages from the archive linked by the fixed README. Its prose uses `_model.pt` filenames, whereas its runner uses `_model_step_90000.pt` / `_model_step_100000.pt`. **Inspect the archive and identify the actual matching P2S/S2R weights; pass those paths explicitly.** Do not rename an unrelated model to satisfy a filename.

Input: a UTF-8 file with one nonempty product SMILES per line, the full source checkout and both weights. Example:

```bash
python <skill-dir>/scripts/run_inference.py --source-root /path/to/RetroPrime   --python /path/to/retroprime-env/bin/python --input products.txt   --p2s /path/to/verified-p2s.pt --s2r /path/to/verified-s2r.pt   --output-dir ./prediction-01 --beam 10 --gpu 0
```

Use a new output directory. `--gpu` selects a visible physical GPU; `-1` requests the upstream translator's CPU mode, which still requires a compatible runtime. The helper runs tokenizer → P2S → stage-two preparation → S2R → reranking using the [fixed runner's arguments](https://github.com/wangxr0526/RetroPrime/blob/a765b670b72fbfd512d0d437da8f27a95f9f0554/run_example.sh). It does not treat first-stage synthons as final reactants.

Read JSON `status`, `completed_stages`, `prediction_file` and `output_nonempty`. Final results are in `reactants_predicted_mix.txt`; intermediate predictions, per-stage logs and `run.json` are retained together. Keep input-row order when interpreting beam blocks and preserve raw output rather than treating it as a calibrated probability table.

Exit **0** / `completed` means subprocesses completed and expected files exist, not that a prediction is chemically correct. Inspect empty/invalid predictions explicitly. Exit **2** reports bad prerequisites or a failed stage; the report/logs identify where to resume diagnosis. Input SMILES chemistry is interpreted by the target tokenizer, not validated by the standard-library launcher.

This package is independently usable with its declared checkout/runtime/weights; it has no dependency on another Skill. Source and artifact identity remain the user's preparation contract; computed hashes provide provenance, not proof that a supplied weight belongs to the right stage.
