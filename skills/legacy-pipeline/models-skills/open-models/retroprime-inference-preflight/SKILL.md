---
name: retroprime-inference-preflight
description: "Diagnose RetroPrime script, checkpoint-name and input-file readiness before inference, without loading the model."
license: MIT
---


# Check RetroPrime readiness

Use Python 3.10+ for the included helper. Obtain the full source from [RetroPrime](https://github.com/wangxr0526/RetroPrime/blob/a765b670b72fbfd512d0d437da8f27a95f9f0554/README.md) at `a765b670b72fbfd512d0d437da8f27a95f9f0554` and place the two verified model stages according to the runner you intend to use.

```bash
python <skill-dir>/scripts/preflight.py --source-root /path/to/RetroPrime --input products.txt
# When the real legacy runtime is separate, inspect files only:
python <skill-dir>/scripts/preflight.py --source-root /path/to/RetroPrime --input products.txt --skip-env-check
```

Input is a checkout and optional one-nonempty-SMILES-per-line file. The helper checks the source files and step-numbered weight paths used by the [pinned runner](https://github.com/wangxr0526/RetroPrime/blob/a765b670b72fbfd512d0d437da8f27a95f9f0554/run_example.sh), and warns about README/runner naming differences. It does not parse SMILES, verify checkpoint hashes, or prove that a renamed weight belongs to the correct stage.

Output JSON gives missing scripts/weights/modules, input errors and warnings. Exit **0** means those checks passed; `ready_to_attempt` does not mean model inference succeeded. Module visibility concerns the Python interpreter running this helper. `--skip-env-check` yields file-only readiness and cannot certify a separate Python environment.

The source README's linked archive may use generic weight names. Inspect it rather than renaming arbitrarily. If you choose explicit alternate weight paths, this fixed-layout preflight is not their validator: configure and record those paths in your actual runner. Once ready, execute the selected **upstream** runner or your explicit-path launcher from the checkout; no sibling Skill is required.

Exit **2** is a preparation issue, not evidence that RetroPrime predicts incorrectly. This helper never starts inference or downloads weights.
