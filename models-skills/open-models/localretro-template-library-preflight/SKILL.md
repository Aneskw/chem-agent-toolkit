---
name: localretro-template-library-preflight
description: >-
  Check the source files, training-data schema and Python dependencies needed to build a LocalRetro template library. Invoke for: preparing a batch template-extraction run from a pinned LocalRetro checkout; do not use it as proof that templates were built or that retrosynthesis inference works.
license: MIT
compatibility: Python 3.10+; inspect target environment for RDKit, DGL, DGLLife, PyTorch, pandas and NumPy
allowed-tools: Bash, Read
---

# LocalRetro template-library preflight

Check whether the pinned LocalRetro checkout and selected training split are
ready for a batch template-extraction attempt. This is distinct from the
single-reaction `localretro-extract-local-template` skill. It does not create a
template library, train a model, or predict reactants.

## Credibility

**High confidence (Enforce strictly)** for reporting missing files, the
required training CSV column, visible Python modules and the implementation's
`class_train.csv` convention. The script is tested on complete and incomplete
synthetic file layouts. **Medium confidence (Need verification)** for the
suggested extraction command: actual execution needs the full dataset and
upstream environment, which are not bundled; no extraction result is claimed.

## Reference

- Wang et al., *JACS Au* 2021, DOI `10.1021/jacsau.1c00246`, describes local
  template derivation from mapped training reactions.
- Pinned `kaist-amsg/LocalRetro` commit
  `eba83e72efabeb854fec86c865e8743c295a8a1e`, specifically
  `preprocessing/Extract_from_train_data.py` and
  `LocalTemplate/template_extractor.py`. Source hashes are in
  `creation_pipeline/source_locks/2GFR874J.json`.
- The selected implementation reads `class_train.csv` while its README
  mentions `train_class.csv`; verify against the pinned code rather than
  assuming the README name.

## Input & Output

Input: `--source-root` pointing to a LocalRetro checkout and `--dataset`
matching its `data/<dataset>/` folder. The training CSV needs a
`reactants>reagents>production` column. Output is JSON with `ok`, readiness
status, missing files/modules, class-label availability, and a suggested
command. `execution_performed` is always false. Exit code 2 means blocked.

## Procedure Guidance

```bash
python scripts/preflight.py --source-root /path/to/LocalRetro --dataset USPTO_50K
```

Only after `ready_to_attempt`, and after separately reviewing source data and
compute requirements, run the suggested command from the reported working
directory. Keep the dataset provenance, preprocessing commit and extraction
logs. Do not substitute fabricated CSV rows to make preflight pass.

## Matters & Troubleshooting

- `--skip-env-check` checks file layout only; it cannot establish runtime
  readiness.
- Training data and pretrained weights are not part of this Skill package.
- File presence does not verify atom mapping, class balance, chemical validity
  or successful template extraction.
