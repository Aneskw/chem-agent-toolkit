# Runtime interfaces

These references are for developers maintaining RuntimeRequest, ToolArtifact and local management interfaces under workflow: legacy-script-images. See [code organization](../pipeline/code-organization.md) for the shared environment state machine.

| Document | Content |
| --- | --- |
| [Delivery protocol](delivery-protocol.md) | Revisions, freezes, catalogs and qualification |
| [Delivery layout](delivery-layout-contract.md) | Required files and exact-path checks |
| [Docker execution](docker-execution.md) | RuntimeRequest, container checks and results |
| [Recovery](runtime-recovery.md) | Interrupted work, revalidation and import |
| [Dependency environments](dependency-environments.md) | Dependency-stage identity, cache and inspection |
| [Tool artifacts](tool-artifacts.md) | Source closure, concrete versions and execution bindings |
| [Scoped contracts](scoped-tool-contracts.md) | Tool compatibility and current business requirements |
| [Bundled JSON](bundled-json-tool-protocol.md) | Fixed file-relative resource access |
| [Sibling JSON](sibling-json-tool-protocol.md) | Fixed with_name resource access |
| [Open Babel](openbabel-external-tool-protocol.md) | External executables and image closure |
| [Local management](local-management-api.md) | Versioned operations, parameters and errors |
| [Reverse references](reverse-references.md) | Read-only dependency queries over explicit scopes |

Machine contracts are in validation/fixtures/contracts/local-management-v1.json and validation/fixtures/contracts/runtime-contract.json. Offline cross-checks are in validation/checks/; see [developer verification](../../validation/README.md).
