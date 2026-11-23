# Readiness checks

Use the configured Python from the repository root:

```bash
python -m creation_pipeline build input.json --preflight
python -m creation_pipeline readiness input.json --mode build
```

| Entry | Checks | Model calls |
| --- | --- | --- |
| build --preflight | Fields, resource groups, path syntax and configuration rules | No |
| readiness --mode build | Known source conditions, CLI arguments, Linux Docker server and GHCR login | No |
| readiness --mode discover | Source and CLI prerequisites for discovery | No |
| readiness --offline | Configuration and local observations, with external prerequisites deferred | No |
| Actual build | Prerequisites plus real model calls, workspace/helper writes, shared cache writes and CLI session resume | Yes |

publish=false skips GHCR login checks. Authentication checks do not guarantee upload rights; the actual push must pass registry authorization. ready describes the prerequisites observed, not a qualified Skill or image.

Successful model permission checks can be reused for one hour. Configuration, check code, CLI or engine identity changes invalidate them, as does a model call failure.

## Common blockers

| Observation | Action |
| --- | --- |
| Missing or incompatible CLI | Install a compatible CLI and make it available on PATH |
| Model unavailable | Check authentication and model.name |
| Docker unreachable | Start the engine and select Linux containers |
| GHCR login failure | Authenticate with your classic token and confirm write:packages rights |
| Source unavailable | Correct the path/address or supply accessible material |
| Uploaded image cannot be downloaded anonymously | Make the target Package Public, then resume |

See [operations](batch-operations.md) for resume commands.
