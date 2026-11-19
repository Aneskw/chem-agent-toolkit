# Outputs and retention

```text
skills/name/                            # approved pure package
skills/README.md                        # current packages and collection navigation
skills/catalog.json                     # adopted-name registry: name, path and tags
.pipeline/
  records/batch-id/
    input.json                         # sanitized configuration
    sources.json                       # origins, versions, file fingerprints
    sources/source-id/                 # retained supplemental evidence
    summary.json                       # batch decisions, usage and cleanup status
    complete.json                      # archive completion marker
    skills/name/
      basis.json                       # concise writing basis
      review.json                      # final review, important fixes and unresolved problems
      package.json                     # path/hash of adopted package
      package/                         # approved no-adopt/conflicting package only
      draft/                           # unfinished latest draft only
  runs/batch-id/                       # full temporary/recovery workspace
  outputs/batch-id/                    # staging output until safely archived
  retention/                          # registered lifecycle and pin flags
  leases/                             # OS-lock-backed active run detection
  cache/                              # shared originals; registered units only are pruned
```

Successful adopted skills have one formal package, not a second copy in records. --no-adopt or a
name conflict keeps the sole new approved package in records. No silent overwrite occurs.
Unfinished candidates keep the latest draft, existing basis and issues; full workspaces remain
available for 7 days after last activity. Archived drafts/records do not expire automatically.

Cleanup runs on build startup or prune. There is no background timer. Active batches and pinned
workspaces are skipped. unpin starts a fresh 7-day window. Registered cache units expire after
30 unused days, except those needed by pinned batches; cache cleanup defers while runs are active.
User originals and unregistered historical artifacts are never automatically removed. Historical
unmanaged paths are listed by retention for explicit later inspection/migration.

pin/unpin manage a registered batch; prune --dry-run previews expiration. --keep-debug preserves
successful full workspaces only for the normal retention window; pin makes preservation indefinite.
Archive writes must succeed before temporary copies are removed. Linked paths and Windows junctions
are refused. Cleanup warnings do not turn approved content into rejected content.

Latest drafts permit reuse, not guaranteed restoration of a discarded CLI session. resume requires
the retained checkpoint and unchanged specifications. Source locators preserve origins, versions,
paths and claims; a deleted cache may need reacquisition. No hidden reasoning is archived.
Supplemental source paths in archived sources.json point to retained content under that archive;
they remain readable after ordinary workspace and cache expiration. Initial user sources retain
their existing reference/snapshot policy.

## State location and public catalogs

The state tree defaults to ignored `.pipeline/`. To store it in an external working directory,
pass `--state-dir` on build/discover and subsequent resume, retention, pin/unpin or prune commands:

```text
python -m creation_pipeline build sources.json --state-dir ../chemical_skill/pipeline-state
python -m creation_pipeline retention --state-dir ../chemical_skill/pipeline-state
```

Choose the location before starting a batch. Retained records contain paths; moving an existing
state tree manually is not a supported migration procedure.

The root `skills/catalog.json` registers packages adopted by the pipeline, using only `name`,
`path` and `tags` in its `skills` entries. It is not a complete inventory of independently managed
collections. Their own catalogs and READMEs provide task categories, package locations and useful
source attribution. The root README links both collections and individual packages. Adoption
refreshes that navigation without putting build IDs, dated batches or review receipts in it.
Detailed review evidence remains in the state tree. After selecting suitable runs, maintainers may
manually publish source, discovery, basis, review and outcome records as curated
[workflow examples](../../examples/README.md). Routine builds do not populate or refresh examples.
Routine human audit reports and one-off maintenance materials belong in an external working directory.
