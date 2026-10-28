"""Three-state invalid-input classification and the separation of coverage from gaps.

``required`` needs a real rejection case. ``none_documented`` is a recorded absence:
examined materials by fingerprint, scope, reason, limitation and an independent
confirmation, never a quotation standing in for proof. ``not_applicable`` needs an
operation without caller-supplied input. Requirement and verification are separate
outputs, and a stated obligation can never be traded for a recorded gap.
"""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from creation_pipeline.runtime import planner, preparation
from creation_pipeline.runtime.acceptance import contracts, input_contract, materials_digest
from creation_pipeline.runtime.coverage import acceptance_coverage

DOC = 'The tool reports terminal fragments for one SMILES string.\n'
ENTRY = '# terminal fragments report\nif len(sys.argv) > 2 or not smiles.strip():\n    raise SystemExit(2)\n'
PATH = 'entry/skill.py'


def make_source(root):
    (root / 'entry').mkdir(parents=True, exist_ok=True)
    (root / 'entry/skill.py').write_text(ENTRY, encoding='utf-8', newline='\n')
    (root / 'package').mkdir(parents=True, exist_ok=True)
    (root / 'package/SKILL.md').write_text(DOC, encoding='utf-8', newline='\n')


def material(path, root):
    raw = (root / path).read_bytes()
    return {'source_path': path, 'sha256': hashlib.sha256(raw).hexdigest()}


def assertion(purpose):
    role = {'computation': 'completion', 'operation': 'result', 'report': 'report',
            'input_rejection': 'rejection'}[purpose]
    return {'role': role, 'kind': 'stdout_equals', 'value': 'ok',
            'source_path': PATH, 'source_quote': 'terminal fragments'}


def case(name, purpose, args, exit_code, violates=None):
    contract = {'purpose': purpose, 'source_path': PATH, 'source_quote': 'terminal fragments',
                'assertion': assertion(purpose)}
    if violates:
        contract.update(violates=violates, invalid_input_reason='blank SMILES cannot be decomposed')
    return {'name': name, 'layer': 'interface', 'kind': 'reference', 'oracle_status': 'supported',
            'tolerance': 0, 'source_paths': [PATH], 'limitations': [],
            'args': args, 'expected_exit': exit_code, 'acceptance': contract}


