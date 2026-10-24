# Configuration

JSON or YAML object. Only sources is required; YAML needs PyYAML. Unknown top-level fields are rejected. Paths resolve relative to the configuration file. Parser/defaults: creation_pipeline/models.py.

| Field | Default | Meaning |
| --- | --- | --- |
| sources | required nonempty array | Local files/directories, known URLs/repos/paper identifiers/catalogs |
| prompt / notes | empty strings | Optional guidance; task is a legacy prompt alias |
| constraints | {} | Model-interpreted preferences, not executable enforcement rules |
| model | {} | Optional name passed to Codex CLI; a model-name string is also accepted |
| execution | {profile: production} | production or development |
| limits | see below | Optional execution/resource overrides |
| network | true | Enable known-address acquisition, including supplements; not search |
| execute_generated_checks | false | Permit generated checks; CLI flag can enable it |
| environment | {allow: []} | Runtime environment variable names to pass, never secret values |
| batch | {label: skills, tags: []} | Readable batch label and simple tags |
| adoption | {enabled: true} | Adopt eligible individual skills |
| http_only | false | Codex built-in-provider transport override |
| checks | [] | User-defined check objects, each with candidate name |
| intent | auto | Legacy guidance direct/extension/auto; explain behavior in construction |

Direct model API/Ollama execution is not implemented. API settings such as base_url/api_key_env/structured are rejected before resource fetching. Existing model.backend=codex_cli configurations remain accepted; no other backend is supported. The underlying Codex connection to its model is unaffected. User model selection and Windows sandbox configuration are retained; arbitrary CLI profiles/plugins are not inherited.

## Sources

Each source has exactly one of path, url, repo, paper, table. Optional id (simple unique identifier), ref, sha256, license and storage are accepted.

- path: local file or directory. ref requires a clean local repository at that revision.
- url: a known HTTPS resource, preserving unknown/binary types. HTML is retained rather than replaced by a guessed PDF link.
- repo: known HTTPS Git repository; resolved version recorded. Archive acquisition streams to disk; no checkout hook or installation is run.
- paper: DOI/arXiv identifier, resolved to a public full text when available; no title search.
- table: CSV/TSV/XLSX resource catalog with pdf/url/doi/repository/github/path columns. For ordinary data use path.
- storage: copy (default) or reference. Reference applies to individual files, avoids a duplicate copy and checks source hashes; directories use filtered snapshots.
- sha256: optional expected single-file digest; license is provenance metadata, not a legal assessment.

Unknown file extensions are retained; parsing support is separate. No implicit input size/count cap. Optional development limits can deliberately narrow a trial; limitations/exclusions are recorded. See [resources](resources.md).

## Execution profiles and limits

Production defaults to null (disabled) for model_calls, candidate_calls, model_timeout, total_seconds, discovery_seconds, agent_events, max_candidates, max_builds, source_bytes, source_total_bytes, source_files, package_bytes, network_requests and repair_rounds.

Development defaults: model_calls=8, max_candidates=3, max_builds=1, repair_rounds=2. It does not impose a model time limit. All defaults can be explicitly overridden; null disables a limit. repair_rounds may also be zero. Quality standards do not change between profiles.

```json
{
  "sources": [{"path": "./research-code"}],
  "execution": {"profile": "development"},
  "limits": {"model_calls": 6, "max_candidates": 2, "max_builds": 1}
}
```

network_timeout=60 seconds, converter_timeout=60 seconds and check_timeout=120 seconds are per-operation fault controls, not whole-build deadlines. converter_timeout/check_timeout may be null for a deliberately long check. Agent resources are original files and optional prepared views; no host read-request protocol or text-context pagination is used.

model_calls counts CLI turns, not internal inference requests. Missing usage is unknown, not zero. No automatic monetary-cost estimate. Optional agent_events counts CLI-reported tool completions; the CLI does not report every native tool there.

## Check definitions

name, argv (string array, no shell), cwd ('{run}' by convention), expected_exit (0), stdout_contains ([]), optional json_equals/artifacts, kind, and generated-check evidence/purpose. At least one result assertion is required. Check names must not collide with host validation names.

Macros: {python}, {package}, {run}, {source:ID}, only in check definitions, never runtime skill text. Execute the actual delivered script or explicitly selected example path. No blanket execution of all Python blocks. A mock or syntax check does not establish a real tool run. Configured assertions cannot be silently weakened.
