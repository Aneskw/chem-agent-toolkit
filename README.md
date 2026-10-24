# Research Skill Creation Pipeline

Use a native Codex Agent to discover reusable capabilities from papers, documentation and code, then write and review English skill packages. A task description is optional. The program prepares sources, provides processing helpers, checks delivered files, records evidence and organizes reviewed skills.

## Prepare

Python 3.11+, Git and authenticated Codex CLI on PATH. Direct model API/Ollama backends are temporarily closed. Install optional parsers only if needed:

```text
python -m pip install "PyYAML>=6,<7" "pypdf>=5,<7"
```

Poppler (`pdftotext`, `pdftoppm`) improves PDF text/page processing. Tool dependencies remain external; no server, Docker or automatic environment installation is provided.

## Build

Save sources.json (paths relative to this file):

```json
{
  "sources": [
    {"path": "./paper.pdf"},
    {"repo": "https://github.com/organization/project.git", "ref": "<commit>"}
  ],
  "batch": {"label": "research-methods", "tags": []}
}
```

```text
python -m creation_pipeline build sources.json --preflight
python -m creation_pipeline build sources.json --execute-generated-checks
```

Production defaults impose no model time/turn, candidate/build-count or source-size quota. Agent reads selectively; retained resources are not all injected into context. Development presets and explicit limits are available. No manual plan approval is required.

Generated execution is opt-in. Without it, source/content review can still complete, but runtime remains unverified and is recorded. A ready skill means applicable review passed without known blocking defects, not every tool was executed or scientific validity was established. Host checks use current user privileges; native commands use the Codex workspace sandbox and receive the execution policy as instructions.

Reviewed skills are organized under `skills/<date>-<batch>/<name>/`. Use --no-adopt for trials and --keep-debug to retain successful workspaces. Failures retain local recovery data.

## Documentation

- [Usage](docs/pipeline/usage.md), [configuration](docs/pipeline/configuration.md)
- [Resources and supplements](docs/pipeline/resources.md)
- [Design](docs/pipeline/design.md), [outputs](docs/pipeline/outputs.md), [status](docs/pipeline/status.md)
- [Minimum content](docs/skills/minimum.md), [packaging](docs/skills/packaging.md)
- [Existing examples](examples/README.md): retained historical cases; not the current complex-resource acceptance trial

Engineering tests: `python -m unittest discover -s tests -q`. Agent benefit evaluation remains separate.
