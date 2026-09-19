# Skill creation pipeline

This pipeline turns selected papers and pinned code repositories into **cited
drafts**, then supports a separate, human-reviewed step that builds and tests
executable skills. A model response is never recorded as an execution pass.
The accepted format is [FORMAT-v0.3.md](FORMAT-v0.3.md).

## Inputs and source policy

`papers.jsonl` contains 52 normalized metadata records from the supplied
`Fwd Prediction.csv` and `Retrosynthesis.csv`. `papers.summary.json` records
input hashes. Local attachment paths, notes and abstracts from the exports are
excluded. `repo_map.json` selects five initial reaction-model repositories;
`source_locks/` stores the exact commits and hashes of selected source files.
Raw fetched sources and model runs live in ignored `cache/` and `runs/`.
The LocalRetro article full text is used locally under CC BY-NC-ND 4.0 and is
not redistributed in this repository.

## One-paper run

From the repository root:

```bash
python3 creation_pipeline/collect.py --paper-id 2GFR874J
python3 creation_pipeline/run_pipeline.py --paper-id 2GFR874J --model gpt-6-astra
```

The first command requires internet access. The second uses the locally signed
in `codex` CLI, so it needs a model that the current Codex account can invoke;
it does not use `OPENAI_API_KEY`. For a deterministic replay without a model
call, supply `--response-file /path/to/saved-response.json --skip-collect` and
a new `--run-id`. Do not treat the replay as a fresh independent extraction.
The runner automatically prepares the source bundle, calls the model, checks
source quotes and line spans, renders v0.3 drafts, and validates their format.
`results/<run-id>.json` records stage, status and source/response hashes.

## Status and promotion

`source_collected` means source bytes were locked. `cited_draft` means the
response schema and cited text locations passed mechanical checks; it does not
mean the procedure is correct. `package_valid` adds a usable script/interface.
`execution_passed` requires an actual positive and negative test in the stated
environment. `heldout_passed` requires independent task evaluation.
`blocked_resources` records missing data, weights or endpoints. Only reviewed,
tested packages are linked from `skills/`.

LocalRetro's replay in `results/localretro-v03-replay.json` produced three
cited candidates. One is blocked by absent training data, one overlaps the
existing LocalRetro inference skill, and one needs a forward model for a
round-trip check. They are **not** counted as three working skills.
RetroPrime's model response was replayed after an external-URL validation fix
(`results/retroprime-v03-replay.json`) and produced two cited candidates: a
weight-blocked inference procedure overlapping the existing RetroPrime skill,
and an unexecuted two-stage training procedure. These are repository-derived
tool-usage drafts; RetroPrime paper full text has not been ingested.
LocalTransform's live run in `results/localtransform-v03-live.json` produced
three citation-checked drafts. All three are blocked because the pinned
repository tree lacks the referenced preprocessing, training or decoding
scripts; no LocalTransform execution pass is claimed. Its paper full text has
not been ingested either.

Five separately implemented packages currently use the v0.3 format: RDKit
compound filtering, RDKit atom-map audit, RDKit retrosynthesis candidate
evaluation, LocalRetro template-library preflight, and RetroPrime inference
preflight. Their tests establish
only the documented deterministic or file-checking scope; no new claim about
reaction-prediction accuracy follows from those tests.
