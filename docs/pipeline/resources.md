# Source acquisition and sharing

Each group has its own workspace and source IDs. Acquired material is stored in shared snapshots, with group-local registration explaining its use. Shared files retain separate evidence IDs in each group.

## Inputs

A source accepts a local path, HTTPS url, Git repo, paper identifier or table. Put a paper and its associated code in the same resource_group. related_to expresses relationships between that group's inputs.

Directories are snapshotted by default. Single-file reference storage uses the original file and is not offered as an immutable cross-group snapshot; resume requires that original to remain unchanged. Git submodule and LFS payloads are not resolved automatically.

Acquisition excludes credentials, installed environments and caches, including .git, .venv, node_modules, .ssh, .aws, .pipeline and actual .env files. Source size is governed by explicit limits. Unsupported formats retain their originals and parsing diagnostics.

## File locations

```text
STATE/cache/snapshots/               # Immutable shared source snapshots
STATE/cache/resource-index.json      # URL, version and snapshot lookup
STATE/runs/BATCH/groups/GROUP/
  resources.json                    # Group file locations, views and helper commands
  source-evidence.json               # Group-local eN IDs
  resource-state.json                # Restorable source registry
  views/                            # Optional text or page views
```

Local originals remain in place. Snapshots are checked on acquisition, and views never replace originals. Agent-downloaded files must be registered in the group and snapshotted with provenance before other groups reuse them.

## Supplemental research

research_access=supplement permits targeted search and acquisition for concrete gaps. known_only disables open search. network=false restricts both source acquisition and Agent network access. Initial Docker pulls and dependency builds also need suitable network access.

Agents use the helper advertised in resources.json:

| Operation | Purpose |
| --- | --- |
| supplement | Acquire a URL, repo or paper and register its purpose and related inputs |
| register | Register a file already saved by the Agent |
| lookup | Search the shared index by address, version or other recorded identity |
| adopt-resource | Register a shared snapshot for a group-local purpose with local evidence IDs |
| inventory | Query the group's file inventory |

Native-acquired content can be saved under the group's `research/inbox/`. Write content first, then
atomically rename a matching `*.source.json` into place with `path` (relative to the group workspace),
`url`, `reason` and `related_to` original source IDs. Optional `version` and `representation`
(`saved_content` or `excerpt`) describe provenance. Save actual source text and identify excerpt scope.
The program ingests committed sidecars before candidate/delivery validation and at Agent turn
boundaries. `inventory` refreshes immediately. Invalid sidecars return repair feedback; unchanged
repeated errors stop the stage. Multiple original inputs require explicit related-to IDs.

Empty downloads are rejected; legacy empty cache entries are fetched again. Helper failures carry
`error_kind` for transport, empty content, constraints or acquisition subprocess failures. Invalid
requests and local implementation/filesystem errors are reported as helper errors. A failed page
viewer alone does not establish missing evidence; use permitted downloads/local PDF views or
verified original-source alternatives where appropriate.

Registered supplements remain shared immutable snapshots with group-local evidence IDs. Their
content and evidence index are also retained under `STATE/records/BATCH/groups/GROUP/` before
workspace cleanup. Cleanup verifies the retained source inventory and content hashes.

Unavailable sources retain concrete gaps. An evidence ID locates a file; it does not prove the Agent read it or establish a scientific claim.

## Reading and views

| Format | Support |
| --- | --- |
| Code, text, HTML | Direct reading; HTML views retain link addresses |
| PDF | Poppler text extraction and page rendering when installed; pypdf can provide text extraction |
| PNG/JPEG/WebP | Native image tools read the original |
| DOCX | Paragraph text |
| XLSX | First worksheet values |
| Notebook | Markdown and code views; outputs remain in the original JSON |
| SQLite | Schema view |

Install document converters as needed. Layout, charts and embedded figures require the original file or page images; text extraction alone does not provide full visual interpretation.
