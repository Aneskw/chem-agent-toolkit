# Benchmark-derived chemistry skill candidates (2026-10-08)

Baseline on `main`: 28 tracked `SKILL.md` packages in `skills/`, `databases-skills/`, `models-skills/`, and `tools-skills/`. This batch adds 22 distinct decision-oriented packages in `skills/`, making 50 tracked packages. This is a file count, **not** a count of demonstrated agent improvements.

## Source selection

| Source | What was checked | Decision |
| --- | --- | --- |
| [AtomisticSkillsBenchmark](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/tree/db6116c1833f30cccb65ff78cda175510c3107b6/tasks) | 31 public Harbor tasks across chemistry, drug discovery, ML, and materials, with instructions and output tests | Used 22 tasks with separable, reusable decision points; each package cites its pinned task and test contract. |
| [ChemBench](https://github.com/lamalab-org/chembench) | Public chemistry question benchmark and evaluation harness | Kept for later held-out reasoning evaluation, not turned into task-answer skills. Writing skills from its question answers would contaminate that evaluation. |
| [Therapeutics Data Commons](https://github.com/mims-harvard/TDC) | Public therapeutic prediction datasets and benchmark tooling | Candidate for dataset/model evaluation; no TDC-specific package added without a dataset download and task-specific model contract. |
| [TSAgent](https://github.com/transition-state-search/TSAgent) | Transition-state workflow code with VASP and SLURM requirements | Useful implementation reference, but its public repo is not a standalone TSBench with benchmark grading cases; no claim of TSBench-derived improvement. |

## Scope and deduplication

The 22 packages cover 6 chemical-analysis decisions, 7 drug-discovery decisions, 2 MLIP-evaluation decisions, and 7 materials decisions. They deliberately do not duplicate the existing RDKit descriptor command, OpenMM execution wrapper, or reaction-stage audit: each new document describes a task-dependent branch, validity gate, reference-scale decision, or uncertainty stop condition.

Every package is a **procedural skill candidate** at low confidence. Its `Reference` section links to the specific pinned instruction and grader contract. The benchmark's fixed molecule, threshold, or output schema is not presented as a universal scientific rule. No benchmark solution files, model checkpoints, or datasets have been copied into these packages.

## Validation boundary

Passing the frontmatter/section validator and checking that source links exist establishes package shape and provenance only. It does not prove the chemistry, execute the referenced methods, or establish a skill effect. Before promoting any package as an effective skill, run matched held-out tasks with no skill, source text, and skill arms; keep the extraction tasks separate from the evaluation tasks and record correctness, scope failures, and token cost. Do not score a skill on the exact task whose instructions produced it.

Validation uses this repository's `creation_pipeline/validate_skill_format.py`. The bundled generic Codex skill validator currently rejects a top-level `compatibility` field, while this repository's user-specified v0.3 format requires it; that generic validator is therefore not the format authority for these packages.
