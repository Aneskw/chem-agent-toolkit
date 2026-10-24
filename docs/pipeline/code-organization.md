# Code organization

Run commands from the repository root with `python -m creation_pipeline`. The CLI and configuration format are independent of the internal package layout.

```text
creation_pipeline/
  __main__.py                 # Python module entry point
  cli.py                      # Commands, arguments and console results
  pipeline.py                 # Stage orchestration, repair, resume and adoption
  models.py                   # Configuration validation, limits and errors
  schemas.py                  # Concise Agent stage result formats
  records.py                  # Hashes, safe paths, durable JSON and cleanup
  paths.py                    # Stable repository, package and prompt locations
  resources/
    acquisition.py            # Known URLs, repositories, papers and catalogs
    intake.py                 # Source snapshots, inventories and integrity
    documents.py              # Optional document-to-text conversion
    workspace.py              # Original-file locators, views and resource registry
    supplements.py            # Known-resource supplements and inventory queries
  agent/
    command.py                # Locate the installed Codex CLI
    backend.py                # Native sessions, CLI events, recovery and image audit
    tools.py                  # Thin helper CLI; delegates to responsible modules
  generation/
    discovery.py              # Discover, normalize and validate candidate decisions
    candidates.py             # Save incremental source-backed candidates
    context.py                # Assemble small source-backed stage handoffs
    author.py                 # Author/repair coordination and independent review
    prompts/                  # Discovery, author, review and revision instructions
  validation/
    checks.py                 # Static checks, execution dispatch and conclusions
    runtime.py                # Execute explicit checks and assert their results
    agent_checks.py           # Record authorized Agent diagnostics
    example_runner.py         # Execute explicitly selected Python examples
  artifacts/
    delivery.py               # Direct-file validation, chunks and delivery receipts
    package.py                # Manifests, output integrity and explicit installation
    library.py                # Individual adoption, collision handling and catalog

tests/pipeline/
  support.py                  # Deterministic Agent-stage doubles and fixtures
  test_components.py          # Validation, execution and safe-file operations
  test_discovery.py           # Discovery, build, repair and source-locked continuation
  test_native.py              # Native CLI/session lifecycle using a fake executable
  test_research.py            # Research resources, direct files and scoped readiness
  test_skill_library.py       # Review, selected examples, adoption and catalog
  test_sources.py             # Acquisition, document conversion and snapshots
  test_entrypoints.py         # Helpers invoked outside the repository directory

docs/                         # Current usage, configuration and design standards
examples/                     # Reserved for complete reproducible build batches
skills/                       # Reviewed skills and simple batch/catalog organization
.pipeline/                    # Ignored local cache, workspaces and build records
```

`pipeline.py` coordinates stages; it does not implement source downloading, CLI transport or file packaging. The helper router in `agent/tools.py` exposes operations whose implementations live in `resources`, `generation`, `validation` and `artifacts`. Native sessions call these helpers and access retained original files directly.

Only native Codex Agent execution is implemented. Test doubles replace stage decisions and write real fixture files through the delivery receipt code. They are not a production backend. The CLI's own connection to its model, including optional model selection and `http_only`, remains the responsibility of the native Agent integration.

Internal import paths follow this tree. Old internal module paths and helper commands saved in earlier workspaces are not compatibility entry points; start a new build after updating the code. Completed skill packages do not depend on these helper paths.
