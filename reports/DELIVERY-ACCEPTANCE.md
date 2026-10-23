# Requirement-aware Skill delivery: r3.1

The creation pipeline now decides each candidate's execution requirement from
source-cited contracts and explicit tool bindings. Tool candidates must prepare
an environment, build a Docker image and pass locked execution tests. Confirmed
text-only candidates pass content/source/format checks without Docker. Unknown
requirements, missing bindings and contradictory declarations block delivery.

Main, batch, public, publication and recovery entrypoints use the delivery gate.
Draft generation and archival are recorded separately from accepted delivery.
Recovery validates source/binding hashes and real image identity before reuse.

## Verification

- Final release independently unpacked and checked: 334 manifest files.
- Full regression: 277 tests, 0 failures, 0 errors, 3 native POSIX tests skipped
  on Windows. These mechanism tests are separate from real Docker acceptance.
- Real RDKit Docker build and 8 container tests passed, including descriptor
  computation, invalid-input rejection and file input/output behavior.
- Default text creation, missing-binding rejection and draft-only CLI checks
  passed. Portable revalidation used bundled sources and bindings.
- The example reuses the previously generated source-cited Skill and locked
  plan; final revalidation made no model calls and did not weaken assertions.

Release archive: `chem-agent-toolkit-source-2026.10.23-r3.1.zip`

SHA-256: `9ed3960b1fc6a444a6d4716c802ec4179e941e23ad054d9b131d0003f256c439`

The archive, example ZIP and detailed acceptance evidence are separate release
artifacts in local `deliverables/`, intentionally excluded from Git. Upload them
as release attachments when publishing. This source commit does not itself host
those attachments. The archive is a buildable environment package, not an image
tar; first-time rebuild normally requires network. Scientific correctness and
agent-effectiveness are outside this engineering acceptance.

See [DELIVERY.md](../creation_pipeline/DELIVERY.md) for commands and migration.
