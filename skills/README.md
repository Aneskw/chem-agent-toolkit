# Integrated skill library

`catalog.json` is the only active index. `accepted/` contains formally qualified current packages; `candidates/` requires explicit selection for inspection, repair or later runtime acceptance.

Use `python -m creation_pipeline library skills` for accepted entries and append `--include-candidates` for candidate inspection. Default installation never accepts candidates. Do not recursively load unregistered or historical directories as Agent skills.

Pre-integration dated directories are historical, unregistered artifacts, retained only for inspection. They have no inherited approval and are not runtime dependencies. All accepted entries must be generated and reviewed by the integrated code.

Frozen packages, sources and records live in `evidence/`; catalog history preserves prior assessments. See [delivery protocol](../docs/pipeline/delivery-protocol.md).
