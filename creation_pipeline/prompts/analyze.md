Discover reusable skills from real research resources without requiring a user task.
This stage ends at candidate discovery. Do not write SKILL.md, author runtime packages,
or call finish; the host invokes a dedicated author stage next. Save only candidate/progress
records here. Summaries describe findings, not package completion.
First understand the resource as a whole (paper overview, README, layout, key examples).
Identify major capability directions, then read selectively to resolve concrete uncertainties.
Do not stop at the easiest API, nor exhaustively read every file. Documentation, implementation,
examples and tests are complementary evidence, not a reading quota.

Judge what useful difficulty a skill removes: choosing the right interface, data/units/index
conventions, scattered steps, state, result semantics, or an existing research-specific method.
Simple/familiar calls can be valuable when concise guidance removes a real recurring difficulty.
Do not invent benefit scores or claim measured Agent gain. No output quota by default.

One coherent capability may use multiple tools; neither a whole library nor each function
is automatically one skill. Keep mandatory preparation and result interpretation together.
Research extensions must reproduce an existing method/code, never invent algorithms,
scientific thresholds, URLs or acceptance policies. Mechanical glue is allowed when transparent.
Independent tools, shared tool layers, MCP and generated environments are out of scope.

For each candidate return name, capability, boundary, value, usage_path (real key interfaces),
construction (explain direct packaging versus existing research/code adaptation), evidence
[{id,claim}], gaps, blocked. Evidence claims identify inspected functions/passages/pages.
eN IDs in resources.json are file locators, not proof of reading. No fixed output filenames,
detailed parameter catalog or executable test commands are required at discovery.
A missing local dependency is normally an execution limitation, not an unpackageable capability.
Mark only the affected candidate blocked; let other candidates proceed.

Use the helper for a concrete missing known URL/repository/DOI, explain why, then continue
in this conversation. No autonomous search or recursive link chasing. End reading when
capability, useful scope, invocation and key uncertainties are sufficiently understood.
Return outcome, summary, candidates, omitted (important exclusions/merges with reasons),
limitations. Distinguish no suitable candidates after adequate inspection from blocked sources
and incomplete work. max_candidates/max_builds apply ONLY when non-null development limits.
You may durably save candidates through the helper as you finish them; final candidates may
be empty with outcome=candidates; saved_candidates must explicitly list the saved names you select.
Use saved_candidates=[] when returning full candidates. Old saved files are not automatically selected.
