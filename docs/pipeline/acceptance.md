# Source and content acceptance

A ready Skill passes deterministic package checks and independent Agent content review. Target
tools, examples and scripts are not executed or installed. Missing local GPU/dependencies is not
a rejection reason. Exact numeric example outputs and runtime test definitions are not required.

The program checks metadata, package paths/links, file roles, possible literal credentials,
applicable Python script syntax, source locators and unchanged delivered files. These establish
mechanical properties, not semantic correctness. It does not blindly parse every Markdown block.

The reviewer starts from the delivered package and independently chooses material risks:
can an Agent start without the build context; does the actual usage path connect declared inputs
to promised results through correct interfaces, data and state; which content is necessary?
Explicit external source/setup entrypoints and relevant versions belong in the package, not just
build records. Writing rationale is not an approval verdict. Evidence helps locate originals.
Concrete concision edits preserve decision-changing pitfalls; fixes and affected relationships are
rechecked instead of merely confirming that a warning sentence was added.

Writing basis is a concise map from content blocks to inspected source files/functions/pages.
The reviewer independently verifies it. Concrete blocking defects go to the writing Agent;
review-record format errors go back to the same review session, without editing the Skill.
Unchanged findings and material cannot trigger endless identical review calls.

Approved pure packages enter skills/name. Incomplete or rejected drafts remain local, with reasons.
There is no pending runtime-verification area or promotion workflow. Content approval is not
runtime proof, scientific certification or measured Agent improvement.
