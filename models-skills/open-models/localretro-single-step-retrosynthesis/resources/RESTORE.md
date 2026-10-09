# LocalRetro resource restore contract

## Pinned source

Clone the upstream repository and check out the exact implementation revision:

```bash
git clone https://github.com/kaist-amsg/LocalRetro.git
cd LocalRetro
git checkout eba83e72efabeb854fec86c865e8743c295a8a1e
```

The required source files, templates, and checkpoint are listed with SHA-256
in [`scripts/inference_manifest.json`](../scripts/inference_manifest.json).
The manifest is the acceptance contract; a different file or commit is not a
drop-in replacement.

## Data and checkpoint acquisition

The upstream README documents the required data and training layout at
https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/README.md.
It does not publish a direct pretrained-checkpoint URL. Therefore this Skill
is not executable from a clean checkout until the owner supplies the artifact;
keep its state as `blocked_resources` rather than guessing a download link.
If a licensed artifact is supplied, record its URL or internal artifact ID and
archive hash, then place it at the manifest path:

- `data/USPTO_50K/atom_templates.csv`
- `data/USPTO_50K/bond_templates.csv`
- `data/USPTO_50K/template_infos.csv`
- `models/LocalRetro_USPTO_50K.pth`

The reproducible fallback is to train from the pinned checkout using the
upstream README's training command, then hash the resulting checkpoint.

Use [`localretro-template-library-preflight`](../../localretro-template-library-preflight/SKILL.md)
to check the dataset preprocessing inputs before inference. Do not substitute
another USPTO split or silently retrain a model.

## Runtime

Install the upstream dependencies from the pinned checkout, including RDKit,
DGL/PyTorch and the versions required by that revision. Then run the packaged
wrapper:

```bash
python3 scripts/predict_localretro.py \
  --source-root /path/to/LocalRetro \
  --product 'CC(=O)Nc1ccccc1' --top-k 10
```

Missing or hash-mismatched files are `blocked_resources`. Preserve the JSON,
stderr, commit, device, and model hash in the run record.
