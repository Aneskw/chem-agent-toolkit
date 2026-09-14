# Agent-level skill ablation

This protocol measures whether an agent benefits from reading a skill document. It is separate from the deterministic tool-level pilot in `compare_existing_skills.py`.

## Conditions

Run every task in `agent_tasks.json` twice with the same model, temperature, tool permissions, timeout, and working directory:

- **no-skill**: provide only the task request and repository/tool availability;
- **with-skill**: additionally provide the complete matching `SKILL.md` and its referenced files.

Randomize task order between conditions and keep the model version fixed. Do not give the agent the expected answer.

## Required run record

Store one JSON object per attempt with `task_id`, `condition`, `model`, `ok`, `output`, `exit_code`, `retries`, `elapsed_seconds`, and `input_tokens`/`output_tokens` when available. Preserve stderr and tool traces separately so a failure can be audited.

## Fixed metrics

- **Task success**: the requested operation completed and the answer is chemically correct.
- **Contract compliance**: required fields and error semantics are present.
- **Execution success**: the generated command or script exits with the expected code.
- **Recovery quality**: invalid inputs are rejected without fabricated values.
- **Efficiency**: retries, elapsed time, and token/API cost.

Report every metric per skill and per condition. Use paired differences (with-skill minus no-skill); do not average incompatible skills into one capability score. Four tasks are a pilot only. For a claim in a paper, expand each skill to a held-out set and repeat with multiple seeds or runs.

## Interpretation

The current repository can run the RDKit and PubChem task groups. The five model skills need their pinned resources before they can enter this agent-level experiment. A higher score with skill supports improved procedural guidance; it does not prove improved model chemistry knowledge.
