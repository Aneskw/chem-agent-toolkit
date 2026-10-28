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
timeout is 90 seconds, distinct from optional development model time limits.

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

Old generated execution, verify-pending and promote options are not supported. See configuration.md
for accepted inputs and outputs.md for lifecycle details. A transport error is not a Skill defect;
a useful rejected draft may be repaired after resolving its concrete content or source gaps.
