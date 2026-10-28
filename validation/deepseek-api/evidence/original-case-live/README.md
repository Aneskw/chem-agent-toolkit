# Evidence: the single live DeepSeek request on the saved original case

One request, no retry, 600 s cap. It consumed the pre-batch verification slot and is
**not** part of the 8-call batch ledger (the batch never started).

| File | Meaning |
| --- | --- |
| `result.json` | verifier verdict: `plan_rejected`, 1 request, elapsed, request id, redaction check |
| `model-request.json` | redacted `deepseek_api` audit record: endpoint, model, the parameters actually sent, prompt/schema/messages fingerprints, deadline scope |
| `model-attempts.json` | request ledger (one attempt, HTTP 200, completed) |
| `model-stream.json` | stream shape (chunks, keep-alives, bytes) |
| `answer-plan.json` | the plan the model returned (schema-valid) |
| `answer-summary.json` | structural summary, both gate failures, and the conclusion |

Result in one line: the transport, the `[DONE]`/`finish_reason` completion and the
local PLAN_SCHEMA validation all passed; the **unchanged acceptance-fixture gate**
rejected the plan on one negative case (`behavior-reject-empty-smiles`) because it
used an unsupported fixture field, and without that field the case has no assertion.

Because the plan did not pass the semantic gate, the full acceptance batch was not
started (0 model calls beyond this one, 0 Docker builds, 0 business cases, 0 queries).
