---
name: wln-build-molecular-graph
description: >-
  Invoke for: converting a molecule SMILES into the WLN atom, bond, neighbor, and adjacency features required by downstream WLN preprocessing. Do not use for full reaction prediction.
license: MIT (upstream code)
allowed-tools: Read, Bash, Write
---

# WLN molecular graph construction

Build the WLN-specific graph representation for one molecule. This package covers preprocessing only; it does not load a reaction-prediction checkpoint.

## Credibility

The patched Python 2 compatibility copy passed five checks: ethanol, benzene, batch masks, invalid input, and the packaged CLI. No model-weight inference or accuracy benchmark was performed.

## Reference

- Fixed source record: `../../evidence/WLN/repo.json`, commit `fb7dea369b0721b88cd0133a7d66348d244f65d3`
- [Graph implementation](../../evidence/WLN/USPTO-15K/core-wln-global/mol_graph.py)
- [Acceptance record](../../batch/runs/format-20260913/wln-graph/attempt-1/revision-1/acceptance.json)

## Input and output

Input: one SMILES through `--smiles`. Output JSON contains `ok`, `input_smiles`, and atom, bond, neighbor, and count arrays. These features are specific to this WLN implementation and are not automatically compatible with other models.

## Procedure

```bash
../../work/localretro/venv/bin/python batch/runs/format-20260913/wln-graph/attempt-1/revision-1/package/run.py --smiles CCO
```

Check exit code 0, `ok: true`, array dimensions, and adjacency consistency before passing the graph downstream.

## Fixed cases

Use [examples/cases.json](examples/cases.json) for three positive and one negative case. Expected checks cover ethanol, benzene, batch masks, feature shapes, neighbor counts, adjacency consistency, and explicit invalid-SMILES rejection.

## Failure and recovery

Invalid SMILES returns exit code 2 and `ok: false`. Restore RDKit/NumPy if dependencies are missing. Use the tested compatibility copy rather than modifying the evidence source. Stop on repeated or uncovered exceptions and preserve the input.
