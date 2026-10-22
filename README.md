# Tool Skill Creation Pipeline

Discover reusable capabilities from papers, documentation and source code, then build English tool skills. A specific task is optional: the model reads the resources, selects capability boundaries and writes the final files. Existing tools are reused; shared adapters are generated only when justified.

## Quick start

Requirements: Python 3.11+, Git, and an authenticated Codex CLI or a configured compatible model API. Tool execution uses your existing environment.

Create `sources.json`:

```json
{
  "sources": [{"id": "tool", "path": "./my-tool"}],
  "prompt": "Prioritize reusable inference capabilities; exclude training."
}
```

`prompt` is optional. Paths resolve relative to the configuration file.

```text
python -m creation_pipeline build sources.json
```

To inspect the choices before building:

```text
python -m creation_pipeline discover sources.json
python -m creation_pipeline build --plan .pipeline/outputs/<id>/plan.json
```

Continuation uses the saved source snapshots and plan. It does not repeat discovery. Edit candidate selection in `plan.json` if needed; source context is locked separately.

## Outputs

A batch contains a reusable plan, a summary, individual records, and a bundle of `skills/` and any necessary shared `tools/`. Each entity has its own status: `ready`, `draft`, `blocked` or `failed`. Zero candidates is a valid result; candidate limits are ceilings, not quotas.

Generated checks need explicit execution permission (`--execute-generated-checks` or configuration). Without required execution evidence, packages stay drafts. Downloading a repository never automatically runs its code. No dependency installation, environment construction, MCP service or Agent benchmark is performed.

## Documentation

- [Usage](docs/pipeline/usage.md): inputs, models, execution, continuation and installation.
- [Architecture](docs/pipeline/design.md): discovery, shared tools, checking and records.
- [Minimum skill content](docs/skills/minimum.md) and [packaging guide](docs/skills/packaging.md).
- [Validation report](docs/pipeline/acceptance.md): tested behavior and evidence limits.

## Layout

- `creation_pipeline/`: implementation, prompts and model backends.
- `examples/`: source-only configurations and preparation helpers.
- `tests/pipeline/`: deterministic engineering tests.
- `skills/`: explicitly adopted skills.
- `evaluation/`: independent Agent evaluation work.
- `.pipeline/`: local source cache, workspaces and build outputs; excluded from Git.

Run engineering tests with `python -m unittest discover -s tests -v`.
