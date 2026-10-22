# Tool Skill Creation Pipeline

Discover reusable capabilities from papers, documentation and code. The model selects scope and writes English skills; the program manages source snapshots, checks, feedback and adoption. A concrete task is optional.

## Prepare

Use Python 3.11+, Git and an authenticated Codex CLI on PATH (or a configured compatible API/Ollama service). JSON and text/code sources use the standard library. YAML and multiline skill frontmatter require PyYAML; text PDFs require pypdf:

```text
python -m pip install "PyYAML>=6.0,<7" "pypdf>=5,<7"
```

These are pipeline parsers, not dependencies of the tools being packaged. Tool dependencies remain external. No environment, MCP, web search or visual reading is provisioned.

## Run

Create `sources.json` (paths are relative to this file):

```json
{"sources": [{"id": "code", "path": "./my-tool"}], "batch": {"label": "molecular-analysis", "tags": ["molecular-analysis"]}}
```

```text
python -m creation_pipeline discover sources.json
python -m creation_pipeline build --plan .pipeline/outputs/<id>/plan.json --execute-generated-checks
```

Or use `build sources.json` directly. Generated code executes only with explicit permission, using the current user's privileges, not an OS sandbox. Ready skills are automatically adopted into `skills/<date>-<batch>/<name>/`. Use `--no-adopt` for output only. Drafts and failures remain under `.pipeline/outputs/`.

## Read more

- [Usage](docs/pipeline/usage.md): commands and feedback.
- [Configuration](docs/pipeline/configuration.md): supported fields and defaults.
- [Design](docs/pipeline/design.md): workflow and code organization.
- [Outputs](docs/pipeline/outputs.md): statuses, library and retention.
- [Status](docs/pipeline/status.md): verification and limits.
- [Minimum skill](docs/skills/minimum.md), [packaging](docs/skills/packaging.md), [examples](examples/README.md).

Engineering tests: `python -m unittest discover -s tests -v`. Agent benefit is evaluated separately.
