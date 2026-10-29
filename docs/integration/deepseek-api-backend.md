# DeepSeek API backend for the structured model calls

**Current scope update (2026-10-29):** the table and original verification below
describe the initial structured-only implementation. Current code additionally
supports opt-in `model.backend=deepseek_api` for discovery, authoring and review
through `creation_pipeline/agent/api_provider.py` and `NativeSession._api_stage`:
one bounded completion returns structured records/files, followed by the existing
host finalization and validation. It does not emulate the CLI tool loop. The
structured backend remains separately selected under runtime options; neither
backend is an automatic fallback. The active acceptance campaign explicitly uses
Codex CLI native stages plus DeepSeek structured stages. Four successful scenarios
do not establish all-DeepSeek end-to-end acceptance. See
[current campaign](extended-acceptance-campaign.md) and
[the additional Open Babel experiment](planner-openbabel-experiment.md).

This document describes the opt-in DeepSeek backend added in this copy of the
repository. It records exactly which model stages move to the API, which stay on
the Codex CLI, the protocol the implementation is written against, and the limits
of the verification that has actually been performed.

## 1. Scope: what changes and what does not

The pipeline has two different model transports. Only one of them is migrated.

| Stage | Transport before | Transport after | Migrated? |
| --- | --- | --- | --- |
| Discovery / authoring (`NativeSession.stage`) | Codex CLI | Codex CLI | no |
| Independent content review (`review_snapshot` → `NativeSession`) | Codex CLI | Codex CLI | no |
| Entry association (`entry.associate` → `model_call.call`) | Codex CLI | DeepSeek API | **yes** |
| Runtime planning and plan repair (`planner.plan` → `model_call.call`) | Codex CLI | DeepSeek API | **yes** |
| Contract diagnosis (`diagnosis.diagnose` → `model_call.call`) | Codex CLI | DeepSeek API | **yes** |

The three migrated stages are exactly the call sites of the structured, tool-free
`creation_pipeline.runtime.model_call.call(prompt, schema, model, ...)` interface
that returns `(answer, receipt)`. The native Agent stages are *not* rewritten and
their configuration still requires `model.backend = "codex_cli"`.

This is therefore a partial migration, not "all model stages now use DeepSeek".
Discovery, authoring and review still spend Codex turns, and those turns are still
counted by `limits.model_calls`.

## 2. Official service facts used

Read from `api-docs.deepseek.com` on 2026-10-27 (first API call, models & pricing,
chat completions reference, JSON output, thinking mode, rate limit, error codes):

* OpenAI-compatible base URL `https://api.deepseek.com`, Anthropic-compatible base
  URL `https://api.deepseek.com/anthropic`. This backend uses the OpenAI format:
  `POST /chat/completions` with `Authorization: Bearer <key>`.
* Model identifiers documented as `deepseek-flash` and `deepseek-v4-pro`
  (`deepseek-v4-flash` is a legacy alias served by the same model).
* `response_format` accepts only `text` or `json_object`. **There is no caller JSON
  Schema parameter**, so the service never enforces the planner schema.
* `finish_reason` ∈ `stop`, `length`, `content_filter`, `tool_calls`,
  `insufficient_system_resource`, `aborted`. Only `stop` is a completed answer.
* Streaming is SSE terminated by `data: [DONE]`; usage rides on the last chunk
  before it, whose choice carries no new content and a non-null `finish_reason`.
* `: keep-alive` (stream) and blank lines (non-stream) are liveness only. A request
  that has not started inference is closed by the service after ten minutes.
* `reasoning_effort` accepts `none|low|high|max`; `minimal`→`low`, `medium`/`xhigh`→
  `high`. Thinking is enabled by default at effort `high`.
* Errors: 400/422 request, 401 auth, 402 balance, 429 rate limit, 500/503 server.

The implementation does **not** guess any of these. The endpoint defaults to the
official host, the model must be configured, and a non-official host is refused
unless it is explicitly declared as a custom endpoint.

## 3. Configuration

`creation_pipeline/runtime/deepseek_api.py` reads, in order of precedence, the
process environment and then the repository `.env` (git-ignored, values never
logged):

