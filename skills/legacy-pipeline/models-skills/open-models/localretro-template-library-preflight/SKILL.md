---
name: localretro-template-library-preflight
description: "Check a LocalRetro template-extraction checkout, training CSV schema, class-label naming and visible dependencies before a batch extraction attempt."
license: MIT
---


# Check template-library inputs

Use Python 3.10+ for this helper and a LocalRetro checkout at `eba83e72efabeb854fec86c865e8743c295a8a1e`. Obtain it from [the upstream repository](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/README.md); the extractor lives in `preprocessing/Extract_from_train_data.py`. No model checkpoint is needed for this readiness check.

```bash
python <skill-dir>/scripts/preflight.py --source-root /path/to/LocalRetro --dataset USPTO_50K
```

Provide `data/<dataset>/raw_train.csv` with a `reactants>reagents>production` column and the complete `LocalTemplate/` source. Optional reaction classes are read from `class_train.csv`, not the README's alternative `train_class.csv` name.

Read JSON `missing_files`, `missing_modules`, `csv_error`, class-label availability and warnings. Exit **0** / `ready_to_attempt` means these checks passed, not that extraction succeeded. `--skip-env-check` reports `files_ready_environment_unchecked`; module visibility otherwise concerns the interpreter running this helper, not a separate environment.

If ready and extraction is requested, use the returned `working_directory` and `command`. The [fixed extractor](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/preprocessing/Extract_from_train_data.py) writes atom/bond template tables and metadata under `data/<dataset>/`; this helper does not run it, validate atom mapping, or verify the checkout commit. Record the actual revision separately.

Exit **2** reports missing or inconsistent prerequisites. Restore real source/data rather than inventing CSV rows to pass readiness. This package has no dependency on a sibling Skill.
