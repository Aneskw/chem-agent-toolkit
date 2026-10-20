# Tool Skill Packaging Requirements

This guide supplements [the minimum SKILL.md requirements](minimum.md).
It defines packaging rules for atomic tool skills and the creation pipeline.
Implementation support and limitations are documented in [the usage guide](../pipeline/usage.md).

## 1. Classify two independent dimensions

**Packaging intent**

- **Direct packaging:** expose an existing tool capability without adding a new
  domain-level computation or acceptance policy. Input parsing, request construction,
  response checks, and output saving normally belong to direct packaging.
- **Capability extension:** add behavior beyond the upstream call, such as a new
  scientific validation rule, diagnostic calculation, or result acceptance policy.
  State what the upstream tool does and what the extension adds.

**Instruction complexity**

- **Compact:** one coherent task, a straightforward call, and few special conditions.
- **Expanded:** the same coherent task needs substantial mode-specific instructions,
  configuration guidance, data conversion rules, or result interpretation.

These dimensions are independent. An extension can fit in one file; a directly
packaged tool can need several references. Python library, CLI, HTTP service, and
remote execution are interface forms, not size classes. Use the smallest adequate
package; neither an entire software product nor every API function is automatically
one skill.

## 2. Decide the task boundary before choosing files

A skill should have one recognizable user objective, a coherent input/output
contract, and an independently assessable outcome.

Keep necessary preparation, execution, and result inspection together. Keep local
and hosted modes together when they serve the same objective and compatible outputs.
Consider splitting when capabilities have different triggers, prerequisites,
input/output contracts, or scientific success criteria and can be selected independently.
Do not split merely to shorten a file. Multi-task orchestration belongs to a separate
workflow layer and is outside this guide.

Routine checks such as non-empty output or valid JSON are part of a call contract.
Treat a check as an extension when it introduces new domain criteria, calculations,
dependencies, or a new verdict beyond upstream behavior.

## 3. Choose a packaging profile

| Profile | Minimum runtime package | SKILL.md emphasis | Additional requirement |
| --- | --- | --- | --- |
| Compact direct packaging | `SKILL.md` | Scope, essential I/O, one complete call, minimum result checks | No supporting files unless needed |
| Expanded direct packaging | `SKILL.md` plus selected `references/` files | Common path, branch selection, mandatory checks, conditional reference links | Explain the reason for each supporting file |
| Integrated extension | Either layout above; `scripts/` only if justified | Upstream call, added behavior, separate outputs and checks | Define and verify the extension contract |
| Independent extension | Separate skill when independently selectable | Its own task, inputs, method, and verdict | Identify upstream artifacts and their requirements explicitly |

An independent extension is still an atomic capability if it completes one
independently assessable task. Do not force an extension into a separate skill when
it is inseparable from the packaged task.

## 4. File organization

```text
tool-task/
  SKILL.md                       # required
  references/                    # only for conditional detail
    <task-relevant-topic>.md
  scripts/                       # only for justified reusable implementation
    <entrypoint>.py
  assets/                        # only for required templates or small fixtures
```

This tree shows permitted roles, not directories to generate by default.

- **SKILL.md:** include the four minimum information requirements. Keep the normal
  call path, decision-changing boundaries, and minimum acceptance checks here.
- **references/:** place long parameter guidance, deployment instructions, specialized
  modes, scientific background, or uncommon troubleshooting here. Link each file
  with a specific read condition. Do not hide mandatory common-path checks behind
  optional reading or duplicate complete examples across files.
- **scripts/:** use when repeated implementation is substantial or easy to get wrong,
  or when an extension needs a stable implementation. A trivial API call can remain
  inline. Every script needs a documented entrypoint, inputs, outputs, and failure
  semantics. Do not invent a wrapper solely to satisfy a directory template.
- **assets/:** include only files needed by the task. Do not bundle upstream source
  trees, model weights, or large datasets by default; document acquisition when needed.

Source records, review status, evaluation definitions, and test results should be
retained by the pipeline or repository without automatically entering the agent's
runtime context. They may be co-located for distribution, but are not extra mandatory
sections in SKILL.md. Runtime links must resolve in the distributed package.

### Suggested main-file layouts

For compact direct packaging, use the minimum template without extra sections.
For expanded direct packaging, the same content can be arranged as follows:

```text
Frontmatter: name + task-specific description
Scope: objective and decision-changing capability boundaries
Input & Output: common contract and important exceptions
Usage:
  normal call example
  branch rules, if needed
  read references/environment.md only for deployment or missing dependencies
  read references/parameters.md only for non-default configuration
Result Checks:
  mandatory common-path checks
  read references/validation.md before making the specified advanced claim
```

