# Outputs and library

```text
.pipeline/runs/<id>/
  resources.json / resource-state.json   # locator index and complete restorable source registry
  checkpoint.json / agent-state.json    # host checkpoint and native session/receipts
  candidates/                           # optional incremental discovery records
  deliveries/                           # completed metadata/hash receipts
  agent-turns/                          # stage inputs/results/events and diagnostics
  agent-checks.jsonl                    # tool-executed review diagnostics, when used
  bundle/skills/<name>/                 # actual authored files
.pipeline/outputs/<id>/
  summary.json / plan.json / sources.lock.json
  attempt-history/                     # summaries retained on resume
  records/<name>.json
  bundle/skills/<name>/
skills/<date>-<batch>/<name>/
```

Keep a few conclusions: ready = applicable source/content and engineering review passed without known blocking defects; draft/blocked = essential evidence or resource gap; failed = unresolved known error; incomplete/interrupted = work did not finish. Ready does not assert every tool ran. Records state checked behavior and unverified scope; no complex confidence matrix is introduced.

Program or review-identified missing execution conditions are not silently counted as passing tests. Generated checks are opt-in. An unexecuted branch or absent local environment can coexist with sound reviewed content; actual wrong interfaces/results remain blockers.

Library adoption is individual: adopted/already_present/conflict/not_eligible/disabled. Same name/content is idempotent; changed content never overwrites automatically. No semantic merging or elaborate classification. Catalog contains capability summary, source versions, batch, paths, hashes, checks, notes and unverified items. Build ledgers do not enter normal runtime skill context.

Keep configuration, source provenance, selection reasons, final files/review/checks and necessary diagnostics. Successful temporary views/events can be cleaned while outputs and cache remain; failures retain local recovery material. No original user file is deleted, including reference storage. Logs can contain source content; private reasoning and base64 image payloads are not archived in normal records. Image audit is best-effort and cumulative by native session.

Catalog operations use a lock and ordinary rollback. A process crash may leave a stale lock; only remove it after confirming no operation is running. Storage is not claimed crash-proof. New trial cases stay local until deliberately selected as examples.
