# Model call accounting

NativeSession records arguments, session identity, events, results and available usage for each Agent turn. Resume reads existing receipts and continues the saved stage session.

The shared workflow's summary.model_metrics is produced by agent.metrics.summarize_usage:

| Field | Meaning |
| --- | --- |
| reported_totals | Nonnegative integer usage reported by the CLI; null when unavailable |
| usage_unknown_calls | Turns without interpretable usage |
| usage_fully_reported | Every recorded turn supplied aggregatable usage |

session_cumulative computes increments per session_id, starting a new segment after a counter reset. incremental sums per-turn values. Cached and reasoning counters remain subsets rather than additional totals.

model_calls counts admitted Agent turns, not underlying requests or fees. Missing usage remains unknown. Inspect individual receipts for request and error details.

RuntimeRequest structured calls use admission tickets. Planning, entry association and diagnosis record their actual backend/model. Receipts update the same ticket without another admission. Failed calls retain attempted status and do not invent provider usage.
