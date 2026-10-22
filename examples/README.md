# Examples

Configurations supply real resources, not desired candidate names or answers. Existing tool environments remain external.

## RDKit source and feedback

```text
python examples/prepare_rdkit_sources.py
python -m creation_pipeline discover .pipeline/example-configs/rdkit-sources.json
python -m creation_pipeline revise --plan <plan.json> --feedback-file feedback.md
python -m creation_pipeline build --plan <revised-plan.json> --execute-generated-checks
```

Example feedback: narrow a broad RECAP hierarchy skill to terminal-fragment retrieval and interpretation of empty results. The actual adopted [terminal-fragment package](../skills/2026-10-22-molecular-fragmentation/rdkit-recap-terminal-fragments/SKILL.md) was generated after such feedback. Its Python block and source-backed result checks passed; this is not an Agent benefit measurement.

```text
python examples/verify_python_example.py skills/2026-10-22-molecular-fragmentation/rdkit-recap-terminal-fragments
```

The helper executes Python blocks. Additional result assertions, environment and scope still matter. It is not a universal semantic validator.

## Research paper and official implementation

`builds/chembl-curation.json` supplies the public ChEMBL structure-curation article and a pinned official commit, including upstream rules/tests. It does not require generating a wrapper or all three components as separate skills.

```text
python -m creation_pipeline discover examples/builds/chembl-curation.json
python -m creation_pipeline build --plan .pipeline/outputs/<id>/plan.json --execute-generated-checks
```

One real run discovered Checker, Standardizer and Parent as separate candidates, selected only Checker under the one-build budget, and adopted the [Checker skill](../skills/2026-10-23-structure-curation/chembl-structure-checker/SKILL.md). Its documented stereo finding and clean empty tuple passed result assertions; the delivered example, review and relocation passed. The run used the pinned source checkout with existing RDKit 2026.03.6; it did not test a fresh package installation. Earlier failed checks were retained, not counted as ready.

To run the adopted example in an environment where its declared prerequisite is already available:

```text
python examples/verify_python_example.py skills/2026-10-23-structure-curation/chembl-structure-checker
```

For a separate installation, select version `chembl_structure_pipeline==1.2.4` explicitly; an unversioned pip command does not pin it. Neither the helper nor the pipeline installs this dependency automatically.

`builds/paper-code.json` retains the Dimorphite-DL version-difference example; its modern tag may require unavailable external dependencies. A generated draft is an honest result. `builds/minimal.json` is a path template to edit, not a ready input on every machine.
