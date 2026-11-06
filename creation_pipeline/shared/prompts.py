"""Stage-specific permissions and decisions for shared environment creation."""
ENVIRONMENT = """Investigate the candidate's tool environment from registered primary sources. Read code,
dependency files, official setup/version notes, and use scoped supplemental research for concrete gaps.
Return ready with evidence and exact resolved tool versions, or blocked with a concrete reason and
resume_when. Do not build Docker or run business code now. Choose reuse, compatible extension, or new
from the supplied catalog. For extension select environment_id AND environment_version; new plans use
an empty environment_version. Tools contain only upstream tools, runtimes and dependencies, never Skill
task implementations, examples or tests. An extension must preserve its parent's contracts. Supply
the complete text build context (Dockerfile, locks, scripts, patches as required), not references to
unavailable workspace files. Use one FROM stage; the host pins the actual base digest. Include all
image tools in extension plans. Tool probes are argv commands inside the image: assert the declared
version and basic usability (for example Python assertions), and required bundled resources' readability.
Each probe must print exactly one JSON object with observed "version" and optional "resources":
{"resource-name": true} after actually checking readability; the host checks these facts against requirements.
Do not claim a compatibility range was tested. resource usage describes actual acquisition and use.
Do not install on the host. Missing installation details require research, not imagined packages.
Separate consumer requirements from investigation: conditions contains only accelerator,
minimum_memory_gib (null if no established minimum), and network_required for task execution, not
image downloading/building. usage_notes contains only essential user-facing conditions that cannot
be expressed in those fields (credentials, licenses, external acquisition constraints). Keep it empty
when none apply. Pinning history, source reading, failed attempts, probe/build details and unresolved
questions belong only in investigation_notes/unresolved, never usage_notes or resource usage.
evidence must contain only registered group-local eN IDs; put concrete inspected claims in investigation_notes.
Ready requires unresolved=[]; research source gaps with the existing supplement/search helper;
if inaccessible, return blocked with precise evidence and resume_when. evidence IDs must be local.
Prepared investigations are not successful images. Use their referenced prepared-plans.json record
for build materials rather than repeating research. Confirm candidate-specific differences and new
sources; when requirements already match, reuse those facts. Discovery version hints are provisional,
not installation proof. tools names and kinds are structured, never natural-language matching keys.
Feedback contains previous attempts: retry transient faults, otherwise explain and change the plan.
"""

REVIEW_EXTRA = """
Return execution_items for delivered code in Markdown and scripts. Give file and 1-based inclusive
line range selecting code only, without Markdown fences, a stable slug id, necessary, reason and
expected_check. Ordinary documented API calls, input/path substitutions and illustrative fragments
may be exempt after semantic review. Custom algorithms/formulas/decisions, nontrivial conversions,
parsing/index joins and multi-tool glue need execution. Location or mere loop syntax is not a reason.
Cover material code blocks/scripts with compact decisions; do not demand every path or numeric output.
This stage does not execute anything. Necessary-but-expensive is still necessary; defer later.
Ensure runtime.json and the one Docker section convey actual use, not internal build history.
"""

EXECUTION = """Prepare minimal validation for the supplied necessary execution items. Do not change or
execute the Skill. For each item provide exactly one case or a concrete external/cost deferral with
resume_when. Do not defer known code defects. Return ready even when all necessary cases are deferred.
Original code will be mounted read-only: full package /skill, extracted selected code at
/code/<item-id><suffix> (Python .py, Bash .sh, R .R); each item supplies suffix. Case files are written
under /work, and command/check_command are argv inside the Docker image. The command must explicitly
include the original /code path or /skill/<original-file>. Context wrappers receive that original path
as an argument and execute it without rewriting logic. Include expected exit plus meaningful stdout,
output artifacts or an asserting check_command. Cite the source-backed expected result in basis,
never fit expected values to observed output. Record all supplied context. For a partial snippet,
fixtures may set missing variables but must run the unchanged source. No network or host installation
is performed in this planning stage. Return blocked only for a demonstrated content defect
(blocked_owner=content) or a missing external prerequisite (blocked_owner=external). Correct fixture
mistakes yourself; never send them to the author. ready uses blocked_owner=none.
Report audit_risks honestly: context_injection for init_globals/runpy/trace injection; monkeypatch
for replaced functions; uncertain_oracle for an expectation needing source adjudication; complex_wrapper
for nontrivial dispatch. Simple direct script calls with data fixtures need none. Risky plans receive
independent audit; host checks the original path/coverage regardless. Do not insert user path rules
into the Skill to accommodate verifier fixtures.
"""

AUDIT = """Independently inspect the exact original code and proposed validation files/commands. Confirm
they exercise that code, supply legitimate context, check meaningful source-backed results, and do
not silently replace business logic or fabricate success. Confirm deferrals are genuine cost or
external conditions rather than ignored errors. Return pass only with no material defect; otherwise
fail with concrete reasons. Do not execute or change files."""

REPAIR = """Diagnose this failed stage using the attempt history and exact logs. Choose retry only for
a plausible transient issue; environment for dependency/build fixes, content for delivered defects,
test for fixture/oracle fixes. Infrastructure/connectivity/CLI/path/persistence errors must use
pipeline (or retry for a demonstrably transient operation), never content. For content fill
defect_location and defect_evidence with exact original code and source evidence; other actions use
empty strings for these fields. content requires an exact
original code location and source-backed defect, not a bad fixture. Give concrete reason and new_evidence_or_change (not 'try again').
If no viable action is available or an external prerequisite is missing, return blocked with a
specific resume_when. Do not change files or execute commands. Repeated error text alone does not
prove failure is permanent, but identical actions need a concrete transient explanation."""
