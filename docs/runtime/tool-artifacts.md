# Local ToolArtifact protocol

runtime/shared_tool.py manages source closures, tool artifacts, concrete version selection and execution bindings. v1 supports Python tools with declared complete closures. External executables, JSON resources and scoped contracts use their respective ABIs.

## Objects and states

| Object | Identity and persistence | Qualification boundary |
| --- | --- | --- |
| EnvironmentArtifact | Dependency recipe, daemon ID, image ID and layer/config observations | Establishes no business result |
| ToolArtifact | ABI, full request, build plan without acceptance, concrete base/environment, observed daemon/image and artifact_id | Checked build object, not a qualified new Skill |
| SkillBinding | Frozen package/source/interface/acceptance identities; embedded selection on hits or a full freeze-bound build receipt on first build | Inherits no prose or qualification |
| ExecutionAttempt | Independent directory/container, current locked cases, inputs, outputs, image, assertions and timing | Recorded runs cannot grant current execution qualification |

request_key covers the pre-planning closure (path/sha256/bytes/mode), explicit requirements, interface, platform, policy, constraints and memory/cpus/pids. recipe_key covers a concrete environment plan without acceptance and its pinned base under the renderer ABI; it does not prove a complete rebuild lock or reproducibility. artifact_id fingerprints the observed version record. image_id with daemon_id identifies local Docker content, not an OCI manifest digest. Renderer or closure changes require an ABI/policy revision.

built, observed available and Skill accepted are separate facts. Tool records contain no tests, passed flag or Skill qualification. Environments with complete_rebuild_lock=false can reuse only the checked concrete image.

## Declaration, closure and preparation

Configure runtime.<candidate> or runtime_defaults:

```json
{
  "options": {"pin_base_image": true},
  "shared_tool": {
    "closure": "all-package-and-sources-except-skill-document",
    "requirements": {"imports": {"rdkit": "unpinned"}, "executables": []},
    "interface": {
      "entrypoint": ["python", "/opt/skill/package/scripts/audit_atom_maps.py"],
      "workdir": "/opt/skill", "resources": [], "runtime_network": false
    },
    "platform": "linux/amd64", "policy": "closed-python-bundle-v1"
  }
}
```

All package support files and complete sources enter the closure; only root package/SKILL.md is excluded. That document remains part of Skill freeze, review and source checks. Other files cannot be selectively excluded, so examples, resources and helper changes conservatively miss. Locked fixtures and cases can differ between Skills.

requirements/constraints enter the request conservatively. Without scoped contracts, the pipeline places the caller prompt in requirements, so different prompts can miss. Callers should share requirements only when those requirements actually match. Changing only SKILL.md prose leaves the tool request unchanged.

Third-party imports need explicit distribution requirements with exact versions or unpinned; supported distribution names match import names. Recipe declarations must agree, and build/binding checks installed versions. Local modules and data are included by bytes. v1 rejects dynamic loading/execution, __file__, external processes/resources, runtime network, Markdown entries, source-dependent installation, generated dependency files and dependencies outside the closure. Caller declarations cannot replace these checks. Unsupported tools receive a named miss/block or use self-contained mode.

Hits resolve before propose() and base resolution. The acceptance_only schema permits only tests, acceptance_json, output_contract and unverified_behavior. Real, simulated and replayed responses use the same strict schema, rejecting environment fields and patch operations. The host copies the bound environment and merges current acceptance deterministically; the model cannot change the environment or entry.

Material reads, deadlines, attempt limits, call guards and backend retries use their existing budgets. Receipts identify runtime_acceptance_planning separately from runtime_planning. Each acceptance read/generation call consumes budget; skipping environment planning does not imply zero model calls.

An initial miss can use combined planning or an explicit plan. Hits do not use the combined environment planner. A supplied plan with different environment fields reports supplied_environment_plan_mismatch. Current cases must pass source-reference, coverage, negative-case, locking and native-check validation. Independent content review remains required. Unavailable models, timeouts, exhausted budgets or invalid contracts block rather than reuse old cases or replan environments. Repairs use the current rejected draft. An explicit acceptance_plan must contain exactly the same four fields and pass the same checks.

## Images and qualification

Self-contained mode verifies revision/environment labels, complete package manifests and source entries. Tool mode uses chem.tool.request/chem.tool.recipe labels and actual daemon/image identity. The canonical tree is /opt/tools/<request_key>/, with a byte-identical /opt/skill/ execution layout for entry/native checks. Both trees are verified; the compatibility copy consumes storage. SKILL.md is absent from tool images. Checks that require it must fail or use self-contained mode rather than be removed.

Before execution, recompute the closure and limits and verify the frozen package/sources, concrete record, entry, layers/ENV/WORKDIR, non-root user and file contents. Extra files and links are rejected. Each task uses an independent read-only, non-root, network-disabled container. Reports need locked_inputs, observations_pass, coverage and current-daemon checks before qualification. A Skill's business failure does not alter its tool or other Skills.

## Registration, inspection and recovery

The default registry is .pipeline/shared-tools. CHEM_AGENT_SHARED_TOOLS can select an absolute shared root on the same host; that path is not part of frozen recipes. A request_key lock waits within the build deadline, then rechecks candidates. Complete build, identity, content and current-input checks precede atomic publication of <request_key>-<artifact_id>.json. Versions append without overwriting. Failures/timeouts publish nothing; cancellation releases only its owner token. Age alone cannot reclaim a crashed lock.

```text
python -m creation_pipeline runtime-tools-inspect
python -m creation_pipeline runtime-tools-inspect --offline
python -m creation_pipeline runtime-tools-inspect --root ABSOLUTE_PATH
```

Inspection creates no directories/images, removes no locks and runs no business code or qualification. Offline returns historical_unverified; online observations include different_daemon, image_unavailable_or_changed and invalid_record. Misses identify concrete versions, fields or paths, without inferring compatibility between distinct requests.

Installed envelopes, import, same-host relocation and recovery use one catalog. Import/relocation withdraws qualification and requires the current locked contract to run again. Recovery, including explicit rebuild, checks the bound concrete version rather than silently replacing a lost image with a recipe rebuild; a new artifact requires explicit preparation of a new revision. Execution uses frozen sources and image files rather than incidental author paths.

Availability is not inherited across hosts/daemons. There is no OCI registry/archive image transfer; copying a file envelope does not deliver its image. Missing concrete artifacts block explicitly.

Installation produces a pure package and .runtime/<name>/{frozen,attempt}. Import accepts that complete envelope or native output containing records/<name>.json. Bare Skill packages, envelopes without receipts and image archives are rejected. Imported candidates need explicit execution before installation. Relocation withdraws execution-location qualification without rewriting frozen inputs or bindings.
