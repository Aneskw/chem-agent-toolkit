# Paper-to-skill creation pipeline

This pipeline starts from the two supplied literature exports, then turns
selected paper full texts and pinned repositories into **cited procedural
candidates**. It records atomic-resource hints separately. A model response
is never recorded as an execution pass or an agent-effect result.
The accepted format is [FORMAT-v0.3.md](FORMAT-v0.3.md).

## Inputs and source policy

`papers.jsonl` contains 52 normalized metadata records from the supplied
`Fwd Prediction.csv` and `Retrosynthesis.csv`. `papers.summary.json` records
input hashes. Local attachment paths, notes and abstracts from the exports are
excluded. `repo_map.json` selects five initial reaction-model repositories;
`source_locks/` stores the exact commits and hashes of selected source files.
Raw fetched sources and model runs live in ignored `cache/` and `runs/`.
The LocalRetro article full text is used locally under CC BY-NC-ND 4.0; the
RetroXpert arXiv PDF is also processed locally. Neither is redistributed here.

Run `python3 creation_pipeline/source_coverage.py` for a paper-by-paper audit.
At this snapshot, 2 of 52 table entries have both local paper full text and
pinned repository evidence (LocalRetro and RetroXpert), 3 have repository
evidence only, and 47 have metadata only. The latter groups are collection
work, not extracted paper skills.

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
By default, a run without paper full text stops as `paper_text_missing` before
the model call. `--allow-repo-only` is available for explicitly labeled
repository hints; these are not paper-derived skill candidates. PDF sources
require `pypdf`; use the project `.venv-eval/bin/python` or another Python
environment with that dependency.

## Abstraction and deduplication

After paper-backed runs, group their `method_procedure` candidates across
papers and compare them with the existing resource catalog:

```bash
.venv-eval/bin/python creation_pipeline/abstract_dedup.py \
  --source 2GFR874J=localretro-v03-replay \
  --source 74LHJIVM=retroxpert-paper-code-full \
  --run-id localretro-retroxpert-code-v2
```

The stage proposes a task-level capability, conditional decision rules, and a
deduplication action for every candidate. It also records overlap with existing
packages. Each candidate must appear in exactly one group. It renders v0.3
`procedural_skill_candidate` documents locally and writes a compact review
report in `results/`. Semantic merging is **never automatic**: the report's
`human_review_required` state must be resolved before publication or installation.
This stage does not run agent tasks or claim that a proposed skill is useful.
The selected LocalRetro/RetroXpert draft documents and overlap notes are
archived in `candidates/localretro-retroxpert-code-v2/` for review; they are
not linked from the flat installation directory.

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
RetroPrime's earlier model response was replayed after an external-URL validation fix
(`results/retroprime-v03-replay.json`) and produced two cited candidates: a
weight-blocked inference procedure overlapping the existing RetroPrime skill,
and an unexecuted two-stage training procedure. These are repository-derived
tool-usage drafts; RetroPrime paper full text has not been ingested.
LocalTransform's earlier live run in `results/localtransform-v03-live.json` produced
three citation-checked drafts. All three are blocked because the pinned
repository tree lacks the referenced preprocessing, training or decoding
scripts; no LocalTransform execution pass is claimed. Its paper full text has
not been ingested either.
RetroXpert's first paper-plus-code model response had two PDF whitespace/line
span citation discrepancies. `repair_citation_spans.py` accepted only quotes
that matched the nearby PDF text after whitespace normalization, recorded both
changes, and a saved-response replay produced two cited method drafts in
`results/retroxpert-paper-code-repaired.json`. This is a citation check, not a
chemical or execution validation.
The subsequent full-source run added six pinned implementation files alongside
the PDF and README. It produced two paper-and-code method drafts plus one
repository-only mapping utility hint in `results/retroxpert-paper-code-full.json`.
The final four-method abstraction report is
`results/localretro-retroxpert-code-v2-abstraction.json`.

Five separately implemented **atomic resource packages** currently use the v0.3 format: RDKit
compound filtering, RDKit atom-map audit, RDKit retrosynthesis candidate
evaluation, LocalRetro template-library preflight, and RetroPrime inference
preflight. Their tests establish only the documented deterministic or
file-checking scope. They have not established a change in agent decision
behavior or reaction-prediction accuracy.
