# Chem Agent Toolkit

A repository of chemistry agent resources and research-stage procedural skill candidates.

## Current status

The repository provides a unified directory layout and runnable database, tool,
and model packages. These packages are **atomic resources**, even when their
installation entry file is called `SKILL.md`. Passing a script or preflight
test does not establish that its instructions change an agent's choices. A
research-level chemical skill must encode decisions extracted from a paper and
its implementation, then show a useful effect in matched agent tasks.

## Atomic resource catalog

| Package | Category | Resource test status |
| --- | --- | --- |
| `localretro-single-step-retrosynthesis` | models-skills/open-models | verified for smoke examples |
| `retroprime-two-stage-retrosynthesis` | models-skills/open-models | verified for smoke examples |
| `wln-build-molecular-graph` | models-skills/open-models | verified preprocessing subskill |
| `retroxpert-evaluate-bond-disconnection` | models-skills/open-models | blocked_resources |
| `localtransform-forward-prediction` | models-skills/open-models | blocked_resources |
| `chem-openbabel-convert` | tools-skills/openbabel | interface and preflight |
| `chem-openmm-md` | tools-skills/openmm | preflight; dependency required |
| `chem-chembl-activity` | databases-skills/chembl | executable query; network required |
| `chem-uspto50k-split` | databases-skills/uspto50k | executable validator; data required |
| `chem-reinvent` | models-skills/open-models | preflight; upstream install required |
| `chem-genmol` | models-skills/open-models | preflight; checkpoint required |
| `chem-diffdock-nim` | models-skills/nim | preflight; endpoint and files required |
| `chem-reaction-atommap-audit` | tools-skills/rdkit | tested mapped-input structural check |
| `chem-retro-candidate-evaluation` | tools-skills/rdkit | tested exact-match and optional round-trip scorer |
| `localretro-template-library-preflight` | models-skills/open-models | tested resource and training-schema preflight |
| `retroprime-inference-preflight` | models-skills/open-models | tested script, weight and input preflight |

## Use

Copy or symlink a resource directory into an agent's installation directory
when a task needs it. The `verified` labels below refer only to documented
execution checks. No package in this table has yet demonstrated a causal
improvement in agent task quality or token use.

## Directory conventions

- `skills/`: flat legacy CLI/agent installation entries for resource packages;
  directory membership is not a research acceptance decision.
- `databases-skills/`: database and dataset skills for PubChem, ChEMBL, and USPTO-50K validation.
- `tools-skills/`: toolkit skills for RDKit, Open Babel, and OpenMM.
- `models-skills/`: model skills for the five reaction models, REINVENT, GenMol, and DiffDock NIM.
- `workflows/`: future composition-level workflows.
- `.claude-plugin/`: plugin marketplace metadata.

## Evidence and method

The [creation pipeline](creation_pipeline/README.md) normalizes the two supplied
literature exports, locks source versions, and extracts cited candidates using
the locally authenticated Codex CLI. The [targeted evaluation](evaluation/targeted/README.md)
separates raw-tool, tools-only, and complete-skill effects with held-out tasks.

Paper snapshots, repository evidence, run logs, and format notes are kept in the project archive. Each skill's `reference` section points to a pinned source. A verified status means only that the stated execution checks passed.

## Paper decision-rule case study

The [non-LocalRetro case study](evaluation/method_decisions/RUN_THIS.md) shows
the complete research workflow on paper `LJMZ9IL6`: locked PDF source →
source-cited method draft → positive/negative task proposals → human-reviewed
answers → paired no-skill/with-skill agent runs. Run the commands in that guide
to reproduce the case locally. The source PDF is downloaded and hash-checked;
the saved model response fixture is included for deterministic replay.

`creation_pipeline/run_pipeline.py --draft-eval-tasks` adds optional automatic
task **proposals** for each method candidate. Review their chemistry, novelty,
applicability and gold answers before scoring. The [case study results](evaluation/method_decisions/RESULTS.md)
show that the selected confidence/abstention candidate did **not** improve the
agent in this small pilot; successful extraction is not evidence of agent value.

## Candidate counts

Numbers such as 9/10 are counts of valid reactant candidates returned by one model inference, not counts of skills or successful experiments. A request for `top_k=10` can yield fewer valid candidates after invalid, duplicate, and placeholder outputs are removed.
