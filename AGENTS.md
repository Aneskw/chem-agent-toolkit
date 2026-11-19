# Repository conventions

## Content boundaries

Use English throughout the repository. Keep reusable code, current documentation, meaningful tests,
curated workflow examples and formal skill packages here.

Store plans, routine run reports, audits, trial outputs and one-off scripts outside the checkout,
normally in the sibling `chemical_skill/` workspace. Use `--state-dir` for external pipeline state;
do not manually move files still referenced by retained builds.

## Documentation and examples

When pipeline behavior, configuration, interfaces or outputs change, update affected documentation
and runnable examples in the same change. Replace or remove obsolete instructions.

Publish example records manually after maintainers select suitable runs; routine builds leave them
unchanged. Retain the stage evidence needed to explain the workflow, label its context and limitations,
and distinguish it from current rerun instructions. Preserve recorded facts when updating those
instructions. See the [example guide](examples/README.md) for layout and reading order.

## Skill library

Keep skill packages focused on task instructions and required supporting files. Keep indexes focused
on available capabilities and locations, with formal packages linked rather than duplicated in examples.
Preserve necessary source attribution and licenses; keep build and review histories in working records.

## Verification

Check affected links, paths and tests when reorganizing files. For pipeline code changes, run
`python -m unittest discover -s tests -q`. For configuration-only validation, use `--preflight`
without starting a model run.
