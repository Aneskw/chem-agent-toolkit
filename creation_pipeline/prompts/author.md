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
  frontmatter in SKILL.md; name must match the plan. Only skills are supported.
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
Preserve generated check names and expected assertions across repairs. Repair
argv/cwd when invocation is wrong. Assertions inspect stdout, not stderr: for
unittest output, use TextTestRunner(stream=sys.stdout) and propagate unsuccessful
results as a nonzero exit. Do not replace a failed expected output with incidental
observed output merely to pass.
Prefer running relevant existing upstream tests over retyping their fixtures.
When fixtures must be embedded, preserve source bytes including leading blank
lines and fixed-width columns; formatting damage is a test-input defect.
Each check also has cwd: use "{run}" for the fresh isolated check directory unless
upstream requires a specific working directory. Use "{source:ID}" for a directory
source when a command reads adjacent files relative to cwd. Logs still go to {run};
do not write outputs into source snapshots. A cwd fix is a check invocation repair,
not an unavailable dependency or a reason to remove a failing assertion.

Always respect user_guidance and constraints, not only the plan's paraphrase.
Use compact real parameter/key lists or tables for numerous I/O fields; do not
copy the whole API. Separate CLI parse/setup failures, row errors and valid negatives.
Qualify guarantees such as "always JSON" unless all relevant paths support them.
Do not reference sibling skills, shared tools or pipeline cache paths. Research extensions must reproduce source-supported behavior, not invent algorithms. Runtime examples need actual acquisition addresses/versions and adjacent resources when relevant.
Return issues: [{id, description, blocking, resolution}]. Unresolved required evidence/dependencies block readiness. All material notes must appear here. No self-declared scientific verification.
Prefer checking primary Python examples using argv ["{python}", "<absolute repository>/examples/verify_python_example.py", "{package}", ...] or the delivered Python statements as the -c argument, with source-grounded output assertions. If your result checks use different statements, the host separately executes all delivered Python blocks when execution is permitted. That completion check does not replace meaningful result assertions. Mark non-executable illustrative blocks as text. Tests need cwd.