| Name | Required | Meaning |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | yes, for a live call | bearer credential |
| `DEEPSEEK_MODEL` | yes unless `api_model` is set | provider model identifier |
| `DEEPSEEK_BASE_URL` | no | defaults to `https://api.deepseek.com` |
| `DEEPSEEK_ALLOW_CUSTOM_ENDPOINT` | no | required to accept a non-official host |

The backend is selected per candidate in the pipeline configuration, under the
runtime stage options:

```json
{
  "runtime": {
    "<candidate-name>": {
      "options": {
        "backend": "deepseek_api",
        "api_model": null,
        "api_retries": 0,
        "api_stream": true,
        "api_max_output_tokens": 65536,
        "model_timeout": 600,
        "reasoning_effort": "medium"
      }
    }
  }
}
```

`validation/deepseek-api/acceptance-input.json` is the acceptance configuration for
this copy and selects the backend exactly like the example above.

Two model identities are kept apart on purpose:

* `model` — the native Agent/Codex model. It is still used by discovery, authoring
  and the independent reviewer, and it is **never** sent to the API provider.
* `api_model` — the API provider's model. When it is `null` the backend reads
  `DEEPSEEK_MODEL`; it never borrows the Codex name.

`backend` defaults to `codex_cli`, so existing configurations are unchanged. An
unknown backend name is a configuration error, not a reason to try another one.

`validation/deepseek-api/acceptance-input.json` is the acceptance configuration for
this copy. It reproduces the finalized explicit-script-binding case - source set,
prompt, execution profile, limits and the `binding` object are byte-identical to
`validation/final-acceptance-review/input-batch-4.json` - and adds only the DeepSeek
provider options. The binding fixes `scripts/terminal_fragments.py` as the entry, so
a fresh creation must author that exact path; otherwise preparation stops at
`binding_unresolved` without a model call.

## 4. Contract and correctness properties

* `model_call.call` keeps its signature and its `(answer, receipt)` return contract.
  The Codex path is byte-for-byte unchanged.
* `answer` is always a JSON object that has been validated with `jsonschema`
  against the caller schema. A syntactically valid JSON document that does not
  satisfy the schema is rejected with `model_schema_mismatch`; it is never passed
  on as a plan. The existing planner/entry validators still run afterwards, so
  semantic checks (entry match, source citations, locked tests) are unchanged.
* Success requires *all* of: HTTP 200, a terminal `finish_reason == "stop"`, the
  `data: [DONE]` marker, non-empty content, JSON parse success, local schema
  conformance. A heartbeat, a keep-alive comment or a retry notice is never treated
  as progress and never as success.
* Incomplete output is classified, not accepted: `finish_reason=length` →
  `model_output_truncated`; missing `[DONE]`, missing `finish_reason`, a malformed
  SSE frame, a dropped connection or `insufficient_system_resource`/`aborted` →
  `model_stream_interrupted`; empty content → `model_output_empty`; tool calls →
  `model_output_invalid`.
* There is no fallback. A configuration error, a provider error or an invalid
  answer stops the stage; nothing retries through Codex or another model.
* The caller's budget guard is preserved and still runs before the request. The
  backend adds no hidden call of its own.

## 5. Deadline, retries and accounting

`timeout` is one application-level deadline. Every blocking step re-derives its
budget from what is actually left, so no phase can borrow a stale timeout:

| Phase | Bound |
| --- | --- |
| DNS resolution | runs in a daemon worker, joined with the remaining budget; on expiry the call fails with `model_timeout` (`detail.phase=dns`) instead of overrunning |
| TCP connect | socket timeout armed from the remaining budget, re-checked per address |
| TLS handshake | socket re-armed with the remaining budget after the TCP connect succeeds |
| Send (request line, headers, body) | re-armed immediately before the send |
| Header wait (`getresponse`) | re-armed immediately before the wait, not inherited from connect |
| Stream/body reads | armed from the remaining budget on the socket captured right after `connect()`; a read timeout therefore *is* the deadline, and the reader is never reused after one |
| Retry pause | clamped to the remaining budget |

Two implementation details matter here and were both wrong in the first version:

