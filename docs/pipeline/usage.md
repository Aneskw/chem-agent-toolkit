# Pipeline usage and current limits

This is the first implementation of the agreed task-focused build flow. The
design describes the intended architecture; this guide describes actual behavior.
It creates English runtime skills. It does not measure Agent gains.

## Requirements

- Python 3.11+; authenticated Codex CLI on PATH (tested with 0.158.0), using its existing configured
  model unless `model` is supplied in the build configuration.
- Git on PATH for repository/version provenance and pinned-source verification.
- JSON configurations need no parser dependency. Install PyYAML for YAML configs
  or multiline YAML frontmatter; install pypdf to read text PDFs. Scanned PDF OCR
  is not provided. Optional dependencies: `requirements-pipeline.txt`.
- Existing environments, tools and small test data remain the user's responsibility.
  The pipeline does not install packages, download weights, clone repositories,
  train models or deploy services automatically.

## First real local example

With RDKit already installed:

```text
python examples/prepare_rdkit.py
python -m creation_pipeline plan .pipeline/sample-configs/rdkit-direct.json --preflight
python -m creation_pipeline build .pipeline/sample-configs/rdkit-direct.json
```

The preparation script extracts installed RDKit API docstrings, records the version
and source hashes, and creates explicit check configurations. It does not call a
model or write a final skill. The direct check executes the Python example from
the model-authored SKILL.md and checks ethane's documented weight. The extension
configuration adds a user-defined mass-window filter with positive/negative cases:

```text
python -m creation_pipeline build .pipeline/sample-configs/rdkit-extension.json
```

These are engineering cases, not a scientific benchmark or Agent efficacy study.
For the extension, accepting a numerical mass window does not establish drug-likeness.

For a lightweight adapter around an existing implementation:

```text
python examples/prepare_adapter.py
python -m creation_pipeline build .pipeline/sample-configs/descriptor-adapter.json
```

This recovers the original small descriptor script from baseline `6bb535a` and
asks for a portable batch-format adapter with order/error preservation tests.
It is not evidence that full paper-to-implementation reconstruction is supported.

## Configuration

```yaml
task: Package one specific existing tool capability.
sources:
  - id: tool
    path: ../../my-tool
    # ref: exact already-checked-out Git revision, if applicable
  - id: documentation
    path: ../../my-tool-docs.md
intent: direct             # direct or extension
limits:
  model_calls: 16          # includes read requests and review; not 16 skill drafts
  repair_rounds: 2
  model_timeout: 300
  check_timeout: 60
  total_seconds: 1800
```

Relative source paths resolve from the configuration file's directory. A source
can be a local directory/file or a direct HTTPS document URL (`url` instead of
`path`), optionally with an expected `sha256`. A GitHub repository page is not a
repository checkout: supply local source code or a direct document URL. A `ref`
is verified against a clean local checkout; the pipeline never switches that checkout.
Without `ref`, the current commit/dirty state and hashes of read files are recorded.
Remote content is size-bounded and stored by content hash; critical read excerpts
are retained. Source licenses remain relevant to redistribution.

The source index omits hidden dependency/configuration stores and links. A capped
index is explicitly marked; the model can list directories and read/search selected
files. Large files and read ranges have configurable limits. The pipeline does not
claim to have read an entire repository because it indexed some filenames.

Optional fields: `model`, `notes`, `checks`, `http_only`, `environment: {allow: [VARIABLE_NAME]}`.
Only environment variable names belong in configs, never credentials. Unknown fields
are rejected. Preflight validates configuration only, without fetching sources,
calling a model or verifying source availability.

## Execution checks

User-configured checks are trusted execution requests. Example:

```yaml
checks:
  - name: documented-example
    argv: ["{python}", "/absolute/path/to/verify_example.py", "{package}"]
    expected_exit: 0
    stdout_contains: ["expected-result"]
    kind: positive
```

Each check has its own working directory. Macros: `{python}`, `{package}`, `{run}`,
and `{source:ID}`. `argv` is an argument list, not a shell command. An assertion is
required: `stdout_contains`, `json_equals` (dot-separated JSON key paths), or nonempty
`artifacts` relative to `{run}`. Expected rejection can use a nonzero `expected_exit`.
Exit code alone, `--help` or an import alone is not sufficient result evidence.

Models can propose additional checks backed by read evidence. They are not executed
by default. `--execute-generated-checks` explicitly trusts those proposed commands.
Skipped proposals do not block an otherwise covered configured check, but no actual
required execution leaves the package a draft. Extension readiness also requires
executed positive and negative checks plus a targeted content review.

