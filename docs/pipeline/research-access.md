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

Do not search unrelated papers/tools to increase output counts, add generic background, recursively chase citations or substitute a similar paper's method for the input study. A supplementary API fact does not establish that the original paper used that operation. Unavailable evidence remains a localized limitation.

These are Agent instructions plus review/registration checks, not an intercepting firewall for all native traffic or a domain whitelist. Access purpose/relevance requires semantic judgment. Reading does not authorize installing dependencies, deployments, external writes or executing source code. Execution uses a separate permission.

## Program and Agent responsibilities

The program downloads known routine sources, caches content, pins versions, prepares views and creates the registry. The Agent searches, browses, selects evidence and recovers from unsupported sites using available native tools. It need not ask the host for every page. Important adopted evidence is registered before being cited in candidate/review records.

Known-address helper:

```text
<helper> supplement --run RUN --url URL --reason "Specific uncertainty" --related-to INPUT_SOURCE_ID
```

The helper also accepts `--repo`/`--paper` and optional `--ref`. Existing callers that omit related-to anchor to the original inputs; supplying it explicitly is preferred.

Native-acquired file or saved verifiable excerpt:

```json
{
  "path": "<absolute path of a saved file inside this run>",
  "url": "https://official.example.org/versioned-api",
  "reason": "Confirm the documented return shape",
  "related_to": ["code"],
  "version": "recorded release or commit",
  "representation": "excerpt"
}
```

```text
<helper> register --run RUN --definition saved-resource.json
```

Registration requires saved nonempty content, an HTTPS URL, a reason and original-input IDs. It snapshots the file and records time/version/content identity and relationships. Existing eN locators stay stable. It rejects unavailable/out-of-workspace files and unknown or supplemental-only anchors. A valid URL/hash is not proof of relevance or source truth; review must check claims and passages. Prefer full original content when feasible; identify excerpt limitations explicitly.

Useful primary configuration references: [OpenAI web search documentation](https://learn.chatgpt.com/docs/web-search) and [Agent security documentation](https://learn.chatgpt.com/docs/agent-approvals-security). CLI native tool configuration is separate from the program acquisition helpers.
