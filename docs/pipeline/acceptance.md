# Source and content acceptance

A ready Skill passes deterministic package checks and independent Agent content review. Target
tools, examples and scripts are not executed or installed. Missing local GPU/dependencies is not
a rejection reason. Exact numeric example outputs and runtime test definitions are not required.

The program checks metadata, package paths/links, file roles, possible literal credentials,
applicable Python script syntax, source locators and unchanged delivered files. These establish
mechanical properties, not semantic correctness. Markdown `python`/`py` fences also receive
host-Python AST diagnostics with file/line locations and parser version. These observations go to
the reviewer, without executing code or resolving imports; snippets and newer target syntax need
contextual judgment rather than an automatic rejection. Other language blocks are not parsed.

The reviewer starts from the delivered package and independently chooses material risks:
can an Agent start without the build context; does the actual usage path connect declared inputs
to promised results through correct interfaces, data and state; which content is necessary?
Explicit external source/setup entrypoints and relevant versions belong in the package, not just
build records. Writing rationale is not an approval verdict. Evidence helps locate originals.
Concrete concision edits preserve decision-changing pitfalls; fixes and affected relationships are
rechecked instead of merely confirming that a warning sentence was added.

For a source-build route, review includes the actual pinned build entrypoint and required
files/modules; a repository link alone does not establish an obtainable tool. Quantitative claims
are checked against material normalization, calibration and inference conditions. Correctly bounded
descriptive results remain valid. Blocking findings require concrete source evidence, and
source-backed rebuttals can retract a mistaken finding.

Each new review records a short usage_assessment: declared inputs/result, concrete operational
contribution and material remaining in-scope gaps. A nonempty field makes the judgment inspectable;
it does not prove that the judgment is sound or that Agent efficiency improves. Missing promised
operations can block approval; speculative optimization and style preferences do not. Historical
review records remain historical evidence and are not backfilled with unperformed assessments.

Writing basis is a concise map from content blocks to inspected source files/functions/pages.
The reviewer independently verifies it. Concrete blocking defects go to the writing Agent;
review-record format errors go back to the same review session, without editing the Skill.
Unchanged findings and material cannot trigger endless identical review calls.

Approved pure packages enter skills/name. Incomplete or rejected drafts remain local, with reasons.
There is no pending runtime-verification area or promotion workflow. Content approval is not
runtime proof, scientific certification or measured Agent improvement.
