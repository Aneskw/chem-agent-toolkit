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
By default, a run without primary full text stops as `primary_text_missing` before
the model call. `--allow-repo-only` is available for explicitly labeled
repository hints; these are not paper-derived skill candidates. PDF sources
require `pypdf`; use the project `.venv-eval/bin/python` or another Python
environment with that dependency.

If citation checking fails, the original model JSON remains in
`runs/<run-id>/responses/`. Inspect the mismatch rather than inventing a
quote. After correcting a mechanical issue, rerun with a fresh ID and
`--response-file runs/<old-run>/responses/<paper-id>.json --skip-collect` to
avoid another model call. A replay is not an independent extraction.

The intended multi-source entry point is `batch_pipeline.py`. Put many local
paper, database, tool, or model documents in one manifest; each job is
processed independently and each successful result is published under
`skills/generated/<run-id>/`:

```bash
.venv-eval/bin/python creation_pipeline/batch_pipeline.py \
  --manifest /path/to/batch-manifest.json \
  --model gpt-6-astra \
  --rounds 1 \
  --push
```

Use `--rounds 2` or more to make independent extraction passes per source.
Different passes can produce different candidates, so the batch report keeps
every run separate. This stage deliberately does not deduplicate, execute, or
claim agent usefulness. See [examples/batch-manifest.example.json](examples/batch-manifest.example.json).

For the two supplied CSV catalogs, use `mine_available.py` so article IDs do
not need to be selected manually. It reads `papers.jsonl` and the pinned
source locks, selects every entry currently in `paper_and_repository` state,
and skips repository-only and metadata-only records:

```bash
.venv-eval/bin/python creation_pipeline/mine_available.py \
  --model gpt-6-astra \
  --rounds 1 \
  --push
```

Use `--dry-run` first to print the counts and selected IDs. At the current
snapshot this selects 2 of 52 records; 3 are repository-only and 47 have only
metadata. It will expand automatically as full texts and pinned repositories
are added to the catalog.

## Other papers and database/tool/model documentation

The catalog collector above is specific to the supplied CSVs and five
reviewed repository mappings. The extraction core also accepts a local JSON
source manifest without a catalog ID or repository. Copy
`examples/database-source.example.json` to a working directory, replace its
placeholder path, URL and SHA-256, and place the downloaded document at the
path relative to the manifest. Run:

```bash
.venv-eval/bin/python creation_pipeline/run_pipeline.py \
  --config /path/to/source-manifest.json \
  --run-id my-source-01
```

The legacy field `paper_id` is a safe **job identifier** in this manifest;
it does not imply a paper. `source_type` may be `paper`, `database`, `tool`, or
`model`. Give the primary document respectively the role `paper`,
`database_doc`, `tool_doc`, or `model_doc`. Additional implementation files
can use `repo_code`/`repo_doc` when `repo_root` and preferably a pinned
`repo_manifest` are supplied. The core reads local PDF, JATS XML, HTML,
Markdown, text, code and notebook files. It checks quoted line spans against
the actual extracted text and enforces a declared SHA-256. A missing primary
document stops the run unless `--allow-repo-only` explicitly requests
secondary hints. The document's `url` records provenance; it does **not**
fetch that URL. Automated discovery, licensing review and downloading for
arbitrary sites are not implemented. Database documentation can support
conditional procedures, but a single API invocation remains a `tool_usage`
hint rather than a procedural skill. Every candidate needs semantic review.
The extractor scans the selected source text, not a hard-coded paragraph or
line number. It currently makes one model pass with a context budget and at
most four candidates per job. Check `omitted_source_sections` and
`source_text_complete` in the result; a long or poorly selected source is
**not** an exhaustive mining run. Automatic section-by-section traversal and
cross-chunk consolidation remain future work.

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
# Public-catalog acquisition and batch extraction

