Write the complete English skill files directly. The program saves their content
verbatim; there is no fixed chapter renderer. Follow the supplied authoritative
minimum and packaging specifications. Four information requirements are semantic,
not required headings. Keep essential correctness in SKILL.md. A simple tool should
usually need only SKILL.md. Do not copy upstream repos or model weights. Do not put
build logs, evidence ledgers, test verdicts or benchmark questions in the runtime skill.
Declare external dependencies and real callable paths honestly. Paths in examples
must work after installation given the declared external prerequisites.

Return a JSON object in payload:
- files: [{path, content, purpose}]. Include the entire final file set, even on repair.
  Paths may be SKILL.md or below scripts/, references/, examples/, resources/, assets/.
  Every new file needs a real task-related purpose. Use YAML name and description
  frontmatter in SKILL.md; name must match the plan.
- coverage: {scope, io, usage, result_checks}. Each value is a short exact quotation
  from SKILL.md locating that information. These are author attestations, not a
  replacement for independent content review or execution.
- tests: optional proposed engineering checks, as an array. Each item has name,
  argv (array of arguments; no shell), expected_exit (integer), stdout_contains
  (array of literal strings), evidence (real read eN ID), purpose (nonempty string),
  and kind (positive, negative, or boundary). Use an empty array when configured
  checks already cover the task. Use {python}, {package}, {run}, {source:ID} macros.
  These macros are for check argv only; runtime skill examples must use real Python
  or documented CLI paths/options, never unresolved pipeline-only macros.
  Checks execute with a fresh {run} working directory. Propose meaningful tests, not
  just --help, imports, file existence or printing a desired string. Expected values
  must follow supplied source tests/examples or requirements, not the new code itself.
- notes: array of limitations or dependencies not demonstrated by checks.

User-configured checks are immutable. Generated checks are proposals and may not
be executed unless explicitly enabled. The program performs actual execution.
Never mark a runtime or scientific claim verified based on writing a test alone.
On feedback, repair the cause without weakening the task, oracles or configured
checks. If the plan's task/algorithm must change, report the limitation instead.
