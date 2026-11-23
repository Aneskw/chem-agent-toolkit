# Sibling JSON resources: shared_tool_image_v4

This protocol supports fixed Path(__file__).with_name("rules.json").read_text(encoding="utf-8") reads. runtime/bundled_data.py requires the declared module, sibling file and original byte hash.

Declarations contain closure, requirements, interface, platform, policy and bundled_data. policy=closed-python-sibling-json-v1 selects ABI v4:

```json
{
  "module": "scripts/screen.py",
  "path": "scripts/rules.json",
  "sha256": "57f8da82b4c7eec60fb37001152a57e8fc9a38624e7a6ee9462a04b600be34ba"
}
```

This is one bundled_data item, not a complete shared_tool declaration. module/path are safe, unlinked, existing package-relative paths. Resources must be UTF-8 JSON matching the raw hash. Only unaliased `from pathlib import Path` is supported. with_name takes one nonempty literal filename without separators, absolute paths or .., and must resolve to the declared sibling path.

Every declaration must be read. read_text requires encoding=utf-8 without positional arguments or additional keywords. Default encodings, mixed resolve/parent and with_name chains, aliases, intermediate variables, rebinding, reflection and writes are unsupported. Exception/pattern bindings and attribute replacement are rejected. The source must pass closure, import and explicit-version checks. Unknown structures return shared_tool.bundled_data or shared_tool.closure with module and expected/actual paths.

The entry is a unique source-identical script, with explicit argv and resources. Required interface: /opt/skill, Linux/amd64, resources=[], runtime_network=false and executables=[]. All implementation files and sources retain path/sha256/bytes/mode. Current SKILL.md is excluded from tool identity but remains in Skill freeze/qualification. Declarations, dependencies, interfaces, policies and runtime limits enter request_key. recipe_key identifies the concrete recipe; observed daemon/image/environment and artifact record establish artifact_id. A local image ID is not an OCI manifest digest, and resource hashes grant no business qualification.

Automatic resolve or explicit select precedes planning, followed by lock-held rechecks and checked publication. Hits skip environment planning and builds while retaining independent content review, current acceptance planning, source/layout/entry and full image checks, fresh locked-contract execution and qualify. Preflight uses the same static rules so known path/hash errors are reported before model calls.

Changing a resource without updating its declaration reports expected/actual SHA. Updating the declaration, source, dependencies or interface creates a new request. Automatic lookup misses; an explicitly mismatched version returns selected_request_mismatch without replacing the version or binding. Unknown structures are rejected rather than inferred complete from a successful Python run. This is a bounded source-shape protocol, not a general Python safety proof.

Outer ToolArtifact fields match v1/v3; SkillBinding, delivery protocol 2, RuntimeRequest and ExecutionAttempt fields retain their schemas. v1–v3 use their own validators. Relabeling cannot convert an artifact to v4, and unsupported clients must reject it without stripping declarations or downgrading qualification. Installation/import/relocation retains the complete frozen envelope and requires fresh execution qualification. OCI distribution, arbitrary imports/subprocesses, automatic GC and transparent cross-host recovery are unsupported.
