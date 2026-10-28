# Examples

The [DNA base-counting example](base-count/README.md) supplies fresh source code, fixed expectations and the observed runtime recovery after a planner timeout. The [dilution experiment](dilution/README.md) records failed automatic attempts followed by an explicit, independently reviewed contract correction. See the stage-five report for results and limits; neither demonstrates a fully autonomous repair loop.

Each batch should show the input resources, important intermediate decisions/checks, and the complete resulting skill packages. Keep related files together:

```text
examples/
  <batch-name>/
    README.md                 # purpose, prerequisites, commands and verified scope
    input.json                # runnable pipeline configuration
    resources/                # small permitted fixtures or pinned acquisition instructions
    records/                  # selected discovery, summary, review and check records
    skills/
      <skill-name>/
        SKILL.md
        ...                   # all necessary supporting files
```

The batch README should explain:

- Which capabilities were found and why they were packaged.
- Where resources came from, including versions/commits and how to obtain them again.
- Required software/resources and the exact preparation and build commands.
- How the important records relate to the generated files.
- Which checks actually ran, what remained unverified, and what a reproduction can reasonably reproduce.

Include redistributable inputs or acquisition steps rather than full upstream trees, large datasets or weights. Keep useful provenance and checks; omit caches, credentials, redundant logs and machine-specific temporary paths. Original run details can remain local under .pipeline.

Resource versions can be pinned, but another model run need not produce byte-identical skills. Distinguish rerunning the workflow from reproducing an actual tool result. Use the project's [usage](../docs/pipeline/usage.md) and [configuration](../docs/pipeline/configuration.md) guides with each example's recorded scope.
