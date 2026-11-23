# Required delivery paths and qualification

Caller-specified file locations are part of the delivery contract. Identical content elsewhere does not satisfy them. Case-insensitive Windows aliases cannot replace exact frozen paths. Authors and planners cannot rewrite these requirements.

artifacts/layout.py reads the original prompt, task, constraints, notes and applicable runtime requirements before authoring, compiling delivery_layout. Candidate overrides apply only to that candidate; defaults apply to all candidates. Supported deterministic forms include:

- `Deliver exactly SKILL.md, scripts/main.py and deps.lock;`, including Ship/Package and exactly/only variants, and `Deliver EXACTLY two files: ...`.
- `Required files: scripts/main.py, resources/input.dat;`, which permits additional files.
- `` `deps.lock` must be at package root. `` and `deps.lock is required in the package root.`.

Additional localized forms are implemented in artifacts/layout.py. Unsupported explicit lists, unsafe paths and conflicts are rejected during preflight. Mentioning a dependency file, source or example does not itself create a delivery obligation. Other wording, complex filenames or machine-specified requirements can use:

```json
{
  "constraints": {
    "delivery_layout": {
      "required_files": ["deps.lock", "data files/input.bin"],
      "exact_files": ["SKILL.md", "scripts/main.py", "deps.lock", "data files/input.bin"]
    }
  }
}
```

Either key may be omitted. exact_files also requires every listed file to exist. Wildcards, directory-existence rules, negative path constraints and arbitrary natural language are outside the deterministic v1 layout protocol. Explicit paths override the default role-directory layout; credential exclusion, safe paths and size limits still apply. Skill structure still requires SKILL.md and is not imposed on lower-level tool materials.

The frozen `inputs.layout={version:1,payload,sha256}` stores original text, field references, required files and an optional complete file set. It contributes to its own fingerprint and the revision ID. Validation recompiles the original text and compares the contract, preventing removal of a required file followed by hash recomputation. Authors receive the same object; helper and host finish use the same gate. Independent review still inspects the actual package and sources.

The actual package is checked again before environment preparation. delivery_layout_mismatch identifies the content path and withdraws content approval before environment planning consumes a model call. qualify checks layout before either the no-execution or Docker-evidence branch. Existing passed/accepted flags cannot bypass it. runtime_request rechecks the frozen list; byte manifests, image file trees and executor checks establish correspondence to actual files. Installation, import and resume retain the frozen contract without inheriting execution qualification.

Errors include code, path, expected, actual, alternative locations, actual delivered files and original field references. Extra files in an exact list are reported separately. Validation does not move files or rewrite requirements or sources.

To audit an existing delivery:

```text
python -m creation_pipeline check OUTPUT_OR_PACKAGE --config ORIGINAL_CONFIG.json
```

This command performs no model calls or business execution, grants no new qualification and does not modify the package. Outputs with frozen requirements check both those requirements and the supplied configuration; a weaker external configuration cannot override the freeze. Without --config, an output uses its frozen requirements. Standalone package structure checks do not authorize installation or execution.

Delivery protocol 1 is read using its frozen rules. A package without original caller text cannot establish its required locations retroactively: supply the original configuration for static auditing or generate an independently reviewed and executed revision. Frozen records and qualification are not rewritten automatically. Path changes affect the tool closure and cannot reuse a differently located ToolArtifact. Each Skill's prose, tests and original request remain separately frozen and checked.
