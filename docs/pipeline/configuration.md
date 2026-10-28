# Configuration

JSON or YAML object. Only sources is required; YAML needs PyYAML. Unknown top-level fields are rejected. Paths resolve relative to the configuration file. Parser/defaults: creation_pipeline/models.py.

| Field | Default | Meaning |
| --- | --- | --- |
| sources | required nonempty array | Local files/directories, known URLs/repos/paper identifiers/catalogs |
| prompt / notes | empty strings | Optional guidance; task is a legacy prompt alias |
| constraints | {} | Model-interpreted preferences, not executable enforcement rules |
| model | {} | Optional name passed to Codex CLI; a model-name string is also accepted |
| execution | {profile: production} | production or development |
| limits | see below | Optional execution/resource overrides |
| network | true | Enable known-address acquisition, including supplements; not search |
| execute_generated_checks | false | Historical internal helper setting; normal builds always map business checks to Docker, regardless of this value |
| environment | {allow: []} | Runtime environment variable names to pass, never secret values |
| batch | {label: skills, tags: []} | Readable batch label and simple tags |
| adoption | {enabled: true} | Adopt eligible individual skills |
| http_only | false | Codex built-in-provider transport override |
| checks | [] | User-defined check objects, each with candidate name |
| intent | auto | Legacy guidance direct/extension/auto; explain behavior in construction |
| draft_only | false | Persist drafts without formal qualification; never an execution bypass to accepted |
| runtime_requirements | {} | Candidate declarations with status, reason and verifiable source citations; conflicts stay unknown |
| runtime | {} | Candidate binding/plan/options/resource_refs/constraints/requirements; absent plan invokes source-grounded planner. `requirements` defaults to the creation prompt plus `constraints` and anchors the invalid-input classification |
| runtime_defaults | {} | Runtime preparation settings shared by every candidate; merged under `runtime.<candidate>` (per-candidate keys win). Lets a normal creation fix provider options before discovery names the candidate |
| revision_parents | {} | Explicit expected current revision for reviewed replacements; prevents accidental overwrite |

Runtime preparation and resource references are described in [Docker execution](docker-execution.md)
and [recovery](runtime-recovery.md). References contain paths/hashes or environment variable
names, never credential values. Remote GPU, external resource mounts, secret delivery and
service probes remain unsupported execution contracts, even when the resources exist.
Temporary Docker/resource absence is recorded separately from unsupported contracts.

`model.backend` selects the native Agent stages and stays `codex_cli`; existing configurations remain accepted and no other value is supported there. The structured, tool-free calls (entry association, runtime planning, contract diagnosis) can be routed to the opt-in DeepSeek API backend with `runtime.<candidate>.options.backend=deepseek_api` plus `runtime.<candidate>.options.api_model` (or `DEEPSEEK_MODEL`). `model.name` remains the Codex model used by discovery, authoring and independent review and is never sent to the API provider. There is no automatic fallback between backends, and API/Ollama settings such as `base_url`/`api_key_env` inside `model` are still rejected before resource fetching. See [DeepSeek API backend](../integration/deepseek-api-backend.md). The underlying Codex connection to its model is unaffected. User model selection and Windows sandbox configuration are retained; arbitrary CLI profiles/plugins are not inherited.

## Structured-call options

Validated by `planner.options`; they apply to the three `model_call` stages only.

| Option | Default | Meaning |
| --- | --- | --- |
| backend | codex_cli | codex_cli (unchanged child process) or deepseek_api (explicit, no fallback) |
| api_model | null | provider model for the API backend; null reads DEEPSEEK_MODEL and never borrows model.name |
| api_retries | 0 | explicit retries, 0-3, counted in the ledger and inside the same total deadline |
| api_max_output_tokens | 65536 | max_tokens actually sent; 1-393216 |
| api_stream | true | SSE streaming; completion requires data: [DONE] and finish_reason=stop |

The API backend reads `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL` and
`DEEPSEEK_ALLOW_CUSTOM_ENDPOINT` from the environment or the git-ignored repository
`.env`. A non-official host is refused unless it is explicitly declared as a custom
endpoint. Missing configuration fails closed: the stage stops, no request is sent.

## Sources

Each source has exactly one of path, url, repo, paper, table. Optional id (simple unique identifier), ref, sha256, license and storage are accepted.

