# RetroXpert resource contract

## Source and preprocessing

Obtain the upstream implementation from:

```bash
git clone https://github.com/uta-smile/RetroXpert.git
```

Use the repository's documented preprocessing code and record the exact commit,
dataset split, and generated-file hashes. The current Skill does not bundle a
drop-in inference adapter.

## Checkpoint

The pinned upstream Git tree includes the typed EGAT checkpoint. Download its
bytes from the exact commit and verify the resulting SHA-256 before use:

```bash
curl -L 'https://raw.githubusercontent.com/uta-smile/RetroXpert/321cc3daf2f3a7ac9ab5b37dde5b666b338e1ed5/checkpoints/USPTO50K_typed_checkpoint.pt' -o checkpoints/USPTO50K_typed_checkpoint.pt
shasum -a 256 checkpoints/USPTO50K_typed_checkpoint.pt
```

Its required path is:

```text
checkpoints/USPTO50K_typed_checkpoint.pt
```

This is the stage-1 checkpoint. The selected source snapshot does not establish
a complete stage-2 checkpoint acquisition path. Full reactant inference remains
`blocked_resources` until both stages' code, data, and weights are pinned and
verified; no inference or accuracy claim is allowed here.
