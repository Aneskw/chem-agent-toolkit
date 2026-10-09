# USPTO-50K resource restore contract

This Skill validates a local dataset. It does not redistribute the USPTO data,
and this repository does not pin a single legally redistributable download URL.
The dataset is derived from patent reaction records; different projects ship
different atom-mapping, filtering, and split conventions under the same name.

## Required provenance before validation

Create a run record with:

```yaml
dataset: USPTO50K
source_url: <the URL or internal artifact used to obtain the data>
source_revision: <release, archive hash, or commit>
preprocessing_repo: <repository URL, if preprocessing was performed>
preprocessing_commit: <commit or release>
atom_mapping_policy: <mapping tool/version or none>
split_convention: <named split release or project convention>
license: <license/terms accepted by the operator>
```

Do not substitute a random GitHub CSV for a missing dataset. The following are
valid implementation references, not claims that they provide a canonical
download of USPTO-50K:

- [LocalRetro](https://github.com/kaist-amsg/LocalRetro)
- [RetroPrime](https://github.com/wangxr0526/RetroPrime)
- [RetroXpert](https://github.com/uta-smile/RetroXpert)
- [Retro*](https://github.com/binghong-ml/retro_star)

## Restore and validate

1. Obtain the licensed archive from the dataset owner or the project release
   named in the run record.
2. Extract only into a private working directory, preserving the archive hash.
3. Place the three files at `train.csv`, `valid.csv`, and `test.csv`, or pass
   their containing directory to `scripts/validate_split.py`.
4. Run:

```bash
python3 scripts/validate_split.py --data-dir /path/to/uspto50k_data
```

5. Save stdout, stderr, exit code, the provenance record, and the validator
   JSON together. A missing source is `blocked_resources`, not an empty or
   synthetic dataset.
