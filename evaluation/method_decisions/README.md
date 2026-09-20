# Paper-method decision pilot (non-LocalRetro)

For a complete copy-and-paste reproduction, see `RUN_THIS.md`.

This stage begins **after** `creation_pipeline/run_pipeline.py` renders a cited
method candidate. That extraction pipeline does not generate held-out positive
and negative tasks or demonstrate agent benefit by default. Its optional
`--draft-eval-tasks` flag now proposes task cards, but they require independent
review before any agent comparison. This pilot makes those steps explicit.

Source candidate: `skills/generated/verified20-LJMZ9IL6-resource-label-fix/predict-reaction-products-with-confidence-abstention/SKILL.md`, extracted from the forward reaction-prediction paper identified as `LJMZ9IL6` in the literature catalog. Its decision rule is: canonicalize a decoded product, then report it only when the top-1 probability meets a **validated, task-specific** threshold; otherwise abstain. A probability alone is not proof of calibration. The paper's 0.83 is an example, not a transferable default. Model weights are absent, so this pilot tests an agent's **reporting decision** on supplied predictions, not chemical prediction accuracy.

`tasks.json` contains new scenarios written for this pilot, with two applicable and two non-applicable/limiting cases. They are not copied examples from the source document. `oracle.json` holds the expected branches separately from the agent prompt. An evaluator should review the oracle before each formal run and should never include it in the model prompt. The same model receives each task with and without the skill document; attempts run in fresh empty directories and shuffled order. `run.py` records raw model responses, token usage, and exact branch scores. This is a four-task feasibility pilot, not statistically reliable proof of benefit.

Run from the repository root:

```bash
python3 evaluation/method_decisions/run.py --model gpt-5.6-luna
```

The runner writes `evaluation/method_decisions/results/pilot.jsonl` and `pilot.summary.json`. It uses the authenticated Codex CLI, which may require the machine's configured proxy. It does not use the LocalRetro candidate, reaction-model checkpoints, or external API keys.

For another paper-derived method candidate, `draft_tasks.py` can propose two
positive and two negative scenarios directly from its SKILL.md:

```bash
python3 evaluation/method_decisions/draft_tasks.py \
  --skill path/to/another/SKILL.md \
  --output evaluation/method_decisions/results/another-task-draft.json
```

This is a **drafting** stage. Review the source rule, scientific premises,
novelty, and gold answers before converting its proposals to `tasks.json` and
`oracle.json` and using `run.py --skill ... --tasks ... --oracle ...`.

The generated proposal for this candidate is in `results/auto_task_draft.json`.
We reviewed its cases, checked the canonical-SMILES equivalence and malformed
SMILES with RDKit, and wrote `reviewed_tasks.json` and `reviewed_oracle.json`
before a second paired run. Run that reviewed set with:

```bash
python3 evaluation/method_decisions/run.py \
  --tasks evaluation/method_decisions/reviewed_tasks.json \
  --oracle evaluation/method_decisions/reviewed_oracle.json \
  --output evaluation/method_decisions/results/reviewed.jsonl
```
