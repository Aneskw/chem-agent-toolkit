# Admitted calls and provider observations

The batch call guard remains the admission point for the caller's model/time
budget. It appends exactly one ticket per admitted invocation and returns that
ticket to the runtime caller. Existing no-argument guards returning None remain
supported. Receipt observation never admits another call or changes the budget.

Planning, entry association and contract diagnosis label the ticket with their
actual selected structured backend/model. Independent runtime reviews use their
separately selected native backend/model. Successful provider/stage receipts then
update that same ticket with observed model/backend, raw usage, elapsed time,
request_count when supplied, and prompt/schema identifiers. Request headers,
endpoints, prompts and arbitrary provider data are not copied into the summary.
Failed transports without an observed receipt retain attempted status and unknown
usage; no tokens or billing are guessed.

This fixes a historical reporting defect: the outer guard labelled every runtime
invocation as runtime_planning using the native session model and usage=None, even
when its detailed receipt correctly identified DeepSeek. The detailed original
receipts remain authoritative for those older rounds; their summaries are not
rewritten. Offline replay of both run72 planning receipts is saved in
`E:\Users\27343\Docker\acceptance-openbabel-run72-20261029\call-accounting-offline-replay.json`.

Raw provider usage keys are preserved. Existing reported_totals groups counters
by their actual key names; native input_tokens and API prompt_tokens are not
silently renamed into a single bill. usage_fully_reported means each admitted
ticket has usage, not that every vendor retry or underlying CLI tool-loop request
has complete billing data. API final-response usage can exclude earlier retry
usage; request_count is a separate observation. model_metrics.usage_scope states
this boundary and monetary_cost stays unknown.

Four focused regressions use mocked transport only: actual planner path retains
the API identity/usage once, guard denial prevents a model call, None-returning
legacy guards still work, failed transport has no fabricated usage, and review
receipt copying preserves timeout state while excluding headers. No live model
requests were used for this change. Development is isolated from the live run73.
