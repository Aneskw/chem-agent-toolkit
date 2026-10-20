# Legacy baseline

The previous repository state is commit `6bb535a`. Development occurs on
`pipeline/task-skill-v1`, never by modifying `main`.

The two former creation pipelines, generated skill catalogs and old evaluation
runners have been removed from this branch's active tree. They remain available
in Git at that commit. No scientific tool or historical source was rewritten.
The local migration also retains an ignored `.pipeline/legacy-6bb535a/` backup;
it is not a new pipeline dependency or a normal build output, and is not pushed.

Historical evidence worth consulting:

- [Negative pilot summary](negative-pilot.md).
- `evaluation/method_decisions/` at the baseline: frozen tasks, raw results and rubric.
- `evaluation/benchmark_skill_pilot/` at the baseline: an easy benchmark with a ceiling.
- `creation_pipeline/` and `creation_pipeline_resource_v2/` at the baseline: the old
  schemas, fixed renderer, acquisition and resource restoration implementations.

To inspect history use `git show 6bb535a:<path>`, or create a separate checkout.
Do not restore a second full active pipeline alongside the new implementation.
