# Outputs and delivery packages

Keep only files needed to use, reproduce, recover or substantiate a result. Do not generate empty
support directories, per-Skill construction reports or duplicate manifests. runtime.json describes
the Skill's requirements, rather than every dependency or external model associated with its image.

Routine successful Agent turns retain structured results and receipts; full prompts, schemas and
transcripts are discarded unless `--keep-debug` is selected. Failures retain diagnostic evidence.
Large failure output is saved once and referenced from repair feedback. Active checkpoints support
resume; final archives omit duplicate checkpoints and installed build contexts. Binary test assets
use shared snapshots rather than a separate copy in every group's archive.

Local approvals and caches can be reconstructed through fresh checks. Removing run checkpoints
loses exact continuation, and removing review/execution evidence loses those historical facts.
Reindexing existing packages recovers their locations and hashes, not their qualification.

These paths correspond to `--state-dir .pipeline/shared --library-dir skills-shared`:

```text
skills-shared/
  verified/NAME/
    SKILL.md
    runtime.json
    scripts/                         # As needed
    references/                      # As needed
  pending-validation/NAME/
tools/
  catalog.json                       # Reusable environment index
  rdkit/v1/environment.json
  rdkit/v1/context/Dockerfile
  rdkit/v1/context/...                # Other build inputs
.pipeline/shared/
  runs/BUILD_ID/groups/GROUP/         # Recoverable workspaces
  outputs/BUILD_ID/summary.json
  records/BUILD_ID/                   # Review, build, execution and archive evidence
  cache/                             # Source snapshots and shared index
.pipeline/skill-libraries/LIBRARY_ID/
  catalog.json                       # Internal delivery index bound to its output directory
  leases/                            # Library read/write locks
  staging/                           # Copies being checked before export
  promotion.json                     # Manual verification record, when applicable
.pipeline/tool-libraries/LIBRARY_ID/
  versions.json                      # Local version allocation
  prepared-plans.json                # Source-bound environment investigation cache
  leases/                            # Environment library locks
  observations/                      # Host command receipts
  records/                           # Local image identities and publication checks
```

## Skill packages

SKILL.md describes the capability, inputs, outputs, representative usage and result handling. Its runtime section appears once. The host generates runtime.json with requirements for using the image or preparing a compatible local environment. Example:

```json
{
  "image": "ghcr.io/your-account/chem-tools:rdkit-v1",
  "platform": "linux/amd64",
  "environment": {
    "tools": [
      {"name": "Python", "version": "3.11.11", "kind": "runtime"},
      {"name": "RDKit", "version": "2024.9.6", "kind": "python"}
    ]
  }
}
```

Actual image references and versions come from investigation and the checked build. environment.conditions can express established memory or task-network requirements. resources and usage notes appear when needed. Empty arrays and unused defaults are omitted.

verified meets every delivery gate. pending-validation retains necessary code awaiting concrete validation. Exempting an ordinary API example does not itself put a Skill in the pending class.

Each package is independently usable with its referenced image or a compatible local environment. Required scripts, reference documents and runtime assets stay in the package. Local catalog entries, source snapshots, review findings and build logs stay outside it. Query and install commands take the delivery directory and locate its private index automatically.

## Internal records

tools stores the environment index, version metadata and complete build inputs. Docker and GHCR store image data. Environment counters, investigation caches, locks and host command receipts live under .pipeline/tool-libraries/, keyed by the tool library's absolute path. The program relocates existing control files there automatically. records holds source claims, reviews, execution decisions, results and final file manifests. None of these process records is installed inside a Skill package.

Each tools/catalog.json entry contains only id, version and path. The referenced environment.json contains tool versions and check commands, image and base references, build-file checksums, and applicable resource or platform requirements. A shared probe prefix is followed by each tool's name and version; a tool can override it with its own complete probe command. Empty resources and unused conditions are omitted.

Build identities and publication observations stay in private records, bound to the exact portable metadata. A fresh checkout can use the build materials and image references but must perform its own checks before delivery.

New definitions can use `@python-version` or `@python-import MODULE` probes. The pipeline mounts
its common checker read-only and uses the image's interpreter; check-only changes require fresh
checks, not new image layers. Explicit tool-specific probe commands remain supported.

summary.json and console output identify the build_id, batch state and candidate outcomes. Blocked candidates record their reason and resume_when. archive_error, adoption_error and publication_error indicate incomplete delivery that must be resolved before export.

Local-only local-verified/local-pending-validation results remain in run records and are not exported as qualified packages.
