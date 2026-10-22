# Usage

See [setup](../../README.md#prepare) and [configuration](configuration.md). Sources are required; prompt is optional.

```text
python -m creation_pipeline discover sources.json --preflight
python -m creation_pipeline discover sources.json
python -m creation_pipeline revise --plan <plan.json> --feedback-file feedback.md
python -m creation_pipeline build --plan <revised-plan.json> --execute-generated-checks
python -m creation_pipeline build sources.json --no-adopt
```

`preflight` validates configuration only. `plan` aliases `discover`. Revision produces a new output with a parent/feedback record; original files are retained. Write feedback in ordinary language to narrow scope, correct a misunderstanding, merge or remove candidates. No task-specific answers are required. Resource evidence remains locked. Source changes must be acquired explicitly; do not edit locked config/source records to bypass validation.

`build` preserves the saved discovery. Unchanged ready candidates may reuse scoped evidence; this is reported, not a new test execution. Drafts and changed candidates rebuild. All skills receive source-aware content review. `--execute-generated-checks` authorizes generated commands, not dependency installation or deployment. Without necessary execution evidence a package stays draft.

```text
python -m creation_pipeline check .pipeline/outputs/<id>
python -m creation_pipeline install .pipeline/outputs/<id> --destination ./exported
python -m creation_pipeline clean <id> --dry-run
python -m creation_pipeline clean <id>
```

`check` verifies manifests/static structure; it does not rerun tests. `install` exports validated content; project adoption occurs separately during build. Cleanup removes registered temporary work only, not source inputs or adopted packages. Use `--keep-debug` for bounded, redacted model diagnostics.

## Troubleshooting

- No readable sources: inspect source errors, paths, format support and network setting.
- Draft: inspect required checks and issues; missing evidence is not fixed by repeatedly rewriting files.
- Failed: inspect per-skill checks and repair history; backend failures stop file repair.
- Adoption conflict: existing content is preserved; review the new output before choosing an identity/version.
- Changed source context: rediscover or use explicit revision rather than changing source lock hashes.

Text extraction is not visual understanding. Search means source-text search, not Internet search. No automatic environment setup or Agent evaluation runs. See [outputs](outputs.md).
