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
python -m creation_pipeline runtime-shared-inspect
```

Use `--library-dir` to select a different persistent library, `--no-adopt` for output-only trials, and `--keep-debug` to retain temporary work. Failed/unqualified candidates retain recovery material. Library evidence is independent of temporary runs and caches.

Python 3.11+, Git and authenticated Codex CLI are required for live generation. Runtime plan validation requires an already available `jsonschema`; local image building requires Docker with a Linux/amd64 engine. The integration never installs host packages. Candidate software is installed only by Docker build steps. Production retains no hidden aggregate time/turn/read quota; explicit caller limits and operation timeouts remain effective.

Read the [fresh-source example](examples/base-count/README.md), [stage-five results and limits](docs/integration/stage-five.md), [implementation architecture](docs/pipeline/integrated-flow.mmd), [recovery and relocation protocol](docs/pipeline/runtime-recovery.md), [stage-four verification record](docs/integration/stage-four.md), [execution protocol](docs/pipeline/docker-execution.md) and [stage-three record](docs/integration/stage-three.md). Earlier stage documents describe their recorded baselines where not superseded. `ready` requires formal qualification; `built` never grants it.

Engineering tests: `python -m unittest discover -s tests -q`. Deterministic model fixtures test mechanisms, not real model quality, Docker execution or scientific validity. Historical skills and approval records are not automatically admitted to the integrated library.

This copy supports an explicit [DeepSeek API backend](docs/integration/deepseek-api-backend.md) for structured, tool-free calls (entry association, runtime planning, contract diagnosis), selected with `runtime.<candidate>.options.backend=deepseek_api`. Discovery, authoring and review separately support the default Codex CLI or opt-in `model.backend=deepseek_api`; the latter returns structured files for host finalization instead of providing the CLI tool loop. Backends never switch as a fallback. Model names come from configuration and credentials stay in the git-ignored `.env`. Current live acceptance uses native Codex CLI plus structured DeepSeek, and does not prove the all-DeepSeek combination.

Docker [shared dependency environments](docs/pipeline/shared-environments.md) reuse exact pinned dependency recipes across skills, followed by separately verified thin tool images and isolated task containers. Each skill still executes its own locked business checks. The [sharing design](docs/integration/shared-tool-layer-current-design.md) records real two-tool, failure-isolation and concurrency evidence. The later [ToolArtifact resolver protocol](docs/pipeline/shared-tool-artifact-protocol.md) is a design proposal, not an implemented planner shortcut. [Text output predicates](docs/pipeline/text-output-patterns.md) can check declared read-source positive examples before locking, while actual output validation remains required.

The [contract consistency and automatic repair follow-up](docs/integration/contract-repair.md)
separates normal creation, historical oracle repair and deliberate fault injection.
Unknown business failures require source diagnosis; they do not automatically prove
defective Skill code. Existing runtime recovery can propose and independently review
a versioned source-backed contract correction before full Docker revalidation.

The [current acceptance report](docs/integration/current-acceptance-20261029.md) records five independently successful mixed-backend batches and 72/72 Docker execution records, including Open Babel run74 (8/8). Frozen bundles, current images and all five accepted library qualifications were checked; the latest offline suite passes 647 tests (three skipped) and all three prompt checks pass. A host-configured registry also shares environments between checkouts, verified with two separate Python/Docker processes. The [four-scenario campaign](docs/integration/extended-acceptance-campaign.md), [Open Babel experiment](docs/integration/planner-openbabel-experiment.md) and [round log](docs/integration/acceptance-experiment-log.md) retain unsuccessful attempts and the fixes they drove. This scope does not establish every Skill/backend combination or independent scientific validity. The [October 26 review](docs/integration/final-acceptance.md) remains a historical report with its original version and scope.
