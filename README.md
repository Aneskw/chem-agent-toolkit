# Research Skill Creation Pipeline

Discover tool Skills from papers, code and documentation, prepare shared Docker environments, author and independently review content, and run selected code checks before delivering Skill packages and downloadable images.

Resource groups run serially. Each group is discovered once, then its candidates are built individually. All groups share source snapshots and the tool environment library.

## Prerequisites

| Component | Requirement |
| --- | --- |
| Python | 3.11 or later |
| Codex CLI | Available on PATH, authenticated with your account, with access to the selected model |
| Docker | A running Linux container engine; Windows can use Docker Desktop |
| Git | Required when acquiring Git repository sources |
| Network | Access to the model service, sources, registries and build dependencies |
| Publishing account | Upload rights to the target GHCR Package; optional for local-only validation |

Live build validation currently covers CPU Linux/amd64. Scientific tools are installed in Docker images.

Run from the repository root. These commands use Windows PowerShell:

```powershell
python scripts/bootstrap.py
codex login
docker info
docker login ghcr.io -u YOUR_GITHUB_USERNAME
```

Bootstrap creates `.venv` and installs the pipeline's JSON Schema validation and YAML parsing dependencies from [requirements.txt](requirements.txt). Model authentication uses the Codex CLI account; no model API key file is required. At the GHCR password prompt, enter a classic token with `write:packages`. The publishing account can be independent of the source repository owner.

See [Codex CLI](https://learn.chatgpt.com/docs/codex/cli) for client setup and [GitHub Container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) for publishing credentials. On Linux, run bootstrap with Python 3.11+ and replace `.\.venv\Scripts\python.exe` below with `.venv/bin/python`.

## Input configuration

Save `input.json` in the repository root. Replace `your-account` with your lowercase publishing namespace:

```json
{
  "workflow": "shared-environments",
  "prompt": "Discover source-grounded RDKit tool Skills with clear inputs and outputs.",
  "model": {"backend": "codex_cli"},
  "resource_groups": [
    {
      "id": "rdkit",
      "sources": [
        {"id": "guide", "url": "https://www.rdkit.org/docs/GettingStartedInPython.html"},
        {"id": "api", "url": "https://www.rdkit.org/docs/source/rdkit.Chem.Descriptors.html", "related_to": ["guide"]}
      ]
    }
  ],
  "research_access": "supplement",
  "network": true,
  "environments": {
    "root": "./tools",
    "repository": "ghcr.io/your-account/chem-tools"
  }
}
```

Paths are relative to the configuration file. Put related papers, code and documentation in one resource group. Set `model.name` to select a model explicitly, or omit it to use the CLI configuration/default. Use the same `environments.root` across batches to share environments. See [configuration](docs/pipeline/configuration.md) for all fields.

You can also generate a configuration with `.\.venv\Scripts\python.exe -m creation_pipeline init --model YOUR_MODEL --output input.json`, then edit its sources and publishing target.

## Check and build

```powershell
.\.venv\Scripts\python.exe -m creation_pipeline build input.json --preflight
.\.venv\Scripts\python.exe -m creation_pipeline readiness input.json --mode build
.\.venv\Scripts\python.exe -m creation_pipeline build input.json --state-dir .pipeline/shared --library-dir skills-shared
```

The first two commands validate configuration and observe known prerequisites without model calls. Build performs actual model and file-tool permission checks before starting the workflow. Candidate counts, repair rounds and model calls have no default aggregate cap; configure `limits` as needed.

A newly created GHCR Package is Private by default. If anonymous access blocks delivery, make the Package Public and resume with the returned `build_id`:

```powershell
.\.venv\Scripts\python.exe -m creation_pipeline resume BUILD_ID --state-dir .pipeline/shared --library-dir skills-shared
```

Resume retains completed authoring, builds and code verification. Further tags in a public Package normally need no visibility change.

## Results

```text
skills-shared/
  verified/NAME/              # Skills meeting all delivery requirements
  pending-validation/NAME/    # Necessary code still needs validation
tools/                       # Environment index, versions and full build materials
.pipeline/shared/            # Workspaces, source snapshots, review and execution records
.pipeline/skill-libraries/    # Private delivery indexes, locks and export staging
```

A Skill package contains `SKILL.md`, `runtime.json` and any useful scripts or references. Images are stored in Docker and the configured GHCR Package, using version tags such as `rdkit-v1`. Candidates with build or publication failures remain in internal records.

The delivery directory contains packages only. Library commands find their private index automatically; build logs, catalog records, locks and staging directories are not included in installed Skills.

```powershell
.\.venv\Scripts\python.exe -m creation_pipeline library skills-shared --include-candidates
.\.venv\Scripts\python.exe -m creation_pipeline install skills-shared --name SKILL_NAME --destination installed
```

For local-only validation, set `environments.publish=false`. This mode needs no GHCR login and does not export packages to the delivery library.

See [the workflow](docs/pipeline/shared-creation.md), [operations](docs/pipeline/batch-operations.md), [examples](examples/README.md) and [documentation index](docs/README.md).
