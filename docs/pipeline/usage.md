# Usage

## Requirements

Python 3.11+ and Git. Use an authenticated Codex CLI on PATH, or configure a compatible chat-completions/Ollama endpoint. Text PDF extraction requires `pypdf`; YAML configurations and multiline frontmatter require `PyYAML`. Both are optional dependencies in `requirements-pipeline.txt`.

No tool dependencies, containers, weights or services are installed automatically. Plain-text and code sources need no document parser dependency. Scanned PDFs and visual interpretation are not supported.

## Resource-only configuration

```yaml
sources:
  - id: paper
    url: https://example.org/article.xml
  - id: code
    repo: https://github.com/example/tool.git
    ref: v1.2.3
prompt: Prioritize reusable inference and result-inspection capabilities.
constraints:
  exclude: [training, broad-research-workflows]
limits:
  max_candidates: 8
  max_builds: 4
  model_calls: 40
  candidate_calls: 10
  repair_rounds: 2
  total_seconds: 1800
network: true
execute_generated_checks: false
```

Only `sources` is required. User guidance and constraints are supplied to discovery, authors and reviewers. `intent` defaults to `auto`; explicitly set `direct` or `extension` only to restrict the kind of behavior. Multiple tools do not automatically imply an extension.

Each source needs exactly one of:

| Field | Meaning |
| --- | --- |
| `path` | Local file or directory |
| `url` | Direct HTTPS document; limited PDF-link following from HTML |
| `repo` | HTTPS Git address; an optional `ref` is resolved to a commit |
| `paper` | `arxiv:...` or `doi:10...`; DOI resolution looks for a public PDF through OpenAlex |
| `table` | CSV/TSV/XLSX resource catalog |

Local `path`/`table` values resolve from the configuration file. An optional file `sha256` verifies supplied bytes. A local directory `ref` requires a clean checkout at that revision; the program never switches the user's checkout. Remote Git sources export supported text blobs at the resolved commit, not weights or submodules. The export is evidence, not a fully runnable installation.

Catalogs recognize `pdf`, `url`, `doi`, `repository`, `github` and `path` headings. XLSX reads the first worksheet. Missing mappings are reported; catalogs are not arbitrary spreadsheet analysis. Use explicit sources when mappings are ambiguous.

Readers support text/code, text PDFs, HTML/XML, DOCX text, notebook code/Markdown, and read-only SQLite schemas. Notebook outputs and SQLite data rows are not treated as documentation. Models can request paginated list/read/search actions; indexing does not imply full reading. Oversized files and partial failures appear in source diagnostics.

The program snapshots eligible files into a content-addressed cache. Continuation reads those bytes even if the original input later changes. A modified/missing snapshot fails verification. Source records distinguish input addresses, resolved addresses and Git commits.

## Network scope

`network: false` disables downloads and repository/identifier acquisition. With network enabled the model may request relevant documents, repositories or identifier resolution through the mediated protocol. Requests and downloads have explicit limits (`network_requests`, `network_timeout`, `source_bytes`, `source_total_bytes`). There is no unrestricted browser, login automation, generic title search, OCR or universal repository discovery.

Related repositories must actually be located in sources or provided; the model must not invent addresses. Acquisition errors remain visible while valid sources continue. A primary document's absence limits the claims supported by the remaining code.

## Models

The default is the existing configured Codex CLI model:

```json
{"model": {"backend": "codex_cli", "name": "your-available-model"}}
```

Omit `name` to use CLI configuration. Optional `http_only: true` changes CLI transport for the built-in OpenAI provider without a named profile; it is not a separate API backend. Inherited MCP servers and built-in execution/browser capabilities are disabled for model calls. The pipeline mediates source requests and separately controls verification execution.

For a compatible API:

```json
{
  "model": {
    "backend": "chat_completions",
    "name": "your-model",
    "base_url": "https://your-provider.example/v1",
    "api_key_env": "MODEL_API_KEY",
    "structured": true
  }
}
```

`structured: true` requests strict JSON Schema. See the [official Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create). For compatible endpoints without this feature, set false to request JSON mode with the schema in the prompt. Compatibility depends on the service/model; incomplete responses and unexpected tool calls are rejected. Credentials are read from the named environment variable, never supplied as literal configuration values.

For local Ollama, set `backend: ollama`, a model `name`, and optionally `base_url` (default `http://localhost:11434`). It uses `/api/chat` with schema format. Remote endpoints require HTTPS; plaintext HTTP is allowed only for localhost. No model downloads or automatic fallback occur.

## Discover, build and continue

```text
python -m creation_pipeline discover sources.json --preflight
python -m creation_pipeline discover sources.json
python -m creation_pipeline build --plan .pipeline/outputs/<id>/plan.json
python -m creation_pipeline build sources.json --execute-generated-checks
```

