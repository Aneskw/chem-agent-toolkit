---
name: retroxpert-evaluate-bond-disconnection
description: >-
  Invoke for: checking or running the RetroXpert typed EGAT bond-disconnection evaluation when the USPTO-50K data, checkpoint, and test configuration are available. Do not use for immediate route generation or unverified accuracy claims.
license: MIT (upstream code)
allowed-tools: Read, Bash, Write
---

# RetroXpert bond-disconnection evaluation

This package currently performs a resource check for the typed EGAT evaluation. It must not produce a prediction or accuracy number until the matching checkpoint, preprocessed data, and environment are available.

## Credibility

Status: `blocked_resources`: `checkpoints/USPTO50K_typed_checkpoint.pt` is missing in the evidence bundle. No inference or accuracy benchmark has been run.

## Reference

- Fixed source record: `../../evidence/RetroXpert/repo.json`, commit `321cc3daf2f3a7ac9ab5b37dde5b666b338e1ed5`
- [Upstream training/evaluation entry](../../evidence/RetroXpert/train.py)
- [Upstream README](../../evidence/RetroXpert/readme.md)

## Input and output

Input: matching preprocessed USPTO-50K data, typed EGAT weights, and a test configuration. Current output is only a checkpoint-presence report; file presence alone does not establish scientific validity.

## Procedure

```bash
python3 -c 'from pathlib import Path; import json,sys; p=Path("evidence/RetroXpert/checkpoints/USPTO50K_typed_checkpoint.pt"); ready=p.is_file(); print(json.dumps({"checkpoint":str(p),"present":ready,"scope":"checkpoint presence only"})); sys.exit(0 if ready else 2)'
```

## Fixed cases

Use [examples/cases.json](examples/cases.json) for one valid resource-preflight request and one unsupported inference request. With the current snapshot, the expected result is `blocked_resources`; no bond-disconnection accuracy may be claimed.

## Failure and recovery

Exit with `blocked_resources` when the checkpoint or data is missing. After resources are restored, pin and hash them, verify the environment, implement the adapter, and then benchmark. Do not bypass the check or substitute another model.