def check(name='nonempty', key=0):
    return {'id': name, 'channel': 'args', 'key': key, 'pattern': r'(?s).*\S.*',
            'source_path': PATH, 'source_quote': 'not smiles.strip()'}


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        make_source(self.root)
        self.index = {'files': {PATH: {'size': 1, 'sha256': material(PATH, self.root)['sha256']}},
                      'read_files': [PATH]}

    def classification(self, record):
        return input_contract(record, self.index, self.root)

    def absent(self, **overrides):
        record = {'status': 'none_documented', 'reason': 'No rejection contract is documented',
                  'scope': 'the delivered entry and the upstream source',
                  'limitation': 'invalid input behavior is therefore unverified',
                  'checked': [material(PATH, self.root)]}
        record['review'] = {'status': 'confirmed', 'reviewer': 'independent-review',
                            'materials_sha256': materials_digest(record['checked'])}
        record.update(overrides)
        return record

    def test_required_needs_the_constraint_text(self):
        self.assertEqual(self.classification({'status': 'required', 'constraint': 'nonempty SMILES'}),
                         'required')
        with self.assertRaises(ValueError) as caught:
            self.classification({'status': 'required', 'constraint': ' '})
        self.assertIn('must identify the input constraint', str(caught.exception))

    def test_an_unknown_state_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.classification({'status': 'probably'})
        self.assertIn('none_documented', str(caught.exception))

    def test_a_recorded_absence_is_accepted_only_with_a_bound_confirmation(self):
        self.assertEqual(self.classification(self.absent()), 'none_documented')
        for field in ('reason', 'scope', 'limitation', 'checked', 'review'):
            record = self.absent()
            record.pop(field)
            with self.assertRaises(ValueError, msg=field) as caught:
                self.classification(record)
            self.assertIn('none_documented', str(caught.exception), field)

    def test_the_confirmation_must_be_bound_to_the_examined_materials(self):
        record = self.absent()
        record['review'] = dict(record['review'], materials_sha256='0' * 64)
        with self.assertRaises(ValueError) as caught:
            self.classification(record)
        self.assertIn('not bound to the examined materials', str(caught.exception))

    def test_checked_materials_must_be_read_and_match_their_fingerprint(self):
        unread = self.absent(checked=[{'source_path': 'package/SKILL.md', 'sha256': '0' * 64}])
        with self.assertRaises(ValueError) as caught:
            self.classification(unread)
        self.assertIn('was never read', str(caught.exception))
        wrong = self.absent(checked=[{'source_path': PATH, 'sha256': '0' * 64}])
        with self.assertRaises(ValueError) as caught:
            self.classification(wrong)
        self.assertIn('fingerprint does not match', str(caught.exception))

    def test_a_quotation_is_optional_context_and_never_a_substitute(self):
        quoted = self.absent(context={'source_path': PATH, 'source_quote': 'raise SystemExit(2)'})
        self.assertEqual(self.classification(quoted), 'none_documented')
        fake = self.absent(context={'source_path': PATH, 'source_quote': 'no rule here'})
        with self.assertRaises(ValueError) as caught:
            self.classification(fake)
        self.assertIn('never proves absence', str(caught.exception))

    def test_not_applicable_needs_a_reason(self):
        self.assertEqual(self.classification({'status': 'not_applicable', 'reason': 'fixed example'}), 'not_applicable')
        with self.assertRaises(ValueError):
            self.classification({'status': 'not_applicable'})

    def _plan(self, policy):
        return {'acceptance_json': json.dumps(policy)}

    def test_the_policy_field_must_agree_with_the_per_operation_aggregate(self):
        policy = {'invalid_input': 'required', 'scope': 'CLI', 'purposes': ['computation'],
                  'source_path': PATH, 'source_quote': 'terminal fragments',
                  'operations': [{'id': 'cli', 'selector': {'args': [{'index': 0, 'equals': 'terminal'}]},
                                  'checks': [], 'purposes': ['computation'], 'require_persistence': False,
                                  'input_contract': {'status': 'not_applicable', 'reason': 'fixed'},
                                  'source_path': PATH, 'source_quote': 'terminal fragments report'}]}
        with self.assertRaises(ValueError) as caught:
            contracts(self._plan(policy), [], self.index, self.root)
        self.assertIn('must equal the per-operation aggregate', str(caught.exception))
        policy['invalid_input'] = 'not_applicable'
        self.assertEqual(contracts(self._plan(policy), [], self.index, self.root)['invalid_input'],
                         'not_applicable')

    def test_every_operation_must_classify_itself(self):
        policy = {'invalid_input': 'required', 'scope': 'CLI', 'purposes': ['computation'],
                  'source_path': PATH, 'source_quote': 'terminal fragments',
                  'operations': [{'id': 'a', 'selector': {'args': [{'index': 0, 'equals': '--smiles'}]},
                                  'checks': ['nonempty'], 'purposes': ['computation'], 'require_persistence': False,
                                  'input_contract': {'status': 'required', 'constraint': 'nonempty'},
                                  'source_path': PATH, 'source_quote': 'terminal fragments'},
                                 {'id': 'b', 'selector': {'args': [{'index': 0, 'equals': '--file'}]},
                                  'checks': ['nonempty'], 'purposes': ['computation'], 'require_persistence': False,
                                  'source_path': PATH, 'source_quote': 'terminal fragments'}],
                  'checks': [check()]}
        with self.assertRaises(ValueError) as caught:
            contracts(self._plan(policy), [], self.index, self.root)
        self.assertIn('must classify its own invalid-input contract', str(caught.exception))


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        make_source(self.root)
        self.index = {'files': {PATH: {'sha256': material(PATH, self.root)['sha256']}},
                      'read_files': [PATH]}

    def policy(self, status, **extra):
        policy = {'invalid_input': status, 'scope': 'one nonempty SMILES argument',
                  'purposes': ['computation'], 'source_path': PATH,
                  'source_quote': 'terminal fragments',
                  'checks': [check()], 'constraint': 'nonempty SMILES'}
        if status == 'none_documented':
            policy.pop('constraint')
            policy['checks'] = []
        if status == 'not_applicable':
            policy.pop('constraint')
            policy['checks'] = []
        policy.update(extra)
        return policy

    def tool(self, policy, anchors=None):
        return {'entrypoint': ['python', '/opt/skill/entry/skill.py'], 'behavior': {'file_io': False},
                'acceptance_version': 2, 'acceptance_policy': policy, 'input_anchors': anchors or {}}

    def absent_policy(self):
        checked = [material(PATH, self.root)]
        return self.policy('none_documented', input_contract={
            'status': 'none_documented', 'reason': 'nothing documents a rejection contract',
            'scope': 'delivered entry and upstream source', 'checked': checked,
            'limitation': 'invalid input stays unverified',
            'review': {'status': 'confirmed', 'reviewer': 'independent-review',
                       'materials_sha256': materials_digest(checked)}})

    def test_a_declared_required_needs_a_rejection_like_the_legacy_form(self):
        policy = self.policy('required', input_contract={'status': 'required',
                                                          'constraint': 'nonempty SMILES'})
        result = acceptance_coverage(self.tool(policy), [case('ok', 'computation', ['CCO'], 0)])
        self.assertFalse(result['coverage_complete'])
        self.assertIn('Missing actual invalid-input rejection: nonempty', result['reasons'])

    def test_checks_cannot_be_carried_by_a_non_required_state(self):
        policy = self.policy('none_documented', input_contract={
            'status': 'none_documented', 'reason': 'r', 'scope': 's', 'limitation': 'l',
            'checked': [{'source_path': PATH, 'sha256': self.index['files'][PATH]['sha256']}],
            'review': {'status': 'confirmed', 'reviewer': 'x', 'materials_sha256':
                       materials_digest([{'source_path': PATH,
                                          'sha256': self.index['files'][PATH]['sha256']}])}})
        policy['checks'] = [check()]
        with self.assertRaises(ValueError) as caught:
            contracts({'acceptance_json': json.dumps(policy)}, [], self.index, self.root)
        self.assertIn('must be required', str(caught.exception))

    def test_required_with_rejection_is_coverage_complete_and_has_no_gap(self):
        cases = [case('ok', 'computation', ['CCO'], 0), case('blank', 'input_rejection', ['  '], 2,
                                                            violates='nonempty')]
        result = acceptance_coverage(self.tool(self.policy('required')), cases)
        self.assertTrue(result['coverage_complete'], result)
        self.assertTrue(result['complete'], result)
        self.assertEqual(result['validation_gaps'], [])
        self.assertEqual(result['blockers'], [])

    def test_required_without_rejection_is_incomplete(self):
        result = acceptance_coverage(self.tool(self.policy('required')), [case('ok', 'computation', ['CCO'], 0)])
        self.assertFalse(result['coverage_complete'])
        self.assertFalse(result['complete'])
        self.assertIn('Missing actual invalid-input rejection: nonempty', result['reasons'])

    def test_a_recorded_absence_completes_coverage_and_reports_the_gap(self):
        result = acceptance_coverage(self.tool(self.absent_policy()), [case('ok', 'computation', ['CCO'], 0)])
        self.assertTrue(result['coverage_complete'], result)
        self.assertTrue(result['complete'], result)
        self.assertEqual(len(result['validation_gaps']), 1)
        gap = result['validation_gaps'][0]
        self.assertEqual(gap['status'], 'none_documented')
        self.assertEqual(gap['reviewer'], 'independent-review')
        self.assertEqual(gap['materials_sha256'], materials_digest(gap['checked'])) if 'checked' in gap else None
        self.assertTrue(gap['limitation'])

    def test_a_stated_obligation_cannot_be_traded_for_a_recorded_absence(self):
        result = acceptance_coverage(self.tool(self.absent_policy(), {'forbids_none_documented': True,
                                                                     'basis': 'the caller requires invalid-input verification'}),
                                     [case('ok', 'computation', ['CCO'], 0)])
        self.assertTrue(result['coverage_complete'])
        self.assertFalse(result['complete'])
        self.assertTrue(result['blockers'])
        self.assertIn('none_documented cannot waive it', result['blockers'][0])

    def test_not_applicable_is_refused_for_an_operation_with_supplied_input(self):
        policy = self.policy('not_applicable',
                             input_contract={'status': 'not_applicable', 'reason': 'fixed example'})
        result = acceptance_coverage(self.tool(policy), [case('ok', 'computation', ['CCO'], 0)])
        self.assertFalse(result['complete'])
        self.assertIn('without supplied user input', result['blockers'][0])

    def test_not_applicable_is_accepted_for_a_fixed_example(self):
        policy = self.policy('not_applicable',
                             input_contract={'status': 'not_applicable', 'reason': 'fixed example'})
        result = acceptance_coverage(self.tool(policy), [case('ok', 'computation', [], 0)])
        self.assertTrue(result['complete'], result)
        self.assertEqual(result['validation_gaps'], [])

    def test_per_operation_states_are_judged_independently(self):
        policy = {'invalid_input': 'required', 'scope': 'two input forms', 'purposes': ['computation', 'operation'],
                  'source_path': PATH, 'source_quote': 'terminal fragments',
                  'checks': [check('text', key=1)],
                  'operations': [
                      {'id': 'direct', 'selector': {'args': [{'index': 0, 'equals': '--smiles'}]},
                       'checks': ['text'], 'purposes': ['computation'], 'require_persistence': False,
                       'input_contract': {'status': 'required', 'constraint': 'nonempty SMILES'},
                       'source_path': PATH, 'source_quote': 'terminal fragments'},
                      {'id': 'file', 'selector': {'args': [{'index': 0, 'equals': '--file'}]},
                       'checks': [], 'purposes': ['operation'], 'require_persistence': True,
                       'input_contract': {'status': 'not_applicable', 'reason': 'fixed reported example'},
                       'source_path': PATH, 'source_quote': 'terminal fragments'}]}
        cases = [case('direct-ok', 'computation', ['--smiles', 'CCO'], 0),
                 case('direct-blank', 'input_rejection', ['--smiles', '  '], 2, violates='text'),
                 case('file-ok', 'operation', ['--file'], 0)]
        cases[2]['output_file'] = 'fragments.json'
        result = acceptance_coverage(self.tool(policy), cases)
        self.assertEqual(result['operations']['direct']['invalid_input'], 'required')
        self.assertEqual(result['operations']['file']['invalid_input'], 'not_applicable')
        self.assertTrue(result['coverage_complete'], result)
        self.assertTrue(result['complete'], result)


