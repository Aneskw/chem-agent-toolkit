Discover reusable tool capabilities from resources, without requiring a user task.
Read actual docs AND relevant implementation/examples/tests using list/read/search.
Initial views are real reads, not full reading. Report unread scope honestly.
Use fetch/repository/resolve actions for relevant additional resources only.
Return one discovery object combining selection and planning, not two essays.
Each candidate must have:
- name: unique lowercase-hyphen ID across skills/tools.
- kind: skill only. Reusable code belongs in the skill scripts/, never an independent tool.
- task, scope, entrypoint: concrete reusable capability, boundary and real interface.
- rationale: specific usage difficulty and why instructions/adaptation help.
- upstream_behavior and added_behavior: distinguish existing and new; use "none"
  for no new domain behavior. Formatting adapters normally remain direct.
- intent: direct or extension; choose when config says auto, respect explicit limits.
- implementation: upstream, adapter or composition. Multiple tools may serve one
  coherent capability. Broad research task orchestration is not the primary output.
- readiness: callable, adapter_needed or blocked; gaps name missing resources.
- needs: always [] (no shared tool layer).
- dependencies: real external requirements, versions and acquisition locations.
- files: [{path,purpose}]. Skills need SKILL.md; tools only justified scripts/ or
  references/ files. Do not create environment configs or MCP services.
- checks: meaningful verification and expected outcomes from source tests/examples
  or documented rules, never from the new implementation alone.
- evidence: [{id,claim}], actual eN reads supporting the capability and entrypoint.
- selected: boolean; priority: smaller integer first.
Use max_candidates/max_builds as ceilings, never quotas. One library is not always
one skill; neither is every function. Different triggers/I/O/result meaning justify
splitting. Keep necessary scripts local to the skill. Provide a short omitted list
of important exclusions/merges and limitations. Zero candidates is valid.
Do not invent algorithms, scientific thresholds, URLs, availability or Agent gain.
No benchmark question generation. Missing evidence is a gap, not permission to
reconstruct algorithms from formulas.

Return handoff: [{fact,evidence:[read IDs]}] for important interfaces, pitfalls and unresolved scope facts. Facts need actual eN read IDs. Each candidate has method_evidence: [{id,claim}]; extensions must cite the EXISTING research method or implementation, not an idea invented while reading docs. No new scientific behavior. Mechanical glue is permitted with explicit scope. Reuse upstream calls; do not force scripts or output counts.