`acquire_catalog_sources.py` scans every row in `papers.jsonl`, follows public
open-access locations (arXiv, PMLR, publisher OA pages, OpenAlex and
Unpaywall), and writes a local `acquisition_report.json` plus an
`acquired_manifest.json`. A row is marked `source_missing` when no public
full-text file can be downloaded; the pipeline never invents article content.

Raw downloads live under `creation_pipeline/acquired/` and are ignored by git.
The report and manifest are committed so the run is reproducible without
putting article PDFs in the repository.

After acquisition, run up to 20 source jobs with:

```bash
.venv-eval/bin/python creation_pipeline/batch_pipeline.py \
  --manifest creation_pipeline/acquired_manifest.json \
  --model gpt-6-astra --max-jobs 20 \
  --prefix public20-$(date +%Y%m%d-%H%M%S) --push
```

`--max-jobs 20` means twenty papers are attempted; the resulting batch report
records the actual candidate count. It may be smaller than 20 because a paper
can yield zero candidates or because the model service fails. Each generated
candidate is source-validated and citation-checked; execution and agent-effect
validation remain separate stages.

## General paper and database ingestion

The entry point is no longer restricted to the 52-paper catalog or named
repositories. Supply a document, directory, public URL, or mixed JSON catalog:

```bash
# All supported documents in a local paper directory
.venv-eval/bin/python creation_pipeline/run_public_pipeline.py \
  --input /absolute/path/to/papers --source-type paper \
  --target-candidates 20 --model gpt-6-astra --push

# Database documentation URL (not a raw database connection)
.venv-eval/bin/python creation_pipeline/run_public_pipeline.py \
  --input https://example.org/database/api-documentation \
  --source-type database --target-candidates 2 --model gpt-6-astra

# Heterogeneous sources and multiple supporting documents per resource
.venv-eval/bin/python creation_pipeline/run_public_pipeline.py \
  --catalog /absolute/path/to/sources.json --target-candidates 20 --push
```

Example `sources.json` (paths resolve relative to this file):

```json
{
  "items": [
    {"id": "paper-a", "source_type": "paper", "title": "A new paper",
     "sources": [{"path": "paper.pdf"}, {"path": "supplement.md"}]},
    {"id": "database-b", "source_type": "database", "title": "A new database",
     "sources": [{"url": "https://example.org/api-docs"},
                 {"path": "schema.sqlite"},
                 {"path": "data-dictionary.md"}]}
  ]
}
```

To acquire and inspect sources without calling a model:

```bash
.venv-eval/bin/python creation_pipeline/ingest_sources.py \
  --catalog /absolute/path/to/sources.json \
  --out creation_pipeline/intakes/my-sources
```

Supported inputs: text PDFs, JATS XML, HTML, Markdown, plain text, DOCX,
notebooks, JSON/JSONL, YAML/OpenAPI, SQL, CSV/TSV and local SQLite schemas.
SQLite access is read-only and exports schema only, not table records.
CSV/TSV rows default to metadata: provide documentation to support a procedure.
Remote input follows explicit PDF links on paper landing pages; a detected
abstract/access-challenge page is rejected. HTML screening is heuristic and
still needs source review. This is not an unrestricted website crawler.

Long documents are normalized into bounded segments with original file hashes,
pages, URLs and a segment inventory in `ingestion_report.json`. Every primary
text segment is queued rather than silently skipped due to context length.
Segments are extracted independently; cross-segment synthesis is not claimed.
Failures remain recorded per input while other inputs continue.

The pipeline does not promise useful skills from every paper or database.
Scanned PDFs require OCR; authenticated/private databases require the user to
export authorized documentation/schema; a method absent from the supplied
material produces no supported skill. Source citations and package format are
checked; execution and agent-utility experiments are separate.

On macOS the model subprocess now inherits explicit proxy environment variables,
or uses the enabled system HTTPS proxy when none is set. This fixes the observed
case where the app connected but CLI sampling timed out. It never changes the
system's proxy configuration.
