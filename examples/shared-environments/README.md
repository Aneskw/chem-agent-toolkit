# Shared tool environment example

Edit input.json to supply your actual GitHub account/repository and image namespace. Authenticate
Codex CLI and Docker to the registry, start the Linux Docker engine, and allow anonymous image access.
Run from the project root:

```bash
python -m creation_pipeline build examples/shared-environments/input.json --preflight
python -m creation_pipeline discover examples/shared-environments/input.json
python -m creation_pipeline resume BUILD_ID --library-dir skills-shared
```

Use a new library directory if an old-format catalog already exists. This input is a small example,
not recorded evidence that a Docker image has been built or published. Full behavior is described in
[the shared creation guide](../../docs/pipeline/shared-creation.md).
