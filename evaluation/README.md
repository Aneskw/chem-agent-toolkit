# Existing skill comparison

This pilot compares the same deterministic tasks in two conditions:

1. **without skill**: a small independent baseline implementation in the evaluator;
2. **with skill**: the packaged skill script and its documented interface.

The evaluator reports four fixed metrics: execution success, output schema validity, expected-value accuracy, and invalid-input handling. This is a tool-level comparison: it tests whether packaging the procedure as a skill preserves reliable execution. It does not measure whether an LLM chooses to read or follow the document. An agent-level study must run the same prompts with and without `SKILL.md` and add success, retries, and cost metrics.

Run from the repository root with an environment containing RDKit:

```bash
python3 evaluation/compare_existing_skills.py --output evaluation/results/pilot.json
```

PubChem cases require network access. The task definitions and expected values are in `tasks.json`.
