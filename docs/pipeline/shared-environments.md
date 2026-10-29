# Shared dependency environments

The local Docker executor shares explicitly declared dependency stages across
skills. Each task still gets a separate container, and each skill keeps its own
locked business tests and qualification. This is environment reuse, not a shared
long-running process, result cache or implemented Tool resolver.

Preparation emits a versioned dependency recipe only when the base is pinned to
a RepoDigest and build_layout declares a source-independent prefix. The key covers
that base, platform, environment setup, exact dependency file bytes/modes/paths,
ordered installation commands and renderer ABI. Skill prose and test fixtures
are excluded when they are not dependency inputs. Uncertain plans retain the
ordinary build path. The planner must not move code-dependent steps into a prefix.

The registry at `.pipeline/shared-environments` records the observed immutable
image ID and Docker daemon ID. A recipe key identifies a build request, not an
identical-from-scratch reconstruction guarantee; unclosed dependencies retain
complete_rebuild_lock=false. A checked local tag is used only for BuildKit transport.
The final thin image is verified against the expected environment layers, ENV,
WORKDIR and the existing entrypoint/package checks.

To share that registry between pipeline checkouts on the same Docker host, set
`CHEM_AGENT_SHARED_ENVIRONMENTS` to an absolute directory for the relevant process:

```powershell
$env:CHEM_AGENT_SHARED_ENVIRONMENTS = 'E:\Users\27343\Docker\shared-environment-cache'
python -m creation_pipeline runtime-shared-inspect
```

Leaving it unset or empty retains the per-checkout default. This is host cache
configuration; it does not enter model context, frozen recipes or delivery input
fingerprints. The selected path is recorded in the dynamic build observation.
Root links are still rejected, and daemon/image/platform/recipe checks and locks
still apply. Different Docker daemons do not inherit availability. A relative
host setting blocks applicable shared builds instead of silently selecting another
cache; ordinary builds without a declared shared prefix do not use that setting.
The inspector uses the same default, with `--root PATH` as an explicit override.
This option does not implement a ToolArtifact resolver or remote OCI distribution.

The opt-in real infrastructure check is:

```text
python validation/deepseek-api/verify_cross_checkout_registry.py FRESH_ROOT --checkouts CHECKOUT_A CHECKOUT_B
```

It starts separate Python processes with different checkout imports and working
directories, sets the common directory only in those child processes, and builds
two different stdlib tools. It requires one environment build, a second-process
hit on the same environment, inherited configuration/layers and independent correct
container outputs. Source/recipe data excludes the cache location. It does not
run chemistry or models, change system environment settings or imply concurrency
queueing. Fresh trials shared-registry-cross-checkout-20261029-01 and -02 passed
under E:\Users\27343\Docker. Four location/CLI regressions and the latest combined
647-test suite pass (three skipped), alongside the three prompt self-checks.

Per-key locks prevent duplicate builders. A contending request waits within its
existing build deadline, acquires the released lock and rechecks the completed
record/image before reuse. A failed owner permits a new builder; it does not
publish a reusable partial record. The dynamic receipt records
`waited_for_builder`. Waiting and dependency preparation share the original
thin-image build deadline; an expired budget cannot start a thin-image build.
Timeout or cancellation never removes another owner's lock, and crashed locks
require explicit recovery. This is bounded per-request waiting, not a durable
scheduler or a fairness guarantee. Incomplete and failed builds are not
registered. A failed installation remains build_failed for the existing environment
repair path; lock/resource unavailability is runtime_blocked. There is no automatic
GC, compatibility merge, stale-lock stealing or migration of an existing skill.

## Inspect without changing state

```text
python -m creation_pipeline runtime-shared-inspect
python -m creation_pipeline runtime-shared-inspect --offline
python -m creation_pipeline runtime-shared-inspect --root PATH
```

Current mode probes only Docker host/image metadata. Offline mode calls neither
Docker nor models, and returns historical_unverified instead of availability.
Neither mode creates a missing registry, changes records, removes locks/images,
installs packages, runs business code or grants a skill execution qualification.
Outputs use the existing credential redaction rules.

