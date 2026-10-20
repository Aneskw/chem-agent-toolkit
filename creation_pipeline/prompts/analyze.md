Read the actual entrypoint and relevant documentation before planning. Use read,
search and list actions as needed; do not treat the initial index as full reading.
Initial source views are actual reads with evidence IDs. Use them directly; do not
request the same ranges again unless a missing detail requires another view.
Package exactly one independently assessable task. Do not wrap a whole library by
default. Existing calls are valid skills. Use a private adapter only if necessary.
Missing algorithm implementations, weights, access or scientific criteria are gaps,
not permission to invent replacements. Do not reproduce algorithms from formulas.

Return a JSON object in payload with:
- name: lowercase-hyphen skill identifier.
- task, scope, entrypoint: concrete strings, including actual interface and boundaries.
- readiness: callable, adapter_needed, or blocked.
- intent: direct or extension, matching the request.
- added_behavior: concrete description, or "none".
- dependencies: array of strings, including external acquisition/version requirements.
- files: array of {path, purpose}, with SKILL.md and only justified supporting files.
- checks: array of short proposed checks and independently grounded expected behavior.
- evidence: array of {id, claim}, citing real eN IDs returned by read actions.
- gaps: array of strings. Use blocked when missing resources prevent implementing
  the task at all; an unavailable runtime can still allow a useful draft.

Do not generate evaluation benchmark questions. This pipeline does engineering
validation only. Prefer official examples, source tests and explicit task requirements
as test oracles. Explain if you cannot recover an implementation or reliable oracle.
