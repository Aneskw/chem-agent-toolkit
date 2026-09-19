# Targeted evaluation of existing chemistry skills

The current pilot contains three executable tasks: standard RDKit molecular
weight (distinguishing average from exact mass), PAINS/Brenk plus novelty
filtering, and refusal to invent a missing USPTO-50K split. The filtering task
is adapted from the public instruction of ScienceAgentBench verified instance
16; its local data are held out from the skill package. The former EDBO task
was removed after the upstream repository deleted that skill package.

## Three conditions

| Condition | Available material | What the comparison estimates |
|---|---|---|
| `no-skill` | Installed libraries and task fixtures | Baseline task solving |
| `tools-only` | Same plus packaged scripts/resources | Benefit of executable packaging |
| `with-skill` | Same plus full SKILL.md, references, examples | Incremental procedural guidance |

Run all conditions with the same model, permissions, input fixture, timeout and
repetition count. Attempts are randomized and isolated in separate `/tmp`
workspaces. The scorer and held-out answers are outside those workspaces.

```bash
.venv-eval/bin/python -m pytest evaluation/targeted/test_score.py -q
python3 evaluation/targeted/run.py --dry-run --repeats 3
python3 evaluation/targeted/run.py --model gpt-6-astra --repeats 3 \
  --output evaluation/targeted/results/run-001
```

The active agent must use its own authenticated Codex CLI. The runner invokes
`codex exec` with a writable sandbox limited to each attempt's workspace;
source data and skills are copied into it. Do not put API keys in tasks or logs.

## Outcome measures

Primary: exact task success and no fabricated scientific result. Secondary:
input/output/cached tokens from `turn.completed`, tool-call count, failed
commands, elapsed time, and output contract. Compare paired outcomes per task.
Token savings count only if quality is maintained or improved; report the
additional skill-context tokens rather than hiding them. Traces describe the
agent's observable procedure, not private chain of thought. Predeclare the
scorer and fixtures before examining agent outputs.

Three repeats are a harness pilot. For a paper claim, use additional held-out
instances per skill, at least ten paired repeats or independent instances per
skill, multiple model strengths, and uncertainty intervals. Do not pool
incompatible skill types into one success rate. Tasks with unavailable weights,
endpoints or datasets should be evaluated as resource-triage tasks, never as
model accuracy tasks.

## Coverage plan for the existing catalog

| Skill group | Targeted decision that the task should expose | Status |
|---|---|---|
| RDKit descriptors | Average MW vs exact mass; invalid SMILES | Executable pilot |
| RDKit compound filter | PAINS + Brenk + strict Tanimoto threshold | Executable pilot |
| USPTO-50K split | Missing dataset must not be manufactured | Executable pilot |
| PubChem, ChEMBL | Identifier/units/provenance; use recorded API fixtures to avoid network drift | Fixture adapter needed |
| Open Babel, OpenMM | Conversion validity or energy-minimization evidence | Environment snapshot needed |
| LocalRetro, RetroPrime, LocalTransform, RetroXpert, WLN | Checkpoints, pinned datasets and upstream code; positive inference plus resource triage | Pinned resources needed |
| REINVENT, GenMol, DiffDock NIM | Valid model output versus honest refusal when weights/endpoint absent | Weights/endpoint needed |

The pilot is deliberately focused on points where a skill might change the
action sequence. A trivial task that the baseline already solves perfectly
cannot establish a skill benefit. A useful skill can also increase tokens; that
result should be reported rather than tuned away after seeing the data.
