# Architecture

The pipeline discovers reusable capabilities from resources, then authors tool skills and justified shared adapters. Users may supply preferences and constraints without naming the exact task. The unit of discovery is a capability; the unit of execution is an entity in a dependency graph.

## Flow

1. Validate configuration; acquire and snapshot supported resources.
2. Index sources; mediate bounded model list/read/search and relevant acquisition requests.
3. Discover candidates, explain meaningful omissions and choose packaging directions in one analysis.
4. Save a source-locked plan. Users may inspect/select candidates before continuation.
5. Build shared tools before dependent skills; keep independent failures local.
6. Save model-authored file text verbatim; perform static and authorized execution checks.
7. Review complex adapters, compositions and extensions; repair within budgets.
8. Export the complete bundle with hashes and individual records; clean successful temporary work.

Discovery is shared across candidates. Each author receives the original guidance/constraints, its own plan, relevant source evidence and shared-tool contracts. It can read further sources. There is no fixed Markdown chapter renderer.

## Candidate selection and boundaries

The model identifies the upstream entrypoint and behavior, specific usage difficulty, why instructions/adaptation help, added behavior, required files, evidence and checks. It may omit/merge candidates or report no suitable capability. Limits are ceilings, not output quotas.

Behavior (`direct` or `extension`) is distinct from implementation (`upstream`, `adapter`, `composition`). Auto classification is the default. Multiple tools can support one coherent capability; one library can support several skills. Full research-project orchestration is not the primary output.

Existing callable interfaces are reused. A new tool requires a justified stable adapter; it is not a reimplementation of upstream algorithms. Missing algorithms, weights or method criteria remain gaps. No new environment configuration or MCP service is generated.

## Source access and snapshots

`acquisition.py` handles bounded HTTPS documents, public identifier resolution and selected text export from a pinned Git commit. Repository exports omit unsupported binary assets and are not installations. `documents.py` extracts textual content. `intake.py` indexes, snapshots, paginates and records actual read evidence.

Snapshots preserve eligible input bytes, independent of later changes to the user's original files. Resume verifies source hashes and specification versions. Source failures, skipped oversized files, capped indices and limited reads remain explicit. Metadata, an index or a successful download do not prove complete scientific understanding.

Models cannot directly execute shell/browser/MCP tools through the authoring backend. Additional acquisition is requested as structured actions. Search within a file is distinct from a generic web search engine, which is not currently implemented. Text extraction is distinct from multimodal interpretation.

## Plan continuation

`discover` saves the plan and source context. `build --plan` validates these and continues without rediscovery. Candidate selections can change; locked source/config fields cannot silently change. Discovery/content-standard changes require rediscovery. Author/reviewer prompt changes can reuse the source plan but rebuild the affected output under the updated instructions. Unchanged ready entity files may be reused from the referenced completed output. Draft/failed entities are regenerated. Interrupted model turns are not replayed.

Skill authors receive the actual generated shared-tool file contents, not only the initial plan, so their calls can follow the implemented interface. These files are not independent scientific or test oracles.

Shared dependencies form an acyclic graph. Required tools build first and only once. If unavailable or not ready, consumers are blocked while unrelated candidates proceed. Cross-run reuse only uses explicit source material or a saved output, not a global semantic registry.

## Validation and evidence

Static checks cover metadata, paths, links, syntax, minimum-content quotations and manifests. Author quotations locate information but do not establish semantic correctness.

Authors propose result-checking executions grounded in source examples or tests. Execution requires configured permission. Checks use argument arrays, bounded time/output and filtered environments; this is not an OS sandbox. Shared bundle and source hashes must remain unchanged. User-configured assertions are not weakened on repair. Failed generated assertions cannot silently disappear or change their expected result to obtain readiness; the record retains failures and unresolved coverage changes.

Complex generated code, compositions, extensions and use of external repository code receive targeted model review. Repository-dependent instructions must identify the usable acquisition address and version. Review distinguishes fixable file defects from missing evidence. Extensions need positive and negative execution cases. Scientific adequacy and Agent benefit remain outside engineering readiness.

## Modules

| Module | Responsibility |
| --- | --- |
| `models.py`, `schemas.py` | Configuration and structured model envelopes |
| `acquisition.py`, `documents.py`, `intake.py` | Resource access, extraction, snapshots and evidence |
| `analyze.py` | Candidate discovery, validation and dependency order |
| `model_backend.py`, `providers.py` | Mediated model sessions, Codex CLI and compatible APIs |
| `author.py`, `prompts/` | Direct file authorship and targeted review |
| `pipeline.py` | Budgets, continuation, entity orchestration and statuses |
| `checks.py`, `runtime.py` | Static checks, actual execution and assertions |
| `package.py`, `records.py` | Bundle integrity, explicit install and restricted cleanup |
| `cli.py` | Discover/build/check/install/clean commands |

## Records and retention

`summary.json` records batch outcomes, deferrals, reported model usage and read evidence. `plan.json` plus `sources.lock.json` support continuation. Per-entity records hold files, checks, notes and relevant plans. A bundle manifest maps skill/tool dependencies and hashes. Only the bundle is runtime content.

Successful workspaces are cleaned unless debug retention is enabled. Draft/failure work remains for diagnosis. Source caches support continuation and are not automatically evicted. There is no exact full-model replay guarantee, automatic adoption, publication or Agent evaluation.

See [usage](usage.md) for commands and limits, and [validation](acceptance.md) for actual evidence.
