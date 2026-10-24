# Usage

See [configuration](configuration.md) and [resources](resources.md). Use authenticated native Codex CLI, Python 3.11+ and Git. Only resources are required, not a task.

```text
python -m creation_pipeline build sources.json --preflight
python -m creation_pipeline build sources.json --execute-generated-checks
```

Preflight validates fields/backend, not remote availability. Build automatically discovers, chooses, writes, reviews and organizes individual skills. --no-adopt is appropriate for trials. --keep-debug preserves successful workspaces. Without generated execution permission, content review still proceeds and unverified runtime is explicitly recorded; do not confuse this with actual tool execution.

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

Compatibility discover/plan/revise/--plan remain diagnostic interfaces, not the normal human workflow. Hand-editing evidence is unsupported. Direct API/Ollama configuration fails early. Existing examples are preserved historical cases and may contain an earlier plan-based invocation; they are not new complex-resource validation.
