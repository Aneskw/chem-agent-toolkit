# Research Skill Creation Pipeline — integrated workflow

The partner native Agent pipeline remains the single creation flow. Versioned delivery contracts and a durable accepted/candidates library connect to local Linux/amd64 Docker dependency building and migrated business execution acceptance.

Normal builds accept independently reviewed, source-supported reading-only skills. Executable skills additionally require current Docker evidence against their locked tests and actual delivered entry. Unknown requirements do not bypass execution. Explicit drafts never qualify for formal delivery.

```text
python -m creation_pipeline build sources.json
python -m creation_pipeline build sources.json --draft-only
python -m creation_pipeline library skills
python -m creation_pipeline library skills --include-candidates
python -m creation_pipeline install skills --name my-skill --destination ./installed
python -m creation_pipeline runtime-build skills --candidate my-skill
python -m creation_pipeline runtime-validate skills --candidate my-skill
python -m creation_pipeline runtime-prepare skills --candidate my-skill --spec runtime-spec.json
python -m creation_pipeline runtime-inspect skills --candidate my-skill
python -m creation_pipeline runtime-resume skills --candidate my-skill
python -m creation_pipeline runtime-relocate moved-library --candidate my-skill --revalidate
python -m creation_pipeline runtime-import native-output moved-library --candidate my-skill
```

Use `--library-dir` to select a different persistent library, `--no-adopt` for output-only trials, and `--keep-debug` to retain temporary work. Failed/unqualified candidates retain recovery material. Library evidence is independent of temporary runs and caches.

Python 3.11+, Git and authenticated Codex CLI are required for live generation. Runtime plan validation requires an already available `jsonschema`; local image building requires Docker with a Linux/amd64 engine. The integration never installs host packages. Candidate software is installed only by Docker build steps. Production retains no hidden aggregate time/turn/read quota; explicit caller limits and operation timeouts remain effective.

Read the [fresh-source example](examples/base-count/README.md), [stage-five results and limits](docs/integration/stage-five.md), [implementation architecture](docs/pipeline/integrated-flow.mmd), [recovery and relocation protocol](docs/pipeline/runtime-recovery.md), [stage-four verification record](docs/integration/stage-four.md), [execution protocol](docs/pipeline/docker-execution.md) and [stage-three record](docs/integration/stage-three.md). Earlier stage documents describe their recorded baselines where not superseded. `ready` requires formal qualification; `built` never grants it.

Engineering tests: `python -m unittest discover -s tests -q`. Deterministic model fixtures test mechanisms, not real model quality, Docker execution or scientific validity. Historical skills and approval records are not automatically admitted to the integrated library.

This copy adds an opt-in [DeepSeek API backend](docs/integration/deepseek-api-backend.md) for the structured, tool-free model calls only (entry association, runtime planning, contract diagnosis). Discovery, authoring and independent review keep the Codex CLI transport. The backend is selected per candidate with `runtime.<candidate>.options.backend=deepseek_api`; it is never a fallback, the model name is read from configuration and never guessed, and credentials stay in the git-ignored `.env`. See `validation/deepseek-api/` for the acceptance configuration, the frozen planner prompt/schema and the single-request check.

The [contract consistency and automatic repair follow-up](docs/integration/contract-repair.md)
separates normal creation, historical oracle repair and deliberate fault injection.
Unknown business failures require source diagnosis; they do not automatically prove
defective Skill code. Existing runtime recovery can propose and independently review
a versioned source-backed contract correction before full Docker revalidation.

The [final independent acceptance review](docs/integration/final-acceptance.md) records current fixes, mechanism regression and outstanding live acceptance blockers. Historical recovery success is not a successful uninterrupted fresh creation.
