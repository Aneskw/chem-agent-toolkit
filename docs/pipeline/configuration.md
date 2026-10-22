# Configuration reference

JSON or YAML object; only `sources` is required. Unknown top-level fields are rejected. The authoritative parser/defaults are `creation_pipeline/models.py`. YAML requires PyYAML. Relative source paths resolve from the configuration file.

```json
{"sources": [{"id": "tool", "path": "./tool"}], "prompt": "Prioritize inference; exclude training.", "batch": {"label": "inference", "tags": ["inference"]}, "adoption": {"enabled": true}}
```

Equivalent YAML (save as `sources.yaml`):

```yaml
sources:
  - id: tool
    path: ./tool
prompt: Prioritize inference; exclude training.
batch:
  label: inference
  tags: [inference]
adoption:
  enabled: true
```

For a paper plus pinned code, see the [ChEMBL configuration](../../examples/builds/chembl-curation.json).

| Field | Type / default | Meaning |
| --- | --- | --- |
| sources | nonempty array, required | Each item has one of path/url/repo/paper/table |
| prompt | string, empty | Optional model guidance |
| task | string, optional | Legacy alias when prompt absent |
| notes | string, empty | Supplementary user guidance |
| constraints | object, empty | Model-interpreted preferences; not arbitrary executable rules |
| intent | auto / direct / extension; auto | Extension must describe a source-existing research method |
| model | object, codex_cli | Backend settings below |
| limits | object | Positive integer budgets below; repair_rounds may be zero |
| checks | array, empty | User-defined execution assertions, each names its candidate |
| environment | object, allow=[] | Allowed runtime environment-variable names, never secret values |
| network | boolean, true | Known-address acquisition and identifier resolution |
| http_only | boolean, false | Codex transport override for supported default provider setup |
| execute_generated_checks | boolean, false | Permission to run generated checks |
| batch | object | label='skills', tags=[]; readable ASCII label and text tags |
| adoption | object | enabled=true; automatically adopt individual ready skills |

## Sources

Each item accepts id, path, url, repo, paper, table, ref, sha256, license. Exactly one location field is allowed. id defaults to source1, source2, etc.; unique simple identifiers only. license is retained metadata, not an automated legal assessment.

- path: local file/directory. ref on a local repository requires a clean checkout already at that ref.
- url: direct HTTPS document, limited PDF-link following.
- repo: HTTPS Git URL; ref optionally pins a branch/tag/commit, resolved commit recorded.
- paper: `doi:...` or `arxiv:...`; public resolution can fail.
- table: CSV/TSV/XLSX catalog, not arbitrary spreadsheet analysis. Recognized columns: pdf/url/doi/repository/github/path.
- sha256: optional expected hash for a single file.

Text/code, textual PDFs, DOCX text, HTML/XML, notebook source cells and SQLite schema are supported. Repository exports are selected source evidence, not installations. Excluded files and limits can prevent complete coverage. No OCR or visual input.

## Models

The object accepts only backend, name, base_url, api_key_env and structured. backend: codex_cli (default), chat_completions, ollama. name is optional for CLI (uses CLI configuration), required for API/Ollama. base_url selects the endpoint; remote endpoints require HTTPS. api_key_env names a credential environment variable. structured defaults true for compatible API strict schema; false requests JSON mode. No automatic backend fallback or model download.

Models receive guidance, constraints, source views and stage artifacts, not the raw configuration or credential values. Budgets and execution permissions are enforced by the host.

## Limits

| Key | Default |
| --- | --- |
| model_calls / candidate_calls | 40 / 10 |
| repair_rounds | 2 |
| model_timeout / check_timeout / total_seconds | 300 / 60 / 1800 |
| source_bytes / source_total_bytes | 2000000 / 30000000 |
| source_files / read_lines / view_chars | 1500 / 160 / 12000 |
| package_bytes | 1000000 |
| context_chars | 160000 |
| network_requests / network_timeout | 12 / 60 |
| max_candidates / max_builds | 8 / 4 |

Counts are ceilings, not quotas. Request/response history contributes to model calls and context.

## Checks

A check has name, candidate (configured checks), argv (string array), expected_exit (0), cwd ('{run}'), stdout_contains ([]), optional json_equals or artifacts, and kind. Generated checks also cite actual evidence and purpose. At least one output assertion is required.

Macros: `{python}`, `{package}`, `{run}`, `{source:ID}`. These are check-only, never runtime documentation. Set cwd to a source directory only when upstream requires adjacent files. Logs remain in the run workspace. Every primary Python block needs execution coverage. If the submitted checks do not execute the delivered statements, the host runs the actual blocks separately when generated execution is permitted, using the first check's cwd. Its completion marker proves execution only; separate meaningful, source-grounded result assertions are still required.

An unknown field such as `my_task` is rejected; put free text in prompt/notes. A valid configuration does not establish source availability or semantic compliance with preferences.
