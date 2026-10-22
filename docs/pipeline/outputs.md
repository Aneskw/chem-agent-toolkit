# Outputs and library

```text
.pipeline/outputs/<id>/
  summary.json
  plan.json
  sources.lock.json
  revision.json                  # only on human revision
  records/<name>.json
  bundle/skills/<name>/SKILL.md
skills/
  catalog.json
  README.md
  <date>-<batch>/<name>/SKILL.md
```

ready: applicable checks and review passed; draft: required evidence is missing; blocked: essential resources are absent; failed: generation/checks did not succeed. Batches may be partial, planned or no_candidates. Read per-skill reasons, not only counts.

Adoption is separate: adopted/already_present/conflict/not_eligible/disabled. A ready package can have a library conflict. Each ready skill can be adopted even when another fails. Names are semantic lowercase hyphen IDs matching frontmatter. Same name/content is idempotent; changed content conflicts without overwrite. Similar names are not semantic deduplication.

The catalog contains tags, source versions, hashes, scoped checks and build identity. Git attributes preserve validated skill bytes across checkouts so newline conversion does not invalidate their hashes. The catalog does not prove usefulness. Batch folders aid browsing; point your Agent to actual skill paths using its own discovery rules. No universal recursive discovery is assumed.

Catalog updates use an exclusive lock and roll back ordinary copy/index failures. After a process crash, a stale `skills/.catalog.lock` may require manual removal, only after confirming no build is adopting skills. This is not crash-proof storage.

Successful temporary runs are cleaned unless keep-debug is enabled. Draft/failure diagnostics remain. Outputs and shared cache are retained; cleanup never deletes original inputs or adopted skills. Detailed runtime evidence remains local. Minimal catalog receipts travel with adopted content.
