# Usage

See [configuration](configuration.md) and [resources](resources.md). Use authenticated native Codex CLI, Python 3.11+ and Git. Only resources are required, not a task.

```text
python -m creation_pipeline build sources.json --preflight
python -m creation_pipeline readiness sources.json
python -m creation_pipeline build sources.json
```

Preflight validates fields/backend, not remote availability. Build automatically discovers, chooses, writes, independently reviews and runs applicable Docker planning/build/business acceptance before catalog qualification. --no-adopt retains output without library adoption. --keep-debug preserves successful workspaces. --draft-only produces candidates with no formal qualification. Unknown requirements and unavailable runtime resources cannot pass as reading-only content. Business checks are mapped to Docker; there is no host-execution opt-in flag.

Production defaults have no overall time/count/size quota. Development can opt into a preset and explicit overrides. It uses the same content standards. Per-network-operation and check timeouts remain configurable fault controls.

```text
python -m creation_pipeline resume <build-id> --keep-debug
```

Requires the local checkpoint, resource registry and session files. Sources/specifications and finalized delivery hashes are validated. Existing successful checks are reused only when applicable to the same files. Optional --rediscover re-enters discovery under current specifications. --extra-turns extends an existing finite budget explicitly; a null production budget needs no extension. Do not concurrently resume one run. Pre-v5 native checkpoints cannot safely inherit new stage rules: start a new build, reusing sources/cache.

```text
python -m creation_pipeline check .pipeline/outputs/<build-id>
python -m creation_pipeline install .pipeline/outputs/<build-id> --destination ./export
python -m creation_pipeline clean <build-id> --dry-run
```

check verifies recorded files/static structure, not fresh runtime execution. install checks eligible output and collisions. Clean only registered local workspaces; do not clean incomplete work intended for resume.

discover/plan/revise/--plan remain diagnostic interfaces. Hand-editing evidence is unsupported. Codex and explicit DeepSeek selection are supported; unsupported provider fields/Ollama fail early. See [batch operations](batch-operations.md), the [base-count example](../../examples/base-count/README.md) and [runtime recovery](runtime-recovery.md). Frozen runtime recovery does not require discovery checkpoints.
