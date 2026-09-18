---
name: localtransform-forward-prediction
description: >-
  Invoke for: checking whether the pinned LocalTransform forward-prediction package has the source files, weights, and preprocessing resources required for execution. Do not substitute another model or claim a prediction while resources are missing.
license: Unknown; upstream licensing requires clarification
allowed-tools: Read, Bash, Write
---

# LocalTransform forward prediction (blocked-resource check)

The current evidence bundle is missing required upstream files, so the accepted behavior is an explicit resource report. This skill does not generate product predictions.

## Credibility

Status: `blocked_upstream_missing_files`. The repository snapshot has not passed a model execution test, and the upstream license still requires clarification. A readable README command is not evidence that the package is runnable.

## Reference

- Paper: https://doi.org/10.1038/s42256-022-00526-z
- Upstream commit: `1b763f20e4d1df560d15aab2a61291fe0c50fae3`
- [Upstream README](https://github.com/kaist-amsg/LocalTransform/blob/1b763f20e4d1df560d15aab2a61291fe0c50fae3/README.md)

## Input and output

Input: reactant SMILES plus the matching source checkout, model weights, and preprocessing files. Current output is a structured missing-resource report; it is not a product prediction.

## Procedure

Run the repository preflight from the ChemSkillNet root:

```bash
python3 skills/localtransform-forward-prediction/scripts/preflight.py evidence/LocalTransform
```

## Fixed cases

Use [examples/cases.json](examples/cases.json) for one valid preflight request and one unsupported prediction request. With the current incomplete snapshot, the expected result is `blocked_resources`; the skill must not substitute another model or fabricate a product.

## Failure and recovery

Record missing decoders, weights, or preprocessing data as `blocked_resources`. Once complete resources are obtained, pin the source and license, implement an adapter, and run acceptance tests. Never use another model's output under the LocalTransform name.
