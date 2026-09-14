# Existing skill comparison

This pilot compares the same deterministic tasks in two conditions:

1. **without skill**: a small independent baseline implementation in the evaluator;
2. **with skill**: the packaged skill script and its documented interface.

The evaluator reports four fixed metrics: execution success, output schema validity, expected-value accuracy, and invalid-input handling. This is a tool-level comparison: it tests whether packaging the procedure as a skill preserves reliable execution. It does not measure whether an LLM chooses to read or follow the document. An agent-level study must run the same prompts with and without `SKILL.md` and add success, retries, and cost metrics.

## Evaluation granularity

Each skill is evaluated in its own task group. The primary score is reported per skill because inputs, outputs, dependencies, and correctness criteria are not interchangeable. A cross-skill average is only a secondary coverage summary and must not be presented as a single capability score.

| Skill group | Task contract | Primary correctness signal | Current lane |
| --- | --- | --- | --- |
| `chem-pubchem-query` | identifier → PubChem record | CID and property match, explicit no-match error | executable |
| `chem-rdkit-descriptors` | SMILES → descriptor JSONL | descriptor values and invalid-input handling | executable |
| `localretro-single-step-retrosynthesis` | product SMILES → reactant candidates | schema, deterministic normalization, resource/runtime status | resource-dependent |
| `retroprime-two-stage-retrosynthesis` | product SMILES → two-stage candidates | both stages complete and candidate schema | resource-dependent |
| `wln-build-molecular-graph` | molecule/reaction → graph features | graph shape and feature invariants | interface-only |
| `retroxpert-evaluate-bond-disconnection` | target → bond edits | edit schema and model execution | blocked resources |
| `localtransform-forward-prediction` | reactants → products | product schema and model execution | blocked resources |

Run from the repository root with an environment containing RDKit:

```bash
python3 evaluation/compare_existing_skills.py --output evaluation/results/pilot.json
```

PubChem cases require network access. The task definitions and expected values are in `tasks.json`.

The separate LLM ablation protocol is in [`agent_eval_protocol.md`](agent_eval_protocol.md), with concrete prompts in [`agent_tasks.json`](agent_tasks.json).