Preflight checks configuration only: no acquisition or model calls. `plan` is an alias of `discover`. Direct `build` performs discovery and construction in one run.

`discover` saves candidates, important omissions/merges, scope limits and a construction plan. Candidates have rationale, upstream/added behavior, implementation form, required shared tools, source evidence and checks. Zero candidates returns `no_candidates` normally.

You may edit candidate `selected`/priority or refine a candidate in a saved plan. On continuation the schema, evidence, dependencies, specifications and source context are checked again. Do not edit locked source/configuration fields; change the input and rediscover instead. Ready unchanged entities can be reused from the referenced output; drafts/failed entities are rebuilt. The accepted plan hash and reuse are recorded. Ready files are reused only when the whole accepted plan, source context and implementation fingerprint match. This is continuation from a saved checkpoint, not recovery of an interrupted model turn.

`max_builds` limits selected skills; required shared tools are built before consumers and count toward `max_candidates`. Deferred skill names are reported. A deselected or unready shared tool blocks its consumers. Independent candidates continue. Only explicitly supplied existing tool sources are available for cross-batch reuse; there is no global semantic tool registry.

## Verification execution

Model authors propose executable checks grounded in real source examples/tests. Writing a check is not evidence that it ran. Generated checks require `--execute-generated-checks` or `execute_generated_checks: true`. They run as the current user, not inside an OS sandbox; enable only for trusted sources and code. Checks cannot install dependencies or deploy services as a pipeline feature.

Optional user-configured checks must identify the candidate they cover:

```yaml
checks:
  - candidate: discovered-capability-name
    name: expected-output
    argv: ["{python}", "/absolute/path/to/verify.py", "{package}"]
    expected_exit: 0
    stdout_contains: ["expected-result"]
    kind: positive
```

Each check defaults to a fresh `{run}` working directory. Set `cwd: "{source:ID}"` when upstream reads adjacent resources relative to its source directory; diagnostic logs still go to the fresh check directory. Source snapshots must not be modified.

Macros: `{python}`, `{package}`, `{run}`, `{source:ID}`, `{bundle}`, `{tool:NAME}`. These are only for checks, not runtime skill examples. Require actual output assertions (`stdout_contains`, `json_equals`, or nonempty `artifacts`); exit status alone is insufficient. Configured assertions are not rewritten during repair. Removing or changing a previously failed generated assertion leaves an explicit evidence gap, rather than silently making the package ready; failed attempts retain their check definitions and diagnostics.

Allow runtime environment variables by name with `environment: {allow: [VARIABLE_NAME]}`. Secrets remain external. stdout/stderr evidence is bounded and redacted. Timeouts stop the process tree. Package/source hashes are checked after execution. Generated code is not guaranteed harmless merely because arguments avoid a shell.

## Outputs and statuses

```text
.pipeline/
  cache/                         # downloads, repository text exports, snapshots
  runs/<id>/                     # registered temporary/debug workspace
  outputs/<id>/
    summary.json                 # batch outcome, counts, deferrals, usage, limitations
    plan.json                    # continuation checkpoint
    sources.lock.json            # source-context integrity
    records/<entity>.json        # per-tool/skill files, checks and evidence references
    bundle/
      manifest.json              # hashes, entity states and dependency mapping
      skills/<name>/SKILL.md
      tools/<name>/scripts/      # only justified shared adapters
```

Entities: `ready` means applicable checks passed; `draft` means required verification is incomplete; `blocked` means critical implementation/resources are missing; `failed` means checks or generation did not succeed within repair limits.

Batch states additionally include `planned`, `no_candidates` and `partial` (some entities ready and some not). The CLI returns 1 for failed/blocked/partial or check failure, 2 for input/command errors, otherwise 0. Read counts and deferrals, not exit code alone. Engineering readiness does not establish scientific correctness or Agent benefit.

## Check, install and clean

```text
python -m creation_pipeline check .pipeline/outputs/<id>
python -m creation_pipeline install .pipeline/outputs/<id> --destination ./adopted
python -m creation_pipeline clean <id> --dry-run
python -m creation_pipeline clean <id>
```

`check` verifies manifests and static structure; it does not rerun execution. Install only accepts a fully ready bundle, preserves skills/tools layout under `<destination>/<id>/` and refuses overwrite. Copying a single skill may omit shared dependencies; partial bundles need plan selection and rebuilding before installation. Import/adopt skill directories according to the target Agent's discovery rules while preserving their shared paths. Installation alone does not register them with an Agent.

Successful builds and completed discovery clean registered workspaces by default; drafts/failures keep diagnostic work. `--keep-debug` retains redacted prompts/responses. Cleanup never removes inputs, outputs or shared cache. There is no automatic cache eviction. Default records are scoped provenance, not full model replay.
