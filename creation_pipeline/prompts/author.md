Write the complete English skill/tool files directly. The program saves their content
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
  frontmatter in SKILL.md; name must match the plan. A tool entity has no SKILL.md:
  supply its scripts/references and return empty coverage strings.
- coverage: {scope, io, usage, result_checks}. Each value is a short exact quotation
  from SKILL.md locating that information. These are author attestations, not a
  replacement for independent content review or execution.
- tests: proposed engineering checks, as an array. When no configured checks cover
  the candidate, provide at least one executable result assertion grounded in actual
  source tests/examples. A build needs these proposals even when execution is disabled;
  the host decides whether to run them. Do NOT return [] merely because no execution
  evidence already exists. If no trustworthy oracle can be found, explain that exact
  gap in notes, return [] and accept draft status. Each item has name,
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
Each check also has cwd: use "{run}" for the fresh isolated check directory unless
upstream requires a specific working directory. Use "{source:ID}" for a directory
source when a command reads adjacent files relative to cwd. Logs still go to {run};
do not write outputs into source snapshots. A cwd fix is a check invocation repair,
not an unavailable dependency or a reason to remove a failing assertion.

Always respect user_guidance and constraints, not only the plan's paraphrase.
Use compact real parameter/key lists or tables for numerous I/O fields; do not
copy the whole API. Separate CLI parse/setup failures, row errors and valid negatives.
Qualify guarantees such as "always JSON" unless all relevant paths support them.
Reuse shared tools at ../../tools/<name>/ from a skill directory. Compute paths
relative to __file__ in scripts, or document the skill directory as the working
directory for CLI examples. Never use build-cache absolute paths in runtime files.
External upstream sources remain external: document actual pinned acquisition,
not pipeline-only source macros. No new dependency environment/Docker configs.
Checks may use {bundle} for the common bundle root and {tool:NAME} for an approved
shared tool directory. Ground expected values in source evidence. Test actual
examples/results, including the shared call path, not just imports or --help.
If using an external repository script/module, include its actual usable repository
address and pinned revision in runtime instructions (or a linked required reference).
Saying only "acquire the upstream repository" is insufficient. For installed libraries
use their actual package/import prerequisites; do not invent a repository requirement.
