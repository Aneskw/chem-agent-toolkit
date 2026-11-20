# Usage

Use authenticated Codex CLI and Python 3.11+. See README for optional parser installation.

```json
{"sources": [{"path": "./paper.pdf"}, {"path": "./code"}]}
```

```text
python -m creation_pipeline build sources.json
python -m creation_pipeline build sources.json --preflight
python -m creation_pipeline build sources.json --no-adopt --keep-debug
python -m creation_pipeline resume BUILD_ID --extra-turns 4
```

--preflight validates configuration only (no network/model calls). Every real build additionally
performs a lightweight selected-model handshake before acquiring research resources. Its connectivity
timeout is at most 90 seconds and respects a shorter configured turn or remaining build limit.

## Serial groups and discovery

Use resource_groups for independently processed collections; sources remains the single-group
shorthand. All group configurations validate before fetching. Resources are acquired when each
group starts, then its candidate draft is explicitly consolidated before authoring. Independent
groups share cached originals, not conversations or evidence namespaces.

```text
python -m creation_pipeline discover groups.json --state-dir D:/study/chemical_skill/.pipeline/v11
python -m creation_pipeline resume QUEUE_ID --state-dir D:/study/chemical_skill/.pipeline/v11 --no-adopt
```

discover retains finalized plans and temporary checkpoints for resume. resume accepts a queue or
single build ID. Completed groups are checked and reused; unresolved groups receive another attempt
from retained state. Missing group resources do not prevent later groups from running. Backend,
explicit global-budget and state-integrity failures stop dispatch; later groups remain unattempted.
Unchanged obstacles are not retried in a loop. Use a new queue for changed configuration or discovery
specifications; grouped --rediscover is unsupported. Missing/expired checkpoints cannot be restored
from package directories. pin QUEUE_ID protects its registered children and their caches.

## Windows state paths

Choose a short absolute `--state-dir` for new Windows builds, especially when the checkout or
trial-report directory is deeply nested. Keep reports wherever useful and store live state separately:

```text
python -m creation_pipeline build sources.json --state-dir D:/study/chemical_skill/.pipeline/run1
```

The full resource path includes this root, cache/snapshot directories, a 64-character content hash
and the upstream relative filename. A short filename alone does not ensure a short full path.
Some Windows APIs/tools retain the legacy 260-character limit. Enabling OS long-path support also
requires compatible applications; it is not a guarantee for Git, parsers and other child tools.
See [Microsoft's path-length documentation](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation).

Resource preparation stops with an actionable local-path error when an actual Windows I/O failure
indicates a possible path/name-length limit, rather than treating that source as remotely unavailable.
It does not reject a working long path merely because of its length. Correct the path and start a
new build; retained runs must use their original state directory. Do not move their folders manually.
`--preflight` checks configuration, not filesystem or third-party long-path compatibility.

## Builds and retained state

Normal builds need no manual plan edit/approval. User guidance is optional. Default approved output
is skills/name. --no-adopt retains approved packages in compact records; --keep-debug retains full
workspace temporarily. resume needs its checkpoint and unchanged specifications; use archived drafts
as new material when the original full workspace/session is unavailable.

```text
python -m creation_pipeline retention
python -m creation_pipeline pin BUILD_ID
python -m creation_pipeline unpin BUILD_ID
python -m creation_pipeline prune --dry-run
python -m creation_pipeline prune
python -m creation_pipeline check skills/NAME
```

check reports static properties only, not semantic approval or execution. pin protects a registered
batch and its resource cache. Unregistered historical files are listed, never auto-migrated/deleted.

See [configuration](configuration.md) for accepted inputs and [outputs](outputs.md) for lifecycle
details, including `--state-dir` for external state storage. A transport error is not a Skill defect;
a useful rejected draft may be repaired after resolving its concrete content or source gaps.