| Observation | Meaning |
| --- | --- |
| available | Current daemon image ID/platform/recipe label match the record |
| historical_unverified | Offline record only; no current availability conclusion |
| different_daemon | Local image identity cannot be inherited across daemons |
| image_unavailable_or_changed | Image disappeared or current identity/labels differ |
| pending_or_interrupted | Lock exists without a completed record; not a reusable artifact |
| invalid_record | Malformed/linked/inconsistent entry; not a reusable artifact |
| host_unavailable | Current Docker host cannot be checked |

The separate locked flag is not proof that the owner is alive or dead. Inspection
does not infer ownership from age. It also does not copy another skill's passed
flags. See [the design and experiments](../integration/shared-tool-layer-current-design.md)
for identities, compatibility evidence, scope and the later exact Tool resolver.

## Reproduce contention and isolation

```text
python validation/deepseek-api/verify_shared_concurrency.py FRESH_EVIDENCE_DIRECTORY
```

This opt-in real Docker infrastructure trial starts a dependency build, then
submits a second same-key request while the first holds its lock. The contender
must wait without consuming a partial record, then hit the completed environment
within the same request. Two different thin tools then execute in
separate network-disabled containers. No models, dependency downloads or chemistry
are used. Evidence directories are never reused, and failed evidence is retained.

The event-controlled trial `shared-environment-wait-20261029-01` passed one
environment build, two thin builds and both original callers completing without
resubmission. Historical `shared-environment-concurrency-20261029-02` instead
tested the former fail-fast policy; its unchanged evidence retains that scope.

For a real collision between two OS processes in separate checkouts, add
`--concurrent` to `verify_cross_checkout_registry.py`. The parent holds the first
builder before Docker build, requires the second process to observe the actual
exclusive-file collision, verifies no published record, then releases the builder.
Both workers must finish automatically, the second must record waiting and a hit,
and their separate isolated containers must return different tool identities.
`shared-registry-concurrent-checkouts-20261029-01` passed with one environment
build and two thin builds. Coordination hooks exist only in the validation script.
Four added regressions and the combined 647-test suite pass (three skipped),
with three prompt checks green; log shared-environment-wait-combined-tests-20261029.log.
The later [ToolArtifact protocol](shared-tool-artifact-protocol.md) remains a
design proposal and does not remove per-skill acceptance.

## Verify delivery and rebuild compatibility

```text
python validation/deepseek-api/verify_shared_delivery.py FRESH_DELIVERY_ROOT --library ACCEPTED_LIBRARY --name SKILL_NAME
python validation/deepseek-api/verify_shared_rebuild.py FRESH_REBUILD_ROOT --library FRESH_DELIVERY_ROOT/moved-library --name SKILL_NAME
```

The first opt-in real Docker trial installs the exact accepted package and its
runtime envelope, imports into a new library, and checks that old qualification
is not inherited. It executes every locked case in the new location, then copies
and explicitly relocates the library, withdraws qualification and executes all
cases again. The original accepted library/package and shared registry remain
unchanged. Model stages and image builds are forbidden during this reuse trial.

The second trial copies that revalidated library into another fresh root and
explicitly rebuilds. It requires the same shared recipe to hit, one thin-tool
build invocation, no dependency-environment build, unchanged revision/freeze and
fresh passed business cases. Models are forbidden. A Docker build invocation can
still use layer cache; it is not a measured installation rerun or speedup.

For Open Babel the public scripts passed in fresh evidence directories
`shared-runtime-install-compatibility-20261029-02` (16/16, two revalidations) and
`shared-runtime-rebuild-compatibility-20261029-02` (8/8, one thin build, environment
hit), both under `E:\Users\27343\Docker`. Earlier `-01` trials are retained too.
These are delivery compatibility checks of existing locked contracts, not new
independent Skill-generation batches or additional model requests.

After bounded-wait/deadline changes, another fresh current-code rebuild trial
`shared-runtime-rebuild-compatibility-20261029-03` passed 8/8, zero models,
one thin build and an environment hit. Frozen revision/package/source library
qualification and registry record bytes remained unchanged.
