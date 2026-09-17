# Chem Agent Toolkit

A reusable skill repository for chemistry research agents.

## Current status

The repository provides a unified directory layout, flat installation entry points, and executable or preflight-tested chemistry skills. A skill's runtime status and acceptance scope are documented in its own `SKILL.md` and reports.

## Skill catalog

| Skill | Category | Status |
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
| `chem-edbo-recommend-next-batch` | tools-skills | executable Bayesian optimization |

## Use

Copy or symlink the desired skill directory into an agent's skill directory, read its `SKILL.md`, and follow its procedure. Treat `verified` as a claim about the documented execution scope, not as a claim about chemical accuracy or experimental success.

## Directory conventions

- `skills/`: flat CLI/agent installation entry points pointing to generated skills.
- `databases-skills/`: database and dataset skills for PubChem, ChEMBL, and USPTO-50K validation.
- `tools-skills/`: toolkit skills for RDKit, Open Babel, OpenMM, and EDBO optimization.
- `models-skills/`: model skills for the five reaction models, REINVENT, GenMol, and DiffDock NIM.
- `workflows/`: future composition-level workflows.
- `.claude-plugin/`: plugin marketplace metadata.

## Evidence and method

Paper snapshots, repository evidence, run logs, and format notes are kept in the project archive. Each skill's `reference` section points to a pinned source. A verified status means only that the stated execution checks passed.

## Candidate counts

Numbers such as 9/10 are counts of valid reactant candidates returned by one model inference, not counts of skills or successful experiments. A request for `top_k=10` can yield fewer valid candidates after invalid, duplicate, and placeholder outputs are removed.
