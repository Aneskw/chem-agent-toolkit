# Scoped supplemental research

Initial user resources anchor the build. Supplemental research resolves a concrete uncertainty in those resources; it does not autonomously choose new research topics or add unrelated skill candidates.

| Setting | Behavior |
| --- | --- |
| network=true, research_access=supplement | Request native live web search and allow purpose-scoped browsing/downloads |
| network=true, research_access=known_only | Disable native search; allow targeted known-resource acquisition |
| network=false | Disable native search and shell resource networking; retained local sources remain readable |

New configurations default to `supplement`. Historical saved runs missing this setting default to `known_only`, avoiding silent permission expansion. The model inference connection is separate from resource networking. Actual native search availability depends on the installed CLI, model/provider and account. Requested configuration is not evidence that a search ran; receipts separately record search mode and CLI-reported search events.

## Scope and evidence

Before searching, identify the missing fact, its input-source/candidate anchor and what evidence would resolve it. Allowed directions are the original paper and supplements, official project code/docs/examples/tests/version notes, directly necessary dependencies and upstream discussions of a specific problem. Prefer primary sources at the relevant version. Read actual pages/files; search summaries only locate material.

For a promising software capability lacking necessary input/invocation/parameter/output evidence,
actively supplement before omission merely because the main paper is incomplete. Inspect relevant
software, computational methods and SI/code-availability passages. Already sufficient sources need
no search; a paper with no eligible software workflow may yield no candidates. Record concrete
attempts and unresolved obstacles in existing omitted/gaps/limitations, not an exhaustive inventory.

Do not search unrelated papers/tools to increase output counts, add generic background, recursively chase citations or substitute a similar paper's method for the input study. A supplementary API fact does not establish that the original paper used that operation. Unavailable evidence remains a localized limitation.

These are Agent instructions plus review/registration checks, not an intercepting firewall for all native traffic or a domain whitelist. Access purpose/relevance requires semantic judgment. Reading does not authorize installing dependencies, deployments, external writes or executing source code. Execution uses a separate permission.

A failed URL or page viewer does not establish that the needed evidence is unavailable. For PDF or
binary viewer failures, use ordinary downloading and available local text/render tools. Follow
promising official, author- or institution-hosted copies of the original material, verifying their
provenance and applicability to the chosen version. Fix malformed requests or source handoff rather
than repeating unrelated searches. Stop when sufficient evidence is obtained or relevant viable
alternatives leave the essential fact unresolved; no fixed search count or exhaustive survey is required.

## Version selection

For reusable tasks, assess official current stable releases, support and target-environment
compatibility before choosing an interface. Prefer a maintained obtainable release; paper age,
an old citation and an accessible legacy manual do not by themselves justify obsolete packaging.
Explicit reproduction, existing artifacts/formats/platforms or scientific-method dependencies can
justify historical versions. A release's age alone is not evidence of abandonment.

Keep the scientific method grounded in the input while verifying target-version interfaces,
defaults, units and result semantics. Do not assume numerical equivalence or substitute a different
method. If current documentation is unavailable, retain an honest gap rather than fabricate an
upgrade or present legacy as the current general workflow. Offline/known-only modes retain their
access restrictions; version support may remain unverified, never guessed.

Discovery records the target and short selection reason in construction/evidence; authors verify
the choice and record provenance in basis/notes; reviewers check task suitability as well as
correctness within the chosen release. No new schema or independent version-planning stage is
introduced. The final Skill carries the chosen version and relevant constraints, not the survey.

## Program and Agent responsibilities

The program downloads known routine sources, caches content, pins versions, prepares views and creates the registry. The Agent searches, browses and selects evidence using native tools directly or the helper; a failed helper attempt is not required first. It need not ask the host for every page. Important adopted evidence is registered before being cited in candidate/review records.

Known-address helper:

```text
<helper> supplement --run RUN --url URL --reason "Specific uncertainty" --related-to INPUT_SOURCE_ID
```

The helper also accepts `--repo`/`--paper` and optional `--ref`. A single original input is the default anchor; multiple inputs require explicit related-to IDs. Cached reuse merges input relationships and purposes.

Empty remote responses are rejected before successful caching/registration; legacy empty download
cache entries are fetched again. This does not exclude legitimate empty files inside repositories.
Expected acquisition failures return `unavailable` with an `error_kind` (`transport`, `content`,
`constraint`, or acquisition subprocess failure `acquisition`) and the original error. Invalid
requests, local filesystem failures and unexpected implementation errors propagate to the helper's
nonzero `error` response instead of being reported as inaccessible remote resources. These categories
locate the failure; a TLS error alone does not identify whether the cause is the server, proxy or host.

Native-acquired file or saved verifiable excerpt:

```json
{
  "path": "research/inbox/official-api.txt",
  "url": "https://official.example.org/versioned-api",
  "reason": "Confirm the documented return shape",
  "related_to": ["code"],
  "version": "recorded release or commit",
  "representation": "excerpt"
}
```

For automatic handoff, save the actual content first in the supplied `research_inbox`, then write
this JSON as `research/inbox/official-api.source.json` by atomic rename from a temporary file.
Paths resolve relative to the run, not the shell cwd. Complete `*.source.json` files are commit
markers; unfinished temporary files are ignored. No separate register command is necessary.
`inventory` refreshes registration immediately. Candidate saving, author `finish`, and turn
boundaries ingest before reference validation. Invalid committed items return actionable errors
for repair; repeated unchanged turn-boundary errors stop rather than loop indefinitely.

The explicit legacy command remains available:

```text
<helper> register --run RUN --definition saved-resource.json
```

Registration requires saved nonempty content, an HTTPS URL, a reason and original-input IDs. It snapshots the file and records time/version/content identity and relationships. Existing eN locators stay stable. It rejects unavailable/out-of-workspace files and unknown or supplemental-only anchors. A valid URL/hash is not proof of relevance or source truth; review must check claims and passages. Prefer full original content when feasible; identify excerpt limitations explicitly.

Do not label an Agent summary as original text. For excerpts save the returned passage with its
title/section and scope, distinct from the author's writing basis. After registration, authors can
reference the saved absolute or run-relative file path, a source-id/path, a unique registered URL,
or an eN returned by inventory; never predict eN IDs. A path alias identifies only registered
content; an unregistered file or ambiguous URL is still rejected.
Source/content review independently reads registered evidence and can supplement missing context.
Adopted supplemental sources are copied to the build archive so they survive workspace/cache expiry.

Useful primary configuration references: [OpenAI web search documentation](https://learn.chatgpt.com/docs/web-search) and [Agent security documentation](https://learn.chatgpt.com/docs/agent-approvals-security). CLI native tool configuration is separate from the program acquisition helpers.