class AnchorTests(unittest.TestCase):
    def record(self, author_tests=None, requirement=None):
        return {'delivery': {'inputs': {
            'acceptance': {'payload': {'author_tests': author_tests or {}}},
            'requirement': requirement or {}}}}


    def test_a_delivered_rejection_check_is_an_obligation(self):
        anchors = preparation.input_anchors(self.record(
            author_tests={'configured': [{'name': 'blank', 'expected_exit': 2}]}))
        self.assertTrue(anchors['forbids_none_documented'])
        self.assertIn('blank', anchors['basis'])

    def test_a_stated_requirement_is_an_obligation(self):
        anchors = preparation.input_anchors(self.record(), ['document invalid input boundaries'])
        self.assertTrue(anchors['forbids_none_documented'])
        self.assertIn('invalid input', anchors['basis'])

    def test_a_silent_record_has_no_obligation(self):
        anchors = preparation.input_anchors(self.record(), ['package the tool'])
        self.assertFalse(anchors['forbids_none_documented'])
        self.assertEqual(anchors['basis'], '')

    def test_anchors_only_accumulate_across_a_revision(self):
        record = self.record(author_tests={'configured': [{'name': 'blank', 'expected_exit': 2}]})
        record['delivery']['inputs']['acceptance']['payload']['input_anchors'] = {
            'rejection_checks': ['blank'], 'requirement_matches': ['invalid input'],
            'forbids_none_documented': True, 'basis': 'earlier'}
        anchors = preparation.merged_anchors(record, ['package the tool'])
        self.assertTrue(anchors['forbids_none_documented'])
        self.assertIn('invalid input', anchors['requirement_matches'])
        self.assertIn('earlier', anchors['basis'])


