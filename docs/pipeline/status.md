# Current status

Integration update: the active workflow combines the partner pipeline with local
Docker planning/build/business acceptance, current qualification and durable recovery.
See [stage-five results](../integration/stage-five.md), [delivery protocol](delivery-protocol.md),
[execution](docker-execution.md), and [recovery](runtime-recovery.md). Unexecuted required
tool content is not ready/accepted. Remote GPU, external mounts and credentials remain
unsupported. The description below is **historical partner-baseline evidence**, including
its old readiness semantics and limitations; it is not the current feature matrix.

Version 5.0.0. Verification date: 2026-10-24. This is a scoped capability summary, not a live dashboard.

| Capability | Evidence |
| --- | --- |
| Agent-only execution, production/development settings | Configuration and public-entry tests; API/Ollama rejected before acquisition |
| No default source byte/count/extension cutoff | Real pinned EDBO export: 411 files, 55,361,999 bytes, plus 4,945,308-byte PDF; large/unknown/hidden-file regression tests |
| Known-address supplements and cache | Real EDBO documentation fetch followed by cached reuse; registry/recovery tests |
| Concise candidates and automatic continuation | Real two-candidate discovery; one built and one explicitly deferred by development setting |
| Durable direct files and multi-file package | Real SKILL.md plus references/source-notes.md; receipt/final-response recovery and binary-asset tests |
| Native source/content review | Separate Agent session inspected EDBO implementation, examples and paper; content passed, runtime explicitly unverified |
| Checks, scoped readiness and library integrity | Deterministic tests for permission, real-example selection, faults, unverified catalog entries, collision and recovery |

102 engineering tests passed: `python -m unittest discover -s tests -q`. Tests using fake CLI responses validate mechanics, not model quality. `git diff --check` passed. The current code uses responsibility-based subpackages and only native Agent execution; direct API/Ollama and the old host-mediated text request loop have been removed. No new model-quality trial was run for this structural cleanup. Old example materials were removed; examples is reserved for complete build batches. Existing formal skills remain unchanged.

The real local trial used authenticated Codex CLI requesting gpt-6.1-sol, 3 CLI turns and no model time limit. It completed acquisition, discovery, two-file delivery, content review and output verification. The code environment was not installed; EDBO numerical optimization/CSV execution was not performed. ready here means scoped applicable review passed without known blocking defects. It does not mean all tools ran or a scientific result was reproduced. Trial adoption was disabled and no public example was added.

The trial also exposed premature drafting in discovery; the prompt now explicitly stops at candidates and helper finalization is restricted to author phase. This correction has regression coverage; another expensive end-to-end model trial was not run just to remeasure it. Existing image/page capabilities remain; comprehensive DOCX charts/notebook-output vision is not implemented.

Known limits: no autonomous search, servers/Docker/environment provisioning, shared tools/MCP, semantic classification/merging or Agent benefit evaluation. Repository archives are materialized, not a lazy remote weight/data store. Source preparation/format handlers still have real disk/memory and tool-availability constraints. Recovery is stage-level, not crash-proof or concurrent. Execution permission includes Agent instructions and a workspace sandbox, not a host filter on every native command. No controlled cost saving is claimed; reported CLI usage is retained without a billing estimate.
