# Build examples

Each folder is one curated research-resource batch. These examples show the creation pipeline,
not a benchmark or proof that the underlying scientific tools were executed. Common instructions
live here; batch READMEs record only resource-specific facts, outcomes and limitations.

## Batches

| Batch | Resources and capabilities |
| --- | --- |
| [EDBO reaction optimization](edbo-reaction-optimization/README.md) | Original EDBO paper and fixed repository revision; see the batch for actual accepted Skills |

## Common layout

```text
examples/<batch>/
  README.md                       # unique sources, outcomes, limitations and any special steps
  input.json                      # reusable configuration, no machine-specific paths or credentials
  sources.json                    # source origins, resolved revisions and content identity
  discovery.json                  # discovered/omitted capabilities, scope, value and known gaps
  summary.json                    # actual batch outcome, calls and acceptance scope
  skills.json                     # links and file hashes of authoritative skills/ packages
  records/<skill-name>/
    basis.json                    # final writing claims and inspected source locations
    review.json                   # program checks, final independent review and important fixes
```

Skills themselves live only under [skills/](../skills/README.md). They are linked from each batch,
not copied here. Supporting references/scripts/assets, when generated, remain inside that same
pure Skill package. Build records are never needed by an Agent merely using the Skill.

## Read a complete extraction

1. Read input.json and sources.json to identify the inputs and exact source revision.
2. Read discovery.json to see which capabilities were considered, why they were selected and
   where scope starts/ends. Development limits can leave selected candidates unbuilt.
3. Follow the batch's Skill links to inspect the actual delivered instructions and support files.
4. Read basis.json to connect delivered content to source functions/pages; read review.json to
   see checks, review findings and substantive repairs. Locators are not proof that every claim is true.
5. Read summary.json for the final scope and limitations. Source/content approval does not mean
   target-tool execution, scientific validation or measured improvement to an Agent.

## Run the pipeline again

From the repository root, prepare Python 3.11+, authenticated Codex CLI and any optional document
parsers described in the [project README](../README.md). Target tool environments are not required.

```text
python -m creation_pipeline build examples/<batch>/input.json --preflight
python -m creation_pipeline build examples/<batch>/input.json --no-adopt
```

The first command checks configuration without model calls; the actual build also performs a real
connection handshake before fetching sources. --no-adopt avoids collisions with published examples:
approved regenerated packages stay under .pipeline/records/<new-build-id>/skills/<name>/package/.
Omit --no-adopt to adopt new non-conflicting names. Do not delete existing Skills to force a rerun.

Inputs record development limits used in the demonstration; production has no implicit candidate,
source-size or model-time quota. Match the recorded model only if it is available to your account;
otherwise the local configured default may differ. Another model run can choose different scopes,
names, files or text, even with the same resources. Remote acquisition may also become unavailable.
This reproduces the workflow to a degree, not byte-identical output or actual scientific results.

## Record curation

Retain decisions and their supporting evidence, not full conversations, caches, credentials, large
upstream trees or every intermediate draft. Public source locators use stable URL/revision/path and
page/function/section details instead of local .pipeline paths. Examples record file hashes so a
later change to an authoritative Skill can be identified; they are not an immutable second copy.

For current architecture, acceptance and cleanup behavior see [design](../docs/pipeline/design.md),
[acceptance](../docs/pipeline/acceptance.md) and [outputs](../docs/pipeline/outputs.md).
