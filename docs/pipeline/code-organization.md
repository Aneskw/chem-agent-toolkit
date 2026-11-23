# Code organization and state invariants

## Entry points and modules

```text
creation_pipeline/
  cli.py                        # Commands, arguments and console output
  pipeline.py                   # Workflow dispatch
  models.py                     # Basic configuration validation and budgets
  records.py                    # File identity, atomic records, locks and safe paths
  shared/
    config.py                   # Resource groups and environment settings
    pipeline.py                 # Group scheduling, candidate state, archives and resume
    preflight.py                # CLI, Docker, registry login and model permission checks
    investigation.py            # Source-bound preparation cache
    environment.py              # Matching, builds, probes, versions and publication
    registry.py                 # GHCR identity checks and anonymous HTTP observations
    contracts.py                # Internal environment contract and consumer JSON projection
    verification.py             # Code inventory, test plans, cache and container execution
    delivery.py                 # Final substitution, file checks, library, install and promotion
    library.py                  # Private library indexes, locks and migration of old output state
    environment_state.py        # Private environment counters, preparation caches and lock migration
    environment_metadata.py     # Portable descriptions, compact indexes and private evidence binding
    resources.py                # Cross-group snapshot lookup and registration
    assets.py                   # Registered binary verification inputs and archive members
    runtime_probe.py            # Read-only common checks run with the image's Python
    observations.py             # Compact diagnostics and operation events
    retention.py                # Pins and explicit cleanup
  generation/
    discovery.py                # Candidate discovery and validation
    content_author.py           # Direct authoring and independent content review
    prompts/                    # Agent instructions
  resources/                    # Acquisition, snapshots, views and supplemental sources
  agent/                        # Native CLI sessions, helper routing and usage observations
  artifacts/                    # Package manifests, file delivery and runtime artifacts
  runtime/                      # Process management and RuntimeRequest execution interfaces
```

shared-environments uses the shared state machine. legacy-script-images uses pipeline.build_legacy and RuntimeRequest interfaces. Their accepted/candidates libraries are separate from verified/pending-validation libraries. See [runtime interfaces](../runtime/README.md).

## Stages and repair ownership

environment → author → review → build → prepare-tests → audit-tests (when needed) → execute → publish → finalize → done.

Environment contract errors return to investigation; code inventory errors return to review; fixture and test-plan errors return to execution preparation. Inconsistent source, package or frozen-file identities block progress. Execution failures can be diagnosed for ownership; content repairs require an original-code location and supporting evidence.

author_revision identifies repair rounds. Interrupted work can resume a consistent receipt within a round; a new round cannot retrieve rejected output merely because feedback is unchanged. Unchanged output is reported to the next repair decision without adding a default universal retry cap.

## Environment identity and publication

contracts.CONTRACT_VERSION identifies internal contracts. Compatibility uses installed tool identity, fixed versions, platform, bundled resources and accelerator requirements. External assets do not distinguish image identity. Skill-specific tool/resource selections determine runtime.json; memory and task-network conditions describe use requirements. Build identity includes the pinned base, context files, installed tools, bundled resources and source label.

An investigation is prepared. A successfully probed image is built and may have no remote reference. A confirmed upload is published, with anonymous_access recorded separately. Uploaded state is persisted before public-access checks so a private Package can resume without repeating upload or business computation.

Version allocation holds a local lock and checks remote tags. Materials are frozen under id/version/context; environment metadata retains image digests while Skill instructions use version tags. Publication and export check tag identity and anonymous access. Multi-machine publishers require coordination beyond the local lock.

Tool environment indexes and complete build contexts stay under tools/. Counters, investigation caches, locks and host command receipts live under .pipeline/tool-libraries/, keyed by the canonical tool-library path. Legacy control files migrate under both lock locations; conflicting copies are retained for inspection.

The environment index contains only id, version and path. Portable version descriptions omit process state and factor repeated probe prefixes. Private checks and local image identities are bound to a hash of that description; missing or changed metadata cannot inherit anonymous-access approval. The reader accepts full legacy catalog entries, and compaction writes the compact index only after all version descriptions are stored.

## Execution and delivery evidence

reviewed_files binds semantic approval to package bytes. Execution items bind original file ranges and code hashes. Complex wrappers require independent audit; direct calls must use the actual entry. Cached evidence binds image content, code, supporting files and the exact test plan.

After publication, only {{image}} substitution and runtime.json projection are allowed. final_files controls archive, export and resume checks; changed work packages cannot inherit approval. Archive, publication and adoption errors remain separate from completed computation.

Delivery indexes, catalog locks, staging and manual-verification records live under `.pipeline/skill-libraries/`, keyed by the canonical delivery-directory path. Packages contain only consumer files. Existing shared catalogs are migrated under both old and new locks after checking package manifests; interrupted staging is retained internally. Keep the delivery directory on the same filesystem as `.pipeline` so the checked staging copy can be renamed atomically. A failed copy or cross-filesystem rename cannot commit a catalog entry or inherit delivery approval.

## Maintenance checks

```bash
python -m unittest tests.pipeline.test_shared_creation tests.pipeline.test_shared_revision tests.pipeline.test_shared_next tests.pipeline.test_environment_state tests.pipeline.test_environment_metadata tests.pipeline.test_research_access tests.pipeline.test_onboarding
python validation/checks/run_offline_suite.py
```

Install requirements.txt before running the suite. Some RuntimeRequest file operations on Windows still require a short temporary root. Offline doubles verify control logic; publication and Skill content quality need separate live small-batch validation.