Checks run with the current user's permissions; shell-free execution is not an OS
sandbox. It does not guarantee that arbitrary Python cannot affect source files.
Review untrusted source/code before opting in. Most environment variables are omitted;
explicitly allow only credentials required for the intended tool/service. Known
credential patterns are redacted from retained diagnostics. Generated package files
are screened for common token literals, not certified free of every possible secret.

## What happens during a build

1. Index sources and mediate model requests to list/read/search selected files.
   Read an initial bounded view of at most two explicitly supplied document files;
   directories remain on-demand and further ranges can always be requested.
2. Record a concise task plan and source evidence. Missing implementations can block.
3. Ask the model for complete file contents, optional scripts and proposed checks.
4. Save those contents verbatim in staging; do not render fixed Markdown chapters.
5. Check frontmatter, links, Python syntax and exact author coverage quotations.
6. Execute configured/opted-in checks; verify package/source immutability.
7. For private scripts/extensions, perform a separate targeted model content review.
8. Repair reported failures within configured call/round/time limits.
9. Produce the package, manifest/hashes and one concise build.json.

Author coverage quotations locate the four required topics; they are not semantic
proof. Model content review is not independent scientific validation. Compact
direct wrappers avoid an unconditional second full model review.

The local backend uses a tool-free Codex final-response protocol. The model requests
reads through JSON actions; the program controls paths and saves authored file text.
The invocation disables shell, apps, plugins, browser and delegation capabilities,
and skips host skill discovery to avoid unrelated instructions. CLI feature flags
can change across versions; incompatible versions fail explicitly rather than
silently enabling a different execution path. Existing global settings are unchanged.
Unexpected actual tool events or incomplete model turns fail the call. The backend
still needs the CLI's existing auth/state access and network connectivity. It does
not bypass approvals or retry indefinitely when authentication/network access fails.

For repeated WebSocket connection failures, optional `http_only: true` uses a
per-invocation OpenAI provider alias with the same login and default endpoint,
and disables WebSocket transport. It currently supports the built-in OpenAI
provider without a named CLI profile only. It does not edit global settings or
change the selected model. See the [official OpenAI configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

User-configured MCP servers are disabled individually for model calls; an empty
TOML table does not remove inherited servers. Server IDs currently need letters,
digits, hyphens or underscores for the CLI override syntax. Unsupported IDs fail
explicitly. Runtime tool access remains a separate, explicitly configured check.

Reviews distinguish file defects from missing source/execution evidence. The
latter leaves a draft for input or environment completion, rather than repeatedly
asking the author to invent a missing source or rewrite working code.

## Outputs and statuses

```text
.pipeline/
  cache/                  # content-addressed remote documents
  runs/<id>/              # registered staging/check/debug work
  outputs/<id>/
    <skill-name>/         # runtime package
    build.json            # provenance, hashes, checks, usage and limitations
  failures/<id>/          # failure record and available authored package
```

- `ready`: applicable required checks passed for the tested scope.
- `draft`: plan/skill exists, but required execution/review is missing; a plan-only
  output is also draft and has no runtime package.
- `blocked`: missing source, implementation or required resource prevents progress.
- `failed`: model, file or execution checks failed within the available budget.

Successful ready builds remove their registered temporary workspace by default.
`--keep-debug` keeps redacted prompts/responses for diagnosis. Drafts/failures keep
work for inspection; build.json points to it. The default record is not a complete
archive for exact model replay. Unknown token usage stays unknown. Pipeline revision
and dirty state, specification hashes and source excerpts are recorded.

```text
python -m creation_pipeline check .pipeline/outputs/<id>
python -m creation_pipeline install .pipeline/outputs/<id> --destination ./skills
python -m creation_pipeline clean <id> --dry-run
python -m creation_pipeline clean <id>
```

`check` verifies the recorded manifest and current static structure; it does not rerun
execution or upgrade a draft. A standalone package check is static-only. For changed
files, rebuild before installation. `install` refuses non-ready records, content
changes, linked paths and existing destinations. No overwrite, auto-install, commit,
category mirroring or Git push occurs. Keep an adopted build.json separately under
build-records when committing an installed skill.

`clean` removes only the registered per-run temporary directory after absolute-path
and link checks. It leaves inputs, outputs, failure records, shared cache and formal
evaluation evidence untouched. It cannot clean arbitrary directories or the legacy
migration backup. Cache eviction and automatic retention scheduling are deferred.

## Tests and remaining work

```text
python -m unittest discover -s tests -v
```

Deterministic test model fixtures are explicitly marked replay. Actual live builds
are listed in the acceptance record. Broader papers, heavyweight tools, remote/GPU
environments and Agent effectiveness require separate evidence. The current API can
describe those interfaces, but their execution is not validated by a local RDKit case.
