# Research Skill Creation Pipeline

Discover, author, independently review, freeze, execute and qualify source-grounded Skills.
Failed candidates retain evidence for explicit recovery. `built`, `available`, `passed` and
`accepted` are separate facts; importing or moving evidence does not inherit current qualification.

Start with [small-batch operations](docs/pipeline/batch-operations.md),
[configuration](docs/pipeline/configuration.md) and the [readiness review](docs/integration/batch-readiness-20261102.md).

## First run

Python 3.11+, Git, the configured authenticated Codex executable and Linux/amd64 Docker are required
for the current executable-Skill configuration. A desktop-bundled executable works on PATH; this is
not ChatGPT UI automation. Host validation dependencies are declared in [requirements.txt](requirements.txt).
PyYAML is optional for YAML. The pipeline never installs host packages or repairs Docker automatically.

```text
python -m creation_pipeline build CONFIG.json --preflight
python -m creation_pipeline readiness CONFIG.json
python -m creation_pipeline build CONFIG.json --state-dir NEW_STATE --library-dir NEW_LIBRARY --keep-debug
python -m creation_pipeline library NEW_LIBRARY --include-candidates
```

Preflight validates configuration only. Readiness observes known prerequisites with zero inference
and zero construction, without qualification. Production defaults have no aggregate cap: set explicit
model/time/candidate budgets before batch use. Admitted model stages are not HTTP counts or fees.

## Implemented scope

- Exact pinned dependency environment sharing and complete ToolArtifact reuse before environment
  planning, for supported closed Python, fixed JSON-resource and Open Babel profiles. A hit still
  requires independent review, current acceptance compilation, actual execution and qualification.
- Explicit backends, without fallback. The current scoped-contract configuration uses Codex for both
  native and structured stages. Opt-in DeepSeek remains supported independently for either.
- Durable accepted/candidates library, installation, import, migration and explicit recovery.
- [Local management](docs/pipeline/local-management-api.md) and
  [read-only reverse references](docs/pipeline/reverse-references.md), with versioned errors and evidence.

See the [current sharing design](docs/integration/shared-tool-layer-current-design.md) for support
boundaries and actual evidence. Arbitrary dynamic loading/external processes, remote distribution,
HTTP/multitenancy, automatic dependency merging and GC are outside scope. Start sequentially; no
campaign-wide budget, production queue or multi-worker scheduler is provided.

```text
python -m creation_pipeline check OUTPUT --config CONFIG.json
python -m creation_pipeline runtime-inspect LIBRARY --candidate NAME
python -m creation_pipeline runtime-validate LIBRARY --candidate NAME
python -m creation_pipeline install LIBRARY --name NAME --destination DESTINATION
python -m creation_pipeline manage REQUEST.json
```

`check` is static auditing, not new qualification. `runtime-resume` can invoke models or rebuild;
inspect failures and budget before recovery. Do not concurrently resume one run. See
[recovery](docs/pipeline/runtime-recovery.md) and [execution](docs/pipeline/docker-execution.md).

## Verification and hygiene

```text
python -m unittest discover -s tests -q
python validation/deepseek-api/verify_prompt_contract.py
python validation/deepseek-api/verify_acceptance_prompt.py check
python validation/deepseek-api/verify_planner.py check
python validation/deepseek-api/verify_skillnet_contract.py
```

Fixtures prove mechanisms, not live model quality or scientific validity. Every live round has new
evidence; unsuccessful rounds are retained. The [October snapshot](docs/integration/current-acceptance-20261029.md)
is historical, not the current test count/backend. Credentials stay in ignored `.env`. Libraries,
`.pipeline` operational data, registries, failure evidence and global Docker data are not disposable caches.