- path: local file or directory. ref requires a clean local repository at that revision.
- url: a known HTTPS resource, preserving unknown/binary types. HTML is retained rather than replaced by a guessed PDF link.
- repo: known HTTPS Git repository; resolved version recorded. Archive acquisition streams to disk; no checkout hook or installation is run.
- paper: DOI/arXiv identifier, resolved to a public full text when available; no title search.
- table: CSV/TSV/XLSX resource catalog with pdf/url/doi/repository/github/path columns. For ordinary data use path.
- storage: copy (default) or reference. Reference applies to individual files, avoids a duplicate copy and checks source hashes; directories use filtered snapshots.
- sha256: optional expected single-file digest; license is provenance metadata, not a legal assessment.

Unknown file extensions are retained; parsing support is separate. No implicit input size/count cap. Optional development limits can deliberately narrow a trial; limitations/exclusions are recorded. See [resources](resources.md).

## Execution profiles and limits

Production defaults to null (disabled) for model_calls, candidate_calls, model_timeout, total_seconds, discovery_seconds, agent_events, max_candidates, max_builds, source_bytes, source_total_bytes, source_files, package_bytes, network_requests and repair_rounds.

Development defaults: model_calls=8, max_candidates=3, max_builds=1, repair_rounds=2. It does not impose a model time limit. All defaults can be explicitly overridden; null disables a limit. repair_rounds may also be zero. Quality standards do not change between profiles.

```json
{
  "sources": [{"path": "./research-code"}],
  "execution": {"profile": "development"},
  "limits": {"model_calls": 6, "max_candidates": 2, "max_builds": 1}
}
```

network_timeout=60 seconds, converter_timeout=60 seconds and check_timeout=120 seconds are per-operation fault controls, not whole-build deadlines. converter_timeout/check_timeout may be null for a deliberately long check. Agent resources are original files and optional prepared views; no host read-request protocol or text-context pagination is used.

model_calls counts CLI turns, not internal inference requests. Missing usage is unknown, not zero. No automatic monetary-cost estimate. Optional agent_events counts CLI-reported tool completions; the CLI does not report every native tool there.

## Check definitions

name, argv (string array, no shell), cwd ('{run}' by convention), expected_exit (0), stdout_contains ([]), optional json_equals/artifacts, kind, and generated-check evidence/purpose. At least one result assertion is required. Check names must not collide with host validation names.

Macros: {python}, {package}, {run}, {source:ID}, only in check definitions, never runtime skill text. Execute the actual delivered script or explicitly selected example path. No blanket execution of all Python blocks. A mock or syntax check does not establish a real tool run. Configured assertions cannot be silently weakened.

## Tool-free model transport diagnostics

Runtime structured calls retain configured model/provider/auth settings and disable unrelated host integrations. Request and schema records, redacted streams, event metadata and process completion are stored under the caller audit directory. Process states include `start_failed`, `running`, `exited`, `timed_out`, `cancelled` and `io_failed`; `exited` describes transport exit, not model success. A nonzero exit, missing `turn.completed`, `turn.failed`/`error`, incomplete I/O or forbidden tool event cannot produce an accepted model answer. Windows uses the existing supervised process Job, POSIX uses a dedicated process group; cancellation and parent exit also clean descendants. No new CLI flag, hidden total quota or higher operation timeout is introduced.

Native discovery/author/reviewer sessions retain their separate partner transport (`--ignore-user-config` with explicit model), not the tool-free configuration policy. Do not claim provider/auth configuration equivalence between those transports.

Native stdin is sent concurrently so an explicit turn timeout still applies when the child does not read input. Reader/writer exceptions, failed events (even alongside a completion event), missing completion and incomplete streams reject the answer. Startup failures retain failed receipts; Windows uses the existing process Job and POSIX a dedicated process group to clean descendants on every exit. Receipts record stream completion and I/O errors. This does not add a production turn timeout or change candidate-session/reviewer separation.

Native cleanup joins only started workers and retains cleanup errors without replacing the original cancellation. A POSIX process that deliberately creates a separate session can escape the owned group: incomplete stream shutdown is recorded as failure, and the caller does not synchronously close a pipe owned by a blocked worker. This is bounded failure reporting, not a guarantee of terminating arbitrary detached processes; no global process enumeration or host permission changes are used.
