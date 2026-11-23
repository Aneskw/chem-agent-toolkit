# Operations

Run commands from the repository root. Use the original state-dir and the intended delivery library-dir.

## Discovery, build and resume

```bash
python -m creation_pipeline discover input.json --state-dir .pipeline/shared
python -m creation_pipeline resume BUILD_ID --state-dir .pipeline/shared --library-dir skills-shared
python -m creation_pipeline build input.json --state-dir .pipeline/shared --library-dir skills-shared
```

discover saves candidates; resume continues their saved stages. build runs the full workflow. Groups and candidates run serially. One blocked candidate does not stop the others. Do not concurrently resume one BUILD_ID.

After resolving external conditions, resume without rediscovering. Changes to Skill specifications require a new batch. Do not edit checkpoints to inherit approval.

If publication fails, resolve the recorded cause and resume that stage. A private Package needs public visibility; a registry transport failure needs connection recovery. Successful authoring and code checks are retained. An undelivered candidate can explicitly change publishing target:

```bash
python -m creation_pipeline resume BUILD_ID --state-dir .pipeline/shared --library-dir skills-shared --image-repository ghcr.io/your-account/chem-tools
```

The program records the target change. Delivered packages retain their original bindings.

## Query and install

```bash
python -m creation_pipeline library skills-shared
python -m creation_pipeline library skills-shared --include-candidates
python -m creation_pipeline install skills-shared --name SKILL_NAME --destination installed
python -m creation_pipeline install skills-shared --name SKILL_NAME --include-pending --destination installed
```

Queries and installation select verified packages by default. Installation copies the pure package and checks catalog file identities. Existing destinations are not overwritten.

If the private Skill catalog was lost, recover package locations without claiming prior validation:

```bash
python -m creation_pipeline library-reindex skills-shared
python -m creation_pipeline library skills-shared --include-candidates
```

Recovered entries have unavailable qualification and are excluded from default verified queries.
They require review/revalidation before qualification; directory names do not establish approval.
Reindex refuses to replace an existing catalog. It does not change package contents or move files.

## Manual validation

Validate every necessary pending item and supply a report bound to the current package and image:

```json
{
  "image": "ghcr.io/your-account/chem-tools:rdkit-v1",
  "package_sha256": "<fingerprint of this catalog entry's files>",
  "items": [
    {"item_id": "<pending item ID>", "status": "passed", "evidence": "<actual run record or result location>"}
  ]
}
```

Compute the package fingerprint with `creation_pipeline.shared.environment.fingerprint(entry['files'])`, where entry is the Skill's catalog item. The report must cover all pending items.

```bash
python -m creation_pipeline promote skills-shared SKILL_NAME --report manual-report.json
```

promote validates the report and updates the library without running tools. A different package or image binding is rejected.

## Retention and cleanup

```bash
python -m creation_pipeline pin BUILD_ID --state-dir .pipeline/shared
python -m creation_pipeline unpin BUILD_ID --state-dir .pipeline/shared
python -m creation_pipeline clean BUILD_ID --state-dir .pipeline/shared --dry-run
python -m creation_pipeline prune --state-dir .pipeline/shared --older-than-days 7 --dry-run
```

Inspect dry-run output before removing that option. Cleanup requires a complete archive and all candidates verified. Pins, active locks, pending validation, blocked candidates and local-only results prevent removal. Shared sources, environment materials, images and durable records are outside these commands' cleanup scope.
