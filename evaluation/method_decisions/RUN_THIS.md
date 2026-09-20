# Run this non-LocalRetro case yourself

Requirements: Python 3.10+, `pypdf` for PDF extraction (install with
`python3 -m pip install pypdf` if missing), and a locally signed-in `codex` CLI for task drafting and
agent comparisons. The saved-response extraction in step 1 itself makes no
model call. If you are using the project `.venv-eval`, replace `python3` in
the commands below with `.venv-eval/bin/python`.

In Terminal, first enter the repository:

```bash
cd /Users/xllin/Documents/Codex/2026-09-06/w/outputs/chem-agent-toolkit
```

The paper PDF is not committed. On a new clone, download and verify it once:

```bash
mkdir -p creation_pipeline/acquired/LJMZ9IL6
curl -L --fail --retry 2 \
  -o creation_pipeline/acquired/LJMZ9IL6/paper.pdf \
  https://arxiv.org/pdf/1711.04810.pdf
echo '6dfa50a0a880e1f699335c8d5b14500ad56904a852091bb9bea607d10f39e0f4  creation_pipeline/acquired/LJMZ9IL6/paper.pdf' | shasum -a 256 -c
```

1. Reproduce the paper-to-skill extraction without spending another model call. Change the run ID if you repeat it:

```bash
python3 creation_pipeline/run_pipeline.py \
  --config creation_pipeline/decision_pilot_manifest.json \
  --response-file evaluation/method_decisions/fixtures/LJMZ9IL6.response.json \
  --run-id my-decision-replay-01
```

Inspect `creation_pipeline/runs/my-decision-replay-01/pipeline_status.json` and `drafts-v03/predict-reaction-products-with-confidence-abstention/SKILL.md`. This is a **saved-response replay** of the previously generated model extraction, not a fresh independent model extraction. To ask the model to re-extract from the PDF, omit `--response-file`, add `--model gpt-6-astra`, and use a new run ID; the candidate set can change and the call consumes model usage.

2. Ask the model to propose positive and negative tasks for that new skill draft:

```bash
python3 evaluation/method_decisions/draft_tasks.py \
  --skill creation_pipeline/runs/my-decision-replay-01/drafts-v03/predict-reaction-products-with-confidence-abstention/SKILL.md \
  --output evaluation/method_decisions/results/my-task-draft.json
```

Review the proposed tasks against the paper and check their gold answers. The already reviewed task set for this case is `evaluation/method_decisions/reviewed_tasks.json` with its separate `reviewed_oracle.json`.

If you prefer the creation pipeline to propose task drafts in the same run,
add `--draft-eval-tasks --model gpt-5.6-luna` to step 1. It will make additional
model calls, one per method candidate, and write proposals under that run's
`evaluation_task_drafts/`. The review of applicability, novelty, and gold
answers remains a separate step.

3. Run the same agent with and without that skill on the reviewed set:

```bash
python3 evaluation/method_decisions/run.py \
  --skill creation_pipeline/runs/my-decision-replay-01/drafts-v03/predict-reaction-products-with-confidence-abstention/SKILL.md \
  --tasks evaluation/method_decisions/reviewed_tasks.json \
  --oracle evaluation/method_decisions/reviewed_oracle.json \
  --output evaluation/method_decisions/results/my-review-run.jsonl
```

Read `my-review-run.jsonl` for every answer and token count, then `my-review-run.summary.json` for paired scores. A successful run means the *workflow* executed; the skill has empirical value only if it improves the agent over the no-skill condition on a sufficiently broad held-out set.
