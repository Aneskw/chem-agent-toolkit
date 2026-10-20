# Chem Agent Toolkit — task-focused skill creation

This branch builds one useful tool skill from a concrete task and trustworthy resources. A model writes SKILL.md and any justified supporting files; the program checks interfaces, runs explicitly configured checks, coordinates bounded repair and packages the result. Simple tasks can remain a single file.

Development branch: `pipeline/task-skill-v1`. The prior repository is preserved at commit `6bb535a`; main is unchanged. Historical generated catalogs and the two old implementations are not part of this branch’s active tree.

Start with the [usage guide](docs/pipeline/usage.md), [agreed design](docs/pipeline/design.md) and [acceptance record](docs/pipeline/acceptance.md). The [documentation index](docs/README.md) links the authoritative skill specifications and legacy evidence.

```text
python -m creation_pipeline --help
python -m unittest discover -s tests -v
```

For an installed RDKit environment, `python examples/prepare_rdkit.py` prepares real local source material and build configurations. See the guide before running a live model build.

## Layout

- `creation_pipeline/`: the single build implementation and stage prompts.
- `docs/`: content specifications, design, operation and historical index.
- `tests/pipeline/`: deterministic engineering tests, separate from model efficacy.
- `examples/`: preparation and verification helpers, not prewritten final skills.
- `skills/`: explicitly adopted outputs; builds do not install here automatically.
- `evaluation/`: reserved for later independent Agent benchmarking.
- `.pipeline/`: ignored local sources, cache, staging and outputs.

Build success is scoped engineering evidence. Agent gains and scientific generalization are not established by a generated example or a passing smoke test. No automatic deployment, Git commit or push is performed.
