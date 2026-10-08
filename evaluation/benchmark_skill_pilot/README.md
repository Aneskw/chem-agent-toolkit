# Benchmark-derived skill A/B pilot

This is a development pilot for four of the 22 skills added in commit `f3d079f`: `committee-force-disagreement`, `symmetry-aware-redocking-control`, `quasi-harmonic-volume-scan`, and `microstate-aware-virtual-screening`. Eight synthetic decisions were written after seeing the skills, so they are **not** independent held-out evidence. None reproduces the source benchmark's fixed case.

Each task has a frozen answer in `oracle.json`. `run.py` loads the skill text from commit `f3d079f`, randomizes paired no-skill/with-skill calls, runs each in an isolated temporary directory without tools, and records answers, errors, elapsed time, and usage. Invalid or timed-out calls do not count as incorrect chemistry answers.

From the repository root, first check the plan:

```bash
python3 evaluation/benchmark_skill_pilot/run.py --dry-run --out /private/tmp/chem-benchmark-ab-plan-01
```

Then run all 16 calls when the Codex CLI model endpoint is reachable:

```bash
python3 evaluation/benchmark_skill_pilot/run.py --model gpt-5.6-luna --out /private/tmp/chem-benchmark-ab-run-01
```

The output directory must be new so an earlier result is never overwritten. An A/B conclusion requires valid paired answers. This pilot cannot establish efficacy for all 22 skills; a later independent evaluation should use unseen tasks, human-reviewed answers, and more than two tasks per skill.

On 2026-10-08 the CLI launched, but the first no-skill and with-skill calls both timed out after 30 seconds. The result was 0/2 valid model responses, **not** a 0/2 chemistry score. The full run was not started because the model endpoint was unavailable.