* `HTTPConnection.getresponse()` drops `connection.sock` when the server answers
  `Connection: close`, so arming through `connection.sock` silently did nothing. The
  live socket is captured after `connect()` (it outlives http.client's reference) and
  every later timeout is armed on that.
* A short per-read slice (for example 5 s) is wrong: `socket.SocketIO` sets a
  one-shot flag, so after a timeout the next read on the same `HTTPResponse` raises
  `OSError: cannot read from timed out object`. A healthy but slow stream would then
  be reported as a broken connection. Reads are therefore armed with the whole
  remaining budget and a timeout is reported as `model_timeout` (`detail.phase`
  `stream_read`), never retried.

A socket timeout that fires because the armed budget ran out is classified
`model_timeout`, not `model_connection_failed`. On expiry or cancellation the
response and socket are closed before the error (or `KeyboardInterrupt`)
propagates.

No SDK is used (`http.client` directly), so there are no implicit retries. A retry
must be configured explicitly (`api_retries`, 0–3). Retries are counted in the
request ledger and share the same total deadline; credential, balance and
request-shape failures are never retried.

The audit directory of every structured call records: `request.json` (endpoint,
model, the parameters actually sent, prompt/schema/messages fingerprints, the
deadline scope, the progress policy), `attempts.json` (per-attempt ledger with
status, HTTP status, elapsed, error class, request id), `stream.json` (chunk,
keep-alive and byte counts), `response.json` on success and `error.json` on
failure, plus `schema.json`. The prompt body is not duplicated there (the callers
already persist it) and the credential is never written.

The receipt returned to the caller adds `backend`, `provider`, `request_params`,
`mapping`, `request_id`, `request_count`, `requests` and `completion` next to the
historical fields.

## 6. Parameter mapping (no false equivalence)

| Codex setting | DeepSeek setting actually sent | Recorded as |
| --- | --- | --- |
| `reasoning_effort: medium` | `thinking: {type: enabled}`, `reasoning_effort: high` | requested `medium`, sent `high`, "compatibility ladder, not an equivalence" |
| `reasoning_effort: none` | `thinking: {type: disabled}` | requested `none`, sent `none` |
| `service_tier: default` | not sent (no provider equivalent) | "not supported by this backend; recorded, never sent" |
| `transport: https` | implicit (single HTTPS JSON call) | endpoint kind |
| `progress_watch` / 240 s stall window | not applied | keep-alives are not generation progress; the total deadline is the only bound |

The backend therefore does not claim the migrated calls run under identical
conditions to the Codex ones.

## 7. What has been verified, and what has not

### 7.1 Offline (hermetic, loopback HTTP server, no real request)

Completion over SSE and over a single response, local schema rejection (missing
field, wrong type, non-object, non-JSON, empty), truncated and incomplete streams
(`length`, missing `[DONE]`, missing `finish_reason`, malformed frame, dropped
connection, `insufficient_system_resource`, streamed error frame, tool calls),
authentication failure, insufficient balance, rate limit (with and without a
configured retry), server error, connection failure, total-deadline expiry on a
silent stream, on a server that never sends headers and on a stalled DNS resolver,
shared deadline across retries, cancellation with connection release, the caller's
budget guard, configuration refusal (missing key, missing model, non-official
endpoint, credentials in the URL, unknown backend) and credential redaction in the
audit directory, the receipt and error messages.

### 7.2 Two different planner fixtures - do not confuse them

| Harness | Prompt | Proves | Does not prove |
| --- | --- | --- | --- |
| `verify_planner.py` | 8,568 B synthetic fixture (`validation/deepseek-api/fixture-source`, no third-party dependency) | the adapter connects, the transport/contract works, the frozen prompt is reproducible | whether the original slow RECAP case behaves better |
| `verify_original_case.py` | the saved historical **45,397 B** RDKit RECAP planning request with its 151,668 B `PLAN_SCHEMA` | the real hard request, judged by the unchanged validators | end-to-end business acceptance |

`verify_original_case.py check` runs entirely offline and proves the saved case is
intact: the prompt and schema match the fingerprints recorded in that run's
`request.json` (`2327f993…`, `67e030bf…`), the inventory is rebuilt from the copied
handoff tree, the explicit markdown-python binding still matches the delivered
package, and the plan that this case historically accepted still passes
`preparation.validate` (8 cases). The replay is therefore comparable to the
historical verdict instead of being a lookalike.

### 7.3 Live status

One real request has been made, on the saved original case. With `DEEPSEEK_MODEL`
`deepseek-flash` and the official endpoint:

```
requests   1 (no retry), HTTP 200, 158.5 s
params     stream=true, response_format=json_object, max_tokens=65536,
           thinking=enabled, reasoning_effort=high (requested medium)
request_id c6842ac2-7d62-4b7d-a67d-152463ca0179
```

Passed: the transport, the documented completion marker (`data: [DONE]` plus a
terminal `finish_reason`), and the local validation against the saved 151,668 B
`PLAN_SCHEMA` - the model returned a complete plan.

Rejected: the **unchanged acceptance-fixture gate** refused that plan on the
negative case `behavior-reject-empty-smiles`, first for an unsupported fixture field
(`stderr_contains`), then - with only that field removed - because the case then has
no assertion at all. Evidence: `validation/deepseek-api/evidence/original-case-live/`.

This is a plan-semantics defect of a single one-shot answer, not a transport defect.
Production would feed the rejection back and spend a repair round; the pre-batch
check deliberately forbids that, so the verdict is "one-shot answer did not pass the
gate", not "the case cannot pass". The request is ledgered separately and was not
charged to the batch budget; the acceptance batch itself was not started.

The remaining unknown is whether routing the planner to DeepSeek helps the original
timeout case: one request says nothing about that, and no performance comparison was
made.

## 8. How to run

```sh
# offline suite (all mechanisms, no network)
python -m unittest discover -s tests -q

# the new backend tests alone
python -m unittest tests.pipeline.test_deepseek_backend -v

# small fixture: frozen planner prompt/schema, rebuild and compare, no request
python validation/deepseek-api/verify_planner.py check

# every prompt surface states the contract the validators enforce (no request)
python validation/deepseek-api/verify_prompt_contract.py

# acceptance path: current-code prompt/schema identity, recorded (no request)
python validation/deepseek-api/verify_acceptance_prompt.py freeze   # or check

# saved original RECAP case: integrity + gate rehearsal, no request
python validation/deepseek-api/verify_original_case.py check

# exactly one real request each (<= 600 s, no retry, no continuation)
python validation/deepseek-api/verify_planner.py run --timeout 600
python validation/deepseek-api/verify_original_case.py run --timeout 600
```

A live `run` needs `DEEPSEEK_API_KEY` and a model in the repository `.env` (or the
environment). Without them it fails closed.

### What the acceptance batch actually sends

The formal batch never reads `validation/deepseek-api/frozen/`; that directory is an
offline diagnostic for `verify_planner.py` only. Every planning round builds its prompt
through `planner.build_prompt()` and its answer schema through `planner.schema_for()`
from the live module (POLICY + the shared invalid-input block, and the schema whose
`acceptance_json` description is the current `ACCEPTANCE_SPEC`), then records the
identity next to the prompt:

```
<audit>/prompt-0.txt              # the exact (redacted) prompt
<audit>/prompt-provenance-0.json  # prompt/schema/policy/description sha256 + bytes
<audit>/receipt-0.json            # backend receipt: prompt_sha256, prompt_bytes, schema_sha256
```

Both backends record the same identity: the Codex CLI receipt carries `prompt_sha256`,
`prompt_bytes` and `schema_sha256`, and the DeepSeek receipt additionally records
`messages_sha256` of the final request body. `validation/deepseek-api/prompt-provenance.json`
pins the current-code identity offline (including the saved RECAP case's round-0 prompt
built by running the real planner up to — never into — the model call), so a stale
prompt/schema can be detected before any request is spent.

The full pipeline acceptance (discovery → authoring → review → Docker build →
business acceptance) is started with the acceptance configuration:

```sh
python -m creation_pipeline build validation/deepseek-api/acceptance-input.json
```

That configuration reproduces the finalized explicit-script-binding case (source
set, prompt, execution profile, limits and the binding object verbatim) and adds
only the DeepSeek provider options. It requires the Codex CLI for the native stages,
Docker for execution and a working `.env`; it was deliberately not started, because
neither provider is currently usable (`validation/deepseek-api/launch-check.json`).

One dependency to know before the batch: because the entry is bound explicitly to
`scripts/terminal_fragments.py`, a fresh creation must author that exact path.
Otherwise runtime preparation stops deterministically at `binding_unresolved`
without a model call - the binding is not widened automatically.
