# RuntimeRequest dependency environments

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
$env:CHEM_AGENT_SHARED_ENVIRONMENTS = 'D:\work\shared-environments'
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
python validation/integration/verify_cross_checkout_registry.py FRESH_ROOT --checkouts CHECKOUT_A CHECKOUT_B
```

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
