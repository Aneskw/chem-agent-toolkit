# Fresh DNA base-counting source

The input consists only of original release 1.0 source, documentation and a sequence
fixture. It contains no Skill, Docker plan or previous passing result. Expected
integer counts and invalid-input behavior were fixed before model generation.
This is literal character counting, not biological or scientific validation.

With existing Python 3.11+, jsonschema, authenticated Codex CLI and local Linux/amd64 Docker,
run from the repository root:

```sh
python -m creation_pipeline build examples/base-count/input.json --state-dir .pipeline/base-count --library-dir ./base-count-library --keep-debug
python -m creation_pipeline library ./base-count-library
python -m creation_pipeline library ./base-count-library --include-candidates
python -m creation_pipeline install ./base-count-library --name dna-base-counting-cli --destination ./installed
python -m creation_pipeline runtime-inspect ./base-count-library --candidate dna-base-counting-cli
python -m creation_pipeline runtime-resume ./base-count-library --candidate dna-base-counting-cli
python -m creation_pipeline runtime-build ./base-count-library --candidate dna-base-counting-cli
```

Use the actual discovered name if another model run chooses a different one. Names,
packaging layout and plans need not be byte-identical. Runtime calls use the frozen
source, entrypoint and locked tests; they do not rediscover or rewrite unchanged files.

In the recorded run, discovery/authoring/review completed, but the initial planner
call reached its 600-second operation timeout. The same persistent candidate was
continued with the existing runtime entry, without editing its files or native checks:

```sh
python -m creation_pipeline runtime-prepare ./base-count-library --candidate dna-base-counting-cli --spec validation/stage5/dna-resume-spec.json
```

That spec sets a 900-second single model-call fault timeout, not an overall work
quota. Real model planning, Docker build and ten checks then passed. This demonstrates
the full chain with explicit runtime recovery, not an uninterrupted automatic build.

Copy or ZIP the complete library (catalog, packages, evidence and runtime records),
then explicitly verify and reexecute at the destination:

```sh
python -m creation_pipeline runtime-relocate ./moved-library --candidate dna-base-counting-cli --revalidate
```

An installed envelope can instead be imported and revalidated:

```sh
python -m creation_pipeline runtime-import ./installed/.runtime/dna-base-counting-cli ./imported-library --candidate dna-base-counting-cli
python -m creation_pipeline runtime-resume ./imported-library --candidate dna-base-counting-cli
```

Import returns `not_run` (exit 1) until current acceptance. Candidates require explicit
selection and cannot be installed; `--draft-only` never grants formal qualification.
Missing resources are preserved for runtime recovery. Unsupported remote/GPU/mount/
credential contracts do not become supported by supplying references.

The observed experiment and all interventions are in [stage five](../../docs/integration/stage-five.md).
The separate dilution experiment required a source-backed, independently reviewed
contract correction before acceptance; neither example substitutes for the other's evidence.
