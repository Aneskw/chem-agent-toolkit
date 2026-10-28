# LocalRetro resources

```bash
git clone https://github.com/kaist-amsg/LocalRetro.git
cd LocalRetro
git checkout eba83e72efabeb854fec86c865e8743c295a8a1e
```

Prepare the dependencies in the [fixed README](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/README.md). The wrapper runs in the invoking Python environment, so its RDKit/PyTorch/DGL builds must be compatible.

`scripts/inference_manifest.json` in this package records expected source and artifact hashes. Provide:

- `data/USPTO_50K/atom_templates.csv`
- `data/USPTO_50K/bond_templates.csv`
- `data/USPTO_50K/template_infos.csv`
- `models/LocalRetro_USPTO_50K.pth`

The inspected README does not supply a direct public pretrained-checkpoint URL. Obtain the matching artifact set from its owner or use an intentionally trained compatible set with a separately reviewed `--manifest`. The fixed manifest is not satisfied by any arbitrary file with the expected name.

For data-library preparation, the checkout expects `data/<dataset>/raw_train.csv` with `reactants>reagents>production`; optional class labels are read from `class_train.csv`. From `preprocessing/`, upstream `python Extract_from_train_data.py -d USPTO_50K` writes the template tables; `python Run_preprocessing.py -d USPTO_50K` assigns them to data. From `scripts/`, `python Train.py -d USPTO_50K` trains a model. These are optional resource-production paths, not steps that the inference adapter runs.

Raw data/splits and retrained weights are user-managed resources; record their provenance and compatible template vocabulary. No other Skill package is required.
