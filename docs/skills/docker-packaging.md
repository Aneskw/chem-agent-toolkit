# Tool skill packaging

Apply the [minimum requirements](minimum.md) with the smallest adequate file set. One recognizable capability has coherent inputs, outputs and independently inspectable results. Neither a complete software library nor every API function automatically defines one skill.

## Source and behavior

Direct packaging exposes existing upstream behavior. Research extensions package a method or combination already supported by the supplied research/code. Record original method and implementation evidence in the separate writing basis; do not invent scientific thresholds, algorithms or new acceptance policies from generic documentation. Formatting and invocation glue may be added transparently and independently reviewed. Missing algorithms, weights or data remain gaps.

One skill may call multiple tools for one coherent objective. Separate capabilities with independently selectable triggers, contracts or result meaning. Keep mandatory preparation and result inspection together. Do not generate scripts just to satisfy a template.

## Files

```text
capability-name/
  SKILL.md
  runtime.json
  references/           # conditional detail
  scripts/              # necessary source-grounded executable support
  assets/               # necessary small inputs/templates
```

SKILL.md contains the normal path, decision-changing boundaries, essential prerequisites, usable example and result handling. Follow the minimum standard's title and organization guidance without a fixed chapter template. Long parameter details or uncommon modes may move to conditionally linked references. Keep common-path correctness in the main file; do not copy complete API references.

A reference needs a usage purpose, such as setup, parameter lookup or a method needed for the task.
Put the link where that need arises and explain conditional reading when appropriate. There is no
mandatory Reference section. Construction provenance, source-ID mappings and review evidence stay
outside the package; citing a source does not by itself make a paragraph useful at runtime.

Scripts need an entrypoint, inputs, outputs and failure semantics, with source/version attribution. Existing research code may be packaged when its dependencies/resources are understood. Task scripts stay in the Skill package; tool environments are shared separately. Sibling-skill script dependencies are unsupported. Do not bundle upstream trees, weights, private credentials or large datasets.

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

Writing basis and review findings stay in build records, not the runtime package. Source/content
approval does not establish runtime success, scientific adequacy or Agent benefit.

Binary support assets may be delivered when useful and source/license conditions are understood. Do not treat all resources as UTF-8 text. Candidate scope and file organization may evolve with evidence; record meaningful adjustments outside runtime context. No server/Docker provisioning is performed.