class RecapScenarioTests(unittest.TestCase):
    """The RECAP case: the caller asked for invalid-input verification.

    The delivered entry takes one SMILES argument and its own error branch rejects a
    blank value, so ``required`` is the honest state. ``none_documented`` must not be
    an escape hatch for it, and a fixed-example tool is not forced to invent an
    interface that it does not have.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        make_source(self.root)

    def record(self, author_tests):
        return {'delivery': {'inputs': {
            'acceptance': {'payload': {'author_tests': author_tests}},
            'requirement': {'status': 'required', 'reason': 'Executable entry', 'citations': []}}}}

    def policy(self, status):
        checked = [material(PATH, self.root)]
        record = {'invalid_input': status, 'scope': 'one nonempty SMILES argument',
                  'purposes': ['computation'], 'source_path': PATH,
                  'source_quote': 'terminal fragments report', 'checks': [check()]}
        if status == 'required':
            record['constraint'] = 'a supplied argument must be nonempty text'
        else:
            record['checks'] = []
            record['input_contract'] = {
                'status': status, 'reason': 'no rejection contract is documented',
                'scope': 'delivered entry and upstream source', 'checked': checked,
                'limitation': 'invalid input stays unverified',
                'review': {'status': 'confirmed', 'reviewer': 'independent-review',
                           'materials_sha256': materials_digest(checked)}}
        return record

    def cases(self):
        return [case('terminal', 'computation', ['CCO'], 0),
                case('blank', 'input_rejection', ['  '], 2, violates='nonempty')]

    def tool(self, policy, anchors):
        return {'entrypoint': ['python', '/opt/skill/entry/skill.py'], 'behavior': {'file_io': False},
                'acceptance_version': 2, 'acceptance_policy': policy, 'input_anchors': anchors}

    def test_required_with_the_delivered_rejection_passes(self):
        anchors = preparation.input_anchors(
            self.record({'generated': [{'name': 'blank-rejected', 'expected_exit': 2}]}),
            ['document invalid input boundaries'])
        result = acceptance_coverage(self.tool(self.policy('required'), anchors), self.cases())
        self.assertTrue(result['complete'], result)

    def test_none_documented_cannot_rescue_the_same_case(self):
        anchors = preparation.input_anchors(
            self.record({'generated': [{'name': 'blank-rejected', 'expected_exit': 2}]}),
            ['document invalid input boundaries'])
        self.assertTrue(anchors['forbids_none_documented'])
        result = acceptance_coverage(self.tool(self.policy('none_documented'), anchors), self.cases())
        self.assertFalse(result['complete'])
        self.assertTrue(result['blockers'])
        self.assertIn('cannot waive it', result['blockers'][0])

    def test_a_fixed_example_tool_may_declare_not_applicable(self):
        anchors = preparation.input_anchors(self.record({}), ['document invalid input boundaries'])
        policy = self.policy('not_applicable')
        result = acceptance_coverage(self.tool(policy, anchors),
                                     [case('fixed', 'computation', [], 0)])
        self.assertTrue(result['complete'], result)
        self.assertEqual(result['validation_gaps'], [])


class GapConfirmationTests(unittest.TestCase):
    def policy(self):
        return {'invalid_input': 'none_documented',
                'input_contract': {'status': 'none_documented', 'reason': 'r', 'scope': 's',
                                   'limitation': 'l', 'checked': [{'source_path': PATH, 'sha256': 'a'}],
                                   'review': {'status': 'confirmed', 'reviewer': 'x',
                                              'materials_sha256': 'a'}}}

    def test_a_recorded_absence_needs_an_independent_review_artifact(self):
        with self.assertRaises(preparation.RuntimeBlocked) as caught:
            preparation.confirm_gaps(self.policy(), None)
        self.assertEqual(caught.exception.code, 'invalid_input_review_missing')
        preparation.confirm_gaps(self.policy(), {'review': {'status': 'pass'}})
        preparation.confirm_gaps({'invalid_input': 'required'}, None)


class DowngradeTests(unittest.TestCase):
    def plan(self, status):
        p = copy.deepcopy(json.loads(json.dumps(_PLAN_FIXTURE())))
        policy = json.loads(p['acceptance_json'])
        policy.update({'invalid_input': status})
        if status == 'required':
            policy['constraint'] = 'nonempty SMILES'
        else:
            policy.pop('constraint', None)
        p['acceptance_json'] = json.dumps(policy)
        return p

    def patch(self, base, policy):
        answer = {'action': 'patch', 'requested_files': [], 'reason': 'repair',
                  'operations': [{'op': 'replace', 'path': '/acceptance_json',
                                  'value_json': json.dumps(policy)}]}
        return planner.patch_plan(base, answer, False)

    def test_a_downgrade_without_evidence_is_rejected(self):
        base = self.plan('required')
        lowered = {'invalid_input': 'none_documented', 'scope': 'one SMILES argument',
                   'purposes': ['report'], 'source_path': PATH, 'source_quote': 'terminal fragments'}
        with self.assertRaises(planner.PlanningError) as caught:
            self.patch(base, lowered)
        self.assertIn('cannot downgrade', str(caught.exception))

    def test_a_downgrade_with_recorded_evidence_is_reported(self):
        base = self.plan('required')
        lowered = {'invalid_input': 'none_documented', 'scope': 'one SMILES argument',
                   'purposes': ['report'], 'source_path': PATH, 'source_quote': 'terminal fragments',
                   'input_contract': {'status': 'none_documented', 'reason': 'no contract documented',
                                      'scope': 'delivered entry', 'limitation': 'unverified',
                                      'checked': [{'source_path': PATH, 'sha256': 'a' * 64}],
                                      'review': {'status': 'confirmed', 'reviewer': 'review',
                                                 'materials_sha256': 'a' * 64}}}
        applied = self.patch(base, lowered)
        delta = planner.scope_delta(base, applied)
        self.assertEqual(delta['input_states'], {'tool': ['required', 'none_documented']})


def _PLAN_FIXTURE():
    from tests.pipeline.test_runtime_build import plan
    p = plan()
    policy = json.loads(p['acceptance_json'])
    policy.update({'invalid_input': 'required', 'constraint': 'nonempty SMILES',
                   'checks': [check()], 'source_path': 'sources/tool/main.py',
                   'source_quote': 'print("ok")', 'scope': 'one nonempty SMILES argument'})
    p['acceptance_json'] = json.dumps(policy)
    return p


if __name__ == '__main__':
    unittest.main()
