# Code organization

Run commands from the repository root with `python -m creation_pipeline`. The CLI and configuration format are independent of the internal package layout.

```text
creation_pipeline/
  __main__.py                 # Python module entry point
  cli.py                      # Commands, arguments and console results
  pipeline.py                 # Stage orchestration, repair, resume and adoption
  groups.py                   # Serial resource groups and flat child-build recovery
  models.py                   # Configuration validation, limits and errors
  schemas.py                  # Concise Agent stage result formats
  records.py                  # Hashes, safe paths, durable JSON and shared OS leases
  retention.py                # Compact archive, active locks, pinning and expiration
  paths.py                    # Stable repository, package and prompt locations
  resources/
    acquisition.py            # Known URLs, repositories, papers and catalogs
    intake.py                 # Source snapshots, inventories and integrity
    documents.py              # Optional document-to-text conversion
    workspace.py              # Original-file locators, views and resource registry
    supplements.py            # Known supplements, native-material registration and inventory
    policy.py                 # Scoped research instructions and native search mode
  agent/
    metrics.py                # Session-aware usage aggregation
    command.py                # Locate CLI and terminate interrupted process trees
    backend.py                # Native sessions, CLI events, recovery and image audit
    tools.py                  # Thin helper CLI; delegates to responsible modules
  generation/
    discovery.py              # Explore, consolidate, reconcile and validate candidate sets
    candidates.py             # Save incremental source-backed candidates
    context.py                # Assemble small source-backed stage handoffs
    author.py                 # Author/repair coordination and independent review
    prompts/                  # Discovery, author and independent review instructions
  validation/
    checks.py                 # Package checks, script syntax and advisory Markdown Python parsing
    basis.py                  # Shared source locator and writing-basis validation
    acceptance.py             # Content approval bound to files and basis
  artifacts/
    delivery.py               # Direct-file validation, chunks and delivery receipts
    package.py                # Manifests, output integrity and explicit installation
    library.py                # Flat adoption, active name registry and library navigation

tests/pipeline/
  support.py                  # Deterministic Agent-stage doubles and fixtures
  test_components.py          # Validation and safe-file operations
  test_discovery.py           # Build, no-candidate decisions, failures and preflight gating
  test_consolidation.py       # Candidate coverage, scope handoffs and discovery recovery
  test_groups.py              # Serial dispatch, group isolation, budgets and queue recovery
  test_native.py              # Native CLI/session lifecycle using a fake executable
  test_research.py            # Research resources, direct files and scoped readiness
  test_skill_library.py       # Pure flat adoption, archive installation and conflicts
  test_sources.py             # Acquisition, document conversion and snapshots
  test_entrypoints.py         # Helpers invoked outside the repository directory
  test_review_workflow.py     # Independent content review and correct feedback routing
  test_inline_python.py       # Read-only fence parsing, locations and language boundaries
  test_research_access.py     # Policy, native CLI wiring and adopted-source registry
  test_retention.py           # Expiry, pinning, active locks, safe archives and usage
  test_source_handoff.py      # Acquisition failures, native fallback and evidence handoff
  test_examples.py            # Portable inputs, preflight and example evidence links

AGENTS.md                     # Repository content and contribution conventions
docs/                         # Current usage, configuration and design standards
examples/                     # Workflow walkthroughs, selected stage records and portable inputs
skills/                       # Formal packages and indexed task collections
.pipeline/                    # Ignored local cache, workspaces and build records
```

`pipeline.py` coordinates stages; it does not implement source downloading, CLI transport or file packaging. The helper router in `agent/tools.py` exposes operations whose implementations live in `resources`, `generation`, `validation` and `artifacts`. Native sessions call these helpers and access retained original files directly.

Only native Codex Agent execution is implemented. Test doubles replace stage decisions and write real fixture files through the delivery receipt code. They are not a production backend. The CLI's own connection to its model, including optional model selection and `http_only`, remains the responsibility of the native Agent integration.

Completed skill packages are independent of pipeline helper paths. Recovery checkpoints require unchanged content specifications; compact records preserve drafts for reuse when a full session cannot be resumed.

Plans, audit reports, routine trial histories and one-off maintenance scripts are working materials kept outside the checkout. Curated examples retain selected process records that explain the workflow, with recorded-run context and limitations. The ignored `.pipeline/` directory contains managed execution state, not public documentation; `--state-dir` can place that state elsewhere.

JSON publication uses unique same-directory staging files and atomic replacement, with bounded
retry for Windows sharing/access failures. Persistent errors propagate without replacing the old
document. Logical read-modify-write transactions still need their existing leases.
