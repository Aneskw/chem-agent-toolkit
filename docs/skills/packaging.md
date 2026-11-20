# Tool skill packaging

Apply the [minimum requirements](minimum.md) for eligibility, capability scope, version choice
and usage content. This guide covers file organization and delivery details.

## Source and behavior

Direct packaging exposes existing upstream behavior. Research extensions package a method or combination already supported by the supplied research/code. Record original method and implementation evidence in the separate writing basis; do not invent scientific thresholds, algorithms or new acceptance policies from generic documentation. Formatting and invocation glue may be added transparently and independently reviewed. Missing algorithms, weights or data remain gaps.

Prefer supported entrypoints and structured outputs that cover the task without avoidable manual
reimplementation. A lower-level route can be appropriate when the scientific method or declared
inputs require it; do not infer that the highest-level API is always best.

## Files

```text
capability-name/
  SKILL.md
  references/           # conditional detail
  scripts/              # necessary source-grounded executable support
  assets/               # necessary small inputs/templates
```

SKILL.md contains selection, the common path, decision-changing boundaries, essential prerequisites,
a usable example and result handling. For a task family, make mode selection explicit and keep each
promised route complete across the main file and its linked reference. Substantial conditional
instructions can live in references so ordinary use need not read every branch. Follow the minimum
standard without a fixed chapter template; do not copy complete API references.

A reference needs a usage purpose, such as setup, parameter lookup or a method needed for the task.
Put the link where that need arises and explain conditional reading when appropriate. There is no
mandatory Reference section. Construction provenance, source-ID mappings and review evidence stay
outside the package; citing a source does not by itself make a paragraph useful at runtime.

Scripts need an entrypoint, inputs, outputs and failure semantics, with source/version attribution.
Use them when repeated, error-prone invocation or transformation would otherwise be reconstructed
from Markdown by the execution Agent. Compare that work with the cost of another script interface;
a short adaptable example is enough for simple operations. A narrow task can justify a script and
a broader task need not have one. Do not generate scripts to satisfy a template.
Existing research code may be packaged when its dependencies/resources are
understood. Independent tool packages, sibling-skill script dependencies and shared tool layers are
unsupported. Do not bundle upstream trees, weights, private credentials or large datasets.

## Interface details

For Python: real import and entrypoint, important types/shapes, mutation and result access.
For CLI: executable resolution, arguments, cwd, relative paths, output files and failure signals.
For existing services: declared endpoint/authentication source, request/response, completion and artifact relationships. No service deployment is generated.

A pure package must be independently usable with its declared inputs: name and link essential
external tools, relevant source versions and official installation/resource entrypoints. Do not
assume access to the build conversation, private source index or sibling package.

Document existing prerequisites only when necessary; no generated Docker/Conda environments or automatic dependency installation. Preserve original structures unless the source-supported operation explicitly transforms them. Clearly distinguish transformed output from original input.

## Review and information value

The program checks package structure, paths, references and applicable script syntax without
importing or executing target tools. An independent Agent checks original sources, actual
interfaces, preparation, input/output contracts, Usage and result meaning. It also proposes
concrete removal of redundancy and compact alternatives for low-value prose. Do not remove
important pitfalls to meet a word count. No runtime test definitions or exact numeric outputs
are required. Missing local target dependencies do not block sound instructions.

Markdown `python`/`py` fences provide host-parser syntax observations to the reviewer, not an
execution verdict. Label intentional excerpts and their scope; the reviewer distinguishes real
errors from snippets or target-version syntax differences. Required source files and quantitative
interpretation conditions belong in the usable workflow. Correct defects in that path rather
than appending a disclaimer or changing code-fence labels to hide them.

Writing basis and review findings stay in build records, not the runtime package. Source/content
approval does not establish runtime success, scientific adequacy or Agent benefit.

Binary support assets may be delivered when useful and source/license conditions are understood. Do not treat all resources as UTF-8 text. Candidate scope and file organization may evolve with evidence; record meaningful adjustments outside runtime context. No server/Docker provisioning is performed.