For an integrated extension, additionally state the added behavior in Scope,
the added fields in Input & Output, and the extension's method or script in Usage.
In Result Checks, distinguish upstream completion from the extension verdict and
define what missing evidence means. A long method may move to a conditionally linked
reference; the verdict's meaning and essential assumptions stay in the main file.
For an independent extension, apply the same pattern to its own task rather than
copying the upstream tool's entire installation and usage guide.

These are content placement examples, not extra compulsory headings. Reference names
are illustrative; create only files that the actual task needs.

## 5. Requirements by interface form

Add only the rows relevant to the packaged tool.

| Interface | Required details when applicable |
| --- | --- |
| Python library | Import and entrypoint; non-obvious types/shapes; units and indexing; mutation; device placement and synchronization |
| CLI or local executable | Executable resolution; working directory and paths; command arguments; generated files; exit status and tool-specific completion checks |
| HTTP/model service | Endpoint and method; authentication source; payload types; task status; timeout/failure behavior; artifact-to-score mapping |
| Local container service | Image version; necessary runtime resources; mounts and ports; bounded readiness check; deployment versus inference requirements |
| Remote/HPC execution | Existing connection or launcher configuration; transfer method and remote paths; submission versus completion; job identification; result retrieval |

SCP transfers files; SSH or the declared scheduler/launcher executes remote work.
Do not conflate transport, execution, and result retrieval. Prefer existing project
environments and configuration. Document credentials by variable/configuration name,
never by embedding secret values. Include installation instructions only when the
task requires setup.

For version-sensitive behavior, state the documented or tested version and retain
the corresponding source record. An example parameter is not a universal default
unless upstream evidence establishes that default.

## 6. Additional contract for capability extensions

An extension must specify:

1. **Added behavior:** the new computation, check, or decision and why it is needed.
2. **Inputs:** required upstream artifacts, metadata, units, and assumptions.
3. **Method:** the rule or algorithm, implementation location, and any additional
   dependencies. Attribute externally sourced rules; label project-defined heuristics.
4. **Outputs:** added measurements or verdicts, distinct from upstream outputs.
5. **Acceptance and uncertainty:** what supports pass/fail and what remains unknown.
   Missing evidence must not silently become a pass or a scientifically definitive fail.
6. **Verification:** checks that test the added behavior, including relevant boundary
   cases. Keep verification evidence outside the routine usage instructions.

Never silently alter user-supplied structures or replace upstream scientific settings
as part of validation. If repair or transformation is part of the task, document it
and preserve the relationship between original and derived artifacts. Computational
completion, numerical validity, and scientific adequacy are separate claims.

## 7. Creation and later evaluation

1. Identify one task, its real upstream entrypoint, source versions and prerequisites.
   A paper is optional; method claims need evidence beyond an API signature.
2. Plan the scope, direct packaging or extension, necessary files and verification.
   Keep this lightweight build record separate from runtime instructions.
3. The model writes the complete final files directly. The program saves them
   verbatim; it does not reconstruct Markdown from contract fields or fixed headings.
4. Check metadata, paths, actual interfaces and executable examples. Verify added
   behavior using independently grounded expected outcomes and relevant negative cases.
5. Use bounded repair. Record executed, unexecuted and model-reviewed evidence
   separately. Package and clean only registered temporary work.
6. Conduct Agent effectiveness evaluation separately after major pipeline revisions
   and a batch of useful outputs. Independently freeze tasks and compare quality,
   recovery and costs under matched tool access. This is not a per-build stage.

Do not equate a generated test, a passing example, a model review or an engineering
ready status with demonstrated Agent benefit or general scientific correctness.

## 8. Review examples

| Candidate | Likely initial choice | Reason |
| --- | --- | --- |
| One scalar molecular descriptor | Compact direct | One call and a small result contract |
| A fingerprint/similarity task using a GPU library | Compact or expanded direct | Expand only for material batching/device/layout requirements |
| One hosted docking request | Direct; expand for substantial input/scientific guidance | Complex backend does not itself require a large skill |
| Hosted and local docking with the same task | Expanded direct | Shared task plus deployment-specific references |
| NEB input preparation with consistency checks | Direct with scripts if needed | Preparation checks enforce the declared input contract |
| A TS validator adding frequency/connectivity criteria | Extension; separate if independently selectable | Adds a scientific verdict beyond calculation completion |

These are starting judgments, not tool-name-based rules. Reassess using the actual
task boundary, implementation needs, and evaluation results.
