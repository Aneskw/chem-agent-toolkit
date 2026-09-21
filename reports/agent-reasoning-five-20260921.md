# Five paper-derived AI-model skill candidates

## Scope

The creation pipeline processed six papers selected from the two literature spreadsheets:

1. Retroformer (`H9EHIF3J`)
2. GTA (`DMXL3WVG`)
3. Retro* (`KNGUQJ73`)
4. Experience-guided MCTS (`Z3W4BK3K`)
5. UAlign (`C5HMZZWJ`)
6. RetroDFM-R (`K7ZGXDS6`)

The model extraction stage returned 14 `method_procedure` candidates. All five candidates below passed primary-source coverage, schema, citation-span, and `SKILL.md` format checks. PDF line-wrap repairs were limited to exact text found in the supplied paper pages.

## Selected skills

| Skill | Source | Decision layer | Why it can change an agent's reasoning path |
| --- | --- | --- | --- |
| `reaction-center-guided-retrosynthesis` | Retroformer | Reaction-site selection | Chooses between thresholding and connected-center search, prunes overlapping centers, and conditions precursor generation on retained sites. |
| `retro-star-retrosynthetic-planning` | Retro* | Route search | Selects the next frontier molecule by estimated complete-route cost and supplies separate first-solution and optimality stopping rules. |
| `experience-guided-retrosynthetic-search` | EG-MCTS | Route search | Propagates success and failure through an AND-OR tree and uses learned decomposition experience during budgeted search. |
| `generate-and-filter-chemical-reasoning-examples` | RetroDFM-R | Reasoning quality control | Uses Analyzer, Summarizer, and Assessor roles and retains rationales only above a chemical-correctness threshold. |
| `augment-and-rank-retrosynthesis-predictions` | RetroDFM-R | Candidate diversification and ranking | Samples product representations and reasoning trajectories, removes invalid predictions, merges duplicates, and ranks by frequency. |

## Abstraction and deduplication

The five packages are kept separate because they operate at different decision layers. Retro* and EG-MCTS both use AND-OR trees, but Retro* is cost-guided best-first search while EG-MCTS uses PUCT-style selection and experience-based value updates. They are related variants rather than duplicates.

The automatic abstraction run `agent-reasoning-dedup-20260921` timed out after 900 seconds and produced no report. The repository therefore records `source_validated_human_curated`, not automatic semantic deduplication. Excluded candidates were mainly data cleaning, SMILES token alignment, training-only configuration, benchmark construction, and human-only evaluation procedures.

## Validation state

| Check | Result |
| --- | --- |
| Complete primary-paper text supplied | Passed for all five |
| Citation text and line span | Passed for all five |
| Required `SKILL.md` sections and front matter | Passed for all five |
| Packaged executable fixture | Not applicable; these are procedural text skills |
| Agent effect evaluation | Not run |

These are strong candidates for a later no-skill/with-skill agent experiment. They are not yet evidence that task quality, token use, or success rate improves.

## Locations

- Audit set: `skills/generated/agent-reasoning-five-20260921/`
- AI-model category: `models-skills/open-models/<skill-name>/`
- Selection and dedup record: `creation_pipeline/selections/agent-reasoning-five-20260921.json`
