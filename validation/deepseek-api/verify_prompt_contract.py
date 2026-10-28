"""Offline audit: does the real prompt state exactly what the validators require?

Builds the same strings production sends (POLICY, the patch-protocol suffix, the plan
and patch schema descriptions, and the repair feedback), then checks that every rule
the validators enforce is stated somewhere the model can read, and that no superseded
statement survives. No model request is made.

Surfaces:
  plan policy / patch policy   the prompt body; must name the states and point at the
                               acceptance description, and patch rounds must state the
                               repair rules
  plan schema / patch schema   the schema text sent to the provider; carries the
                               acceptance description verbatim
  acceptance description       the authoritative detailed text (ACCEPTANCE_SPEC)
  repair feedback              the diagnostics a rejected plan receives next round
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from creation_pipeline.runtime import planner  # noqa: E402
from creation_pipeline.runtime import acceptance  # noqa: E402

# Every surface must name all three states.
STATES = list(acceptance.INPUT_STATES)
# The prompt body names the states and carries the shared contract block.
POLICY_POINTER = [
    ('three states named', ', '.join(STATES)),
    ('shared contract block', 'input_contract {status, ...}'),
    ('pointer to the description', 'acceptance_json schema description'),
    ('absence is evidence-bound', 'from an independent review that saw them'),
    ('obligation cannot be waived', 'never waives a requirement'),
]
# The authoritative description must carry every field the validator requires for each
# state, derived from the validator itself so a new rule cannot stay prompt-invisible.
DESCRIPTION = [
    ('separate requirement from verification', 'requirement and its verification are separate'),
    ('per-operation classification', 'input_contract'),
    ('required keeps the wrapper basis', 'delivered interface'),
    ('upstream silence does not waive', 'Upstream silence never waives a delivered promise'),
    ('checked materials with fingerprints', 'checked:[{source_path, sha256}]'),
    ('confirmation binding', 'materials_sha256'),
    ('context is optional and not proof', 'never proof of absence'),
    ('gap is not verification', 'reported as a validation gap'),
    ('not applicable is bounded', 'no caller-supplied business input'),
    ('fixed example is not forced', 'need not invent an input interface'),
    ('checks imply required', 'Only a required state may carry checks'),
    ('coverage output', 'coverage_complete'),
    ('gaps output', 'validation_gaps'),
    ('blockers output', 'blockers'),
    ('blocker is not a gap', 'never replaced by a recorded gap'),
    ('aggregate rule', 'strongest declared state'),
    ('per-operation rejection duty', 'declares its own input_contract'),
    ('repair evidence', 'A repair may correct a draft classification only with this recorded'),
]
for state in STATES:
    for field in acceptance.CONTRACT_FIELDS[state]:
        DESCRIPTION.append(('field %s.%s' % (state, field), field))
for field in acceptance.CONTRACT_LINKAGE:
    DESCRIPTION.append(('linkage field ' + field, field))
PATCH_PROTOCOL = [
    ('patch protocol', 'PATCH PROTOCOL'),
    ('nesting pointer form', '/acceptance_json/<pointer>'),
    ('repair evidence rule', 'by supplying that recorded evidence'),
    ('locked acceptance', 'no repair may touch a locked'),
    ('removal carries no value', 'remove operation carries no value_json'),
]
# Text that would contradict the current validators if it were still sent.
FORBIDDEN = [
    ('old two-state list', 'invalid_input (required or'),
    ('old two-state list, inline', 'required or\nnot_applicable)'),
    ('old blanket rejection rule', 'All listed operations require normal business cases'),
    ('forced whole-document replacement', 'must replace the whole /tests array'),
]


def normalize(text):
    """Compare prose without depending on line wrapping or JSON escaping."""
    return ' '.join(text.replace('\\n', ' ').split())


def find(text, needle):
    return normalize(needle) in normalize(text)


def patch_policy():
    return planner.POLICY + planner.patch_protocol(True)


def surfaces():
    parts = {
        'plan policy': planner.POLICY,
        'patch policy': patch_policy(),
        'plan schema': json.dumps(planner.PLAN_SCHEMA, ensure_ascii=False, sort_keys=True),
        'patch schema': json.dumps(planner.PATCH_SCHEMA, ensure_ascii=False, sort_keys=True),
        'acceptance description': planner.ACCEPTANCE_SPEC,
    }
    # What the `run` mode actually sends: a stale frozen copy would reintroduce the
    # exact "the model never saw the contract" failure this audit exists to prevent.
    frozen = Path(__file__).resolve().parent / 'frozen'
    if (frozen / 'prompt-0.txt').is_file():
        parts['frozen prompt'] = (frozen / 'prompt-0.txt').read_text(encoding='utf-8')
    if (frozen / 'schema.json').is_file():
        parts['frozen schema'] = (frozen / 'schema.json').read_text(encoding='utf-8')
    return parts


def audit(parts):
    problems = []
    for where, text in parts.items():
        for label, needle in FORBIDDEN:
            if find(text, needle):
                problems.append('%s: still says %s (%r)' % (where, label, needle))
        if where in ('plan policy', 'patch policy'):
            # The body carries the shared contract block, so the detailed rules apply.
            checks = DESCRIPTION + POLICY_POINTER
            if where == 'patch policy':
                checks += PATCH_PROTOCOL
        elif where == 'acceptance description':
            checks = DESCRIPTION + [('state named: ' + state, state) for state in STATES]
        elif where == 'frozen prompt':
            # Round zero has no patch protocol yet; it names the states, carries the
            # shared block and points at the description the frozen schema repeats.
            checks = DESCRIPTION + POLICY_POINTER
        elif where == 'frozen schema':
            checks = [('description carried', 'none_documented'),
                      ('checked materials carried', 'checked:[{source_path, sha256}]'),
                      ('confirmation binding', 'materials_sha256'),
                      ('coverage output', 'coverage_complete'),
                      ('per-operation duty', 'declares its own input_contract')]
        else:
            checks = [('description carried', 'none_documented'),
                      ('state named: required', 'required'),
                      ('state named: not_applicable', 'not_applicable'),
                      ('input_contract carried', 'input_contract')]
        for label, needle in checks:
            if not find(text, needle):
                problems.append('%s: missing %s (%r)' % (where, label, needle))
    return problems


def repair_feedback():
    """The diagnostics a rejected plan is actually given on the next round."""
    from tests.pipeline.test_runtime_build import plan
    texts = []

    def attempt(patch, base, locked):
        try:
            planner.patch_plan(base, patch, locked)
        except planner.PlanningError as exc:
            texts.append(str(exc))

    base = plan()
    policy = json.loads(base['acceptance_json'])
    policy.update({'invalid_input': 'required', 'constraint': 'nonempty SMILES'})
    base['acceptance_json'] = json.dumps(policy)
    lowered = dict(policy, invalid_input='none_documented')
    lowered.pop('constraint', None)
    attempt({'action': 'patch', 'requested_files': [], 'reason': 'r', 'operations': [
        {'op': 'replace', 'path': '/acceptance_json', 'value_json': json.dumps(lowered)}]}, base, False)
    attempt({'action': 'patch', 'requested_files': [], 'reason': 'r', 'operations': [
        {'op': 'replace', 'path': '/tests/0/case_json', 'value_json': json.dumps('x')}]}, base, True)
    return texts


def main():
    parts = surfaces()
    problems = audit(parts)
    feedback = repair_feedback()
    for text in feedback:
        if 'cannot downgrade' in text and 'evidence' not in text:
            problems.append('repair feedback: downgrade refusal does not ask for evidence')
        if 'cannot downgrade' not in text and 'locked' not in text.lower():
            problems.append('repair feedback: unexpected refusal text ' + text[:120])
    for where, text in parts.items():
        bad = [p for p in problems if p.startswith(where + ':')]
        print('%-24s %6d chars  %s' % (where, len(text), 'PROBLEM' if bad else 'ok'))
    print('repair feedback:')
    for text in feedback:
        print('  -', text[:150])
    if problems:
        print('\nPROBLEMS')
        for problem in problems:
            print('  -', problem)
        return 1
    print('\nevery validator rule is stated where the model can read it, and no '
          'superseded statement survives')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
