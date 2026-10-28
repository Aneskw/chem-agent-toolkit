# Code organization

Run commands from the repository root with `python -m creation_pipeline`. The CLI and configuration format are independent of the internal package layout.

```text
creation_pipeline/
  __main__.py                 # Python module entry point
  cli.py                      # Commands, arguments and console results
  pipeline.py                 # Stage orchestration, repair, resume and adoption
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
    discovery.py              # Discover, normalize and validate candidate decisions
    candidates.py             # Save incremental source-backed candidates
    context.py                # Assemble small source-backed stage handoffs
    author.py                 # Author/repair coordination and independent review
    prompts/                  # Discovery, author and independent review instructions
  validation/
    checks.py                 # Static package, references and script syntax checks
    basis.py                  # Shared source locator and writing-basis validation
    acceptance.py             # Content approval bound to files and basis
  artifacts/
    delivery.py               # Direct-file validation, chunks and delivery receipts
    package.py                # Manifests, output integrity and explicit installation
    library.py                # Individual flat adoption and catalog

tests/pipeline/
  support.py                  # Deterministic Agent-stage doubles and fixtures
  test_components.py          # Validation and safe-file operations
  test_discovery.py           # Build, no-candidate decisions, failures and preflight gating
  test_native.py              # Native CLI/session lifecycle using a fake executable
  test_research.py            # Research resources, direct files and scoped readiness
  test_skill_library.py       # Pure flat adoption, archive installation and conflicts
  test_sources.py             # Acquisition, document conversion and snapshots
  test_entrypoints.py         # Helpers invoked outside the repository directory
  test_review_workflow.py     # Independent content review and correct feedback routing
  test_research_access.py     # Policy, native CLI wiring and adopted-source registry
  test_retention.py           # Expiry, pinning, active locks, safe archives and usage
  test_examples.py            # Portable example records and authoritative package integrity

docs/                         # Current usage, configuration and design standards
examples/                     # Reserved for complete reproducible build batches
skills/                       # Ready skills directly under their names
.pipeline/                    # Ignored local cache, workspaces and build records
```

`pipeline.py` coordinates stages; it does not implement source downloading, CLI transport or file packaging. The helper router in `agent/tools.py` exposes operations whose implementations live in `resources`, `generation`, `validation` and `artifacts`. Native sessions call these helpers and access retained original files directly.

Only native Codex Agent execution is implemented. Test doubles replace stage decisions and write real fixture files through the delivery receipt code. They are not a production backend. The CLI's own connection to its model, including optional model selection and `http_only`, remains the responsibility of the native Agent integration.

Completed skill packages are independent of pipeline helper paths. Recovery checkpoints require unchanged content specifications; compact records preserve drafts for reuse when a full session cannot be resumed.
