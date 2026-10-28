"""Migrated d5b77dc assertion/coverage/cleanup tests; Docker doubles are mechanism tests only.
Old publisher/schema fixtures were replaced by direct calls to the same migrated validators.
Individual test bodies retain their business assertions.
"""
import copy
import json
import os
import tempfile
import subprocess
from pathlib import Path
import unittest
from unittest.mock import patch
from creation_pipeline.runtime import planner, runner
from creation_pipeline.runtime.coverage import acceptance_coverage, input_check, select_usage_case
FIXTURE_DOC = 'Python CLI doubling n: print 2*n. Integer argument required; non-integer input raises ValueError on stderr and exits 1.'
def fixture_plan():
    def test(name, layer, args, **assertions):
        return dict(name=name, layer=layer, kind="derived", source_paths=["README.md"],
                    basis="README defines doubling; 2*3=6 independently", oracle_status="supported",
                    tolerance=0, limitations=["Tiny deterministic example only"],
                    case_json=json.dumps(dict(args=args, **assertions)))
    plan = dict(entrypoint=["python", "/opt/skill/cli.py"], script="cli.py", base_image="python:3.11-slim",
                platform="linux/amd64", language="python", language_version="3.11", source_files=["cli.py"],
                dependencies=[], steps=[], environment=[], resources=[], file_io=False, output_contract="decimal integer",
                runtime_network=False, network_reason="", choices=[dict(choice="Python 3.11", evidence="cli.py uses Python", certainty="inferred")],
                unresolved=[], unverified_behavior=["Only doubling is checked"], generated_files=[],
                tests=[test("environment", "environment", ["-c", "print('available')"], entrypoint="python", stdout_equals="available"),
                       test("interface", "interface", ["3"], stdout_equals="6"),
                       test("double", "behavior", ["3"], stdout_equals="6")])
    evidence = dict(source_path='README.md', source_quote=FIXTURE_DOC)
    plan['acceptance_json'] = json.dumps(dict(evidence, invalid_input='required', scope='integer doubling',
        purposes=['operation'], constraint='integer input', checks=[dict(evidence, id='integer', channel='args', key=0, pattern=r'-?[0-9]+')]))
    for entry in plan['tests'][1:]:
        case = json.loads(entry['case_json'])
        case['acceptance'] = dict(evidence, purpose='operation', assertion=dict(evidence, role='result', kind='stdout_equals', value='6'))
        entry['case_json'] = json.dumps(case)
    rejection = test('invalid-integer', 'interface', ['invalid'], expected_exit=1)
    case = json.loads(rejection['case_json'])
    case['acceptance'] = dict(evidence, purpose='input_rejection', violates='integer', invalid_input_reason='invalid is not an integer',
        assertion=dict(evidence, role='rejection', kind='stderr_contains', value='ValueError'))
    rejection['case_json'] = json.dumps(case)
    plan['tests'].append(rejection)
    return plan

class MigratedFixture(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root=Path(temp.name); self.source=self.root/'source'; self.source.mkdir()
        self.skill=self.root/'delivery'; self.skill.mkdir()
        (self.source/'cli.py').write_text('import sys\nprint(int(sys.argv[1])*2)\n',encoding='utf-8')
        (self.source/'README.md').write_text(FIXTURE_DOC,encoding='utf-8')
        self.plan=fixture_plan()
        self.plan['build_layout']={'dependency_files':[],'prefix_steps':0,'reason':'Conservative fixture'}
        self.plan['resource_assessment']={'status':'complete','source_path':'README.md','source_quote':FIXTURE_DOC,'memory_bytes':0,'cpus':1}

    def generated(self):
        cases,_,_=planner.validate_plan(self.plan,planner.inventory(self.source,planner.options({})),self.source)
        return {'entrypoint':self.plan['entrypoint'],'acceptance_version':2,'acceptance_policy':json.loads(self.plan['acceptance_json']),
                'behavior':{'file_io':self.plan['file_io']}},cases

    def assert_prelock_incomplete(self):
        with self.assertRaises((planner.AcceptancePlanError, planner.PlanningError, ValueError)):
            self.generated()


DOC_test_acceptance_v2 = ('Integer input is required; non-integer input prints invalid with exit 7. '
       'For input 3 the result is 6. '
       'The completed field is true when calculation completed, including uncertain results; '
       'runtime failures set completed false. '
       'This no-input report operation has no user-controlled input.')

class AcceptanceV2Tests(MigratedFixture):
    def setUp(self):
        super().setUp()
        self.plan['tests'] = self.plan['tests'][:3]
        (self.source / 'README.md').write_text(DOC_test_acceptance_v2, encoding='utf-8')
        self.policy = dict(invalid_input='required', scope='integer doubling', purposes=['operation'],
                           constraint='integer argument', source_path='README.md', source_quote=DOC_test_acceptance_v2,
                           checks=[dict(id='integer', channel='args', key=0, pattern=r'-?[0-9]+',
                                        source_path='README.md', source_quote=DOC_test_acceptance_v2)])
        self.plan['acceptance_json'] = json.dumps(self.policy)
        for i in (1, 2):
            case = json.loads(self.plan['tests'][i]['case_json'])
            case['acceptance'] = self.contract('operation', 'result', '6')
            self.plan['tests'][i]['case_json'] = json.dumps(case)
        negative = copy.deepcopy(self.plan['tests'][2])
        negative['name'] = 'reject-invalid'
        contract = self.contract('input_rejection', 'rejection', 'invalid')
        contract.update(violates='integer', invalid_input_reason='abc fails the integer grammar')
        negative['case_json'] = json.dumps(dict(args=['abc'], expected_exit=7, stdout_equals='invalid', acceptance=contract))
        self.plan['tests'].append(negative)
        self.plan["resource_assessment"]["source_quote"] = DOC_test_acceptance_v2

    def contract(self, purpose, role, value):
        return dict(purpose=purpose, source_path='README.md', source_quote=DOC_test_acceptance_v2,
                    assertion=dict(role=role, kind='stdout_equals', value=value, source_path='README.md', source_quote=DOC_test_acceptance_v2))

    def test_completed_uncertain_vs_runtime_failure(self):
        tool, cases = self.generated()
        case = copy.deepcopy(cases[2]); case.pop('stdout_equals')
        case['acceptance']['purpose'] = 'computation'
        case['acceptance']['assertion'] = dict(kind='json', role='completion', path=['completed'],
                                               allowed_values=[True], source_path='README.md', source_quote=DOC_test_acceptance_v2)
        for completed, expected in [(False, 'failed'), (True, 'passed')]:
            receipt = dict(exit_code=0, stdout=json.dumps(dict(completed=completed, result='inconclusive',
                           detail='execution_error' if not completed else 'legitimate uncertain result')), stderr='')
            with patch.object(runner, 'run', return_value=receipt):
                self.assertEqual(runner.run_case(self.skill, tool, 'image', case)['status'], expected)

    def test_no_global_error_string_heuristic(self):
        tool, cases = self.generated()
        case = copy.deepcopy(cases[2]); case.pop('stdout_equals')
        case['acceptance']['assertion']['value'] = 'execution_error is a documented word'
        with patch.object(runner, 'run', return_value=dict(exit_code=0, stdout='execution_error is a documented word', stderr='')):
            self.assertEqual(runner.run_case(self.skill, tool, 'image', case)['status'], 'passed')

    def test_actual_negative_rejection_exit_seven(self):
        tool, cases = self.generated()
        with patch.object(runner, 'run', return_value=dict(exit_code=7, stdout='invalid', stderr='')):
            self.assertEqual(runner.run_case(self.skill, tool, 'image', cases[-1])['status'], 'passed')
        with patch.object(runner, 'run', return_value=dict(exit_code=7, stdout='unrelated crash', stderr='')):
            self.assertEqual(runner.run_case(self.skill, tool, 'image', cases[-1])['status'], 'failed')
        zero_exit_contract = dict(cases[-1], expected_exit=0)
        with patch.object(runner, 'run', return_value=dict(exit_code=0, stdout='invalid', stderr='')):
            self.assertEqual(runner.run_case(self.skill, tool, 'image', zero_exit_contract)['status'], 'passed')

    def test_missing_result_contract_cannot_claim_computation(self):
        self.policy['purposes'] = ['computation']; self.plan['acceptance_json'] = json.dumps(self.policy)
        for i in (1, 2):
            case = json.loads(self.plan['tests'][i]['case_json']); case.pop('acceptance')
            self.plan['tests'][i]['case_json'] = json.dumps(case)
        self.assert_prelock_incomplete()

    def test_missing_negative_final_state_incomplete(self):
        self.plan['tests'].pop()
        self.assert_prelock_incomplete()

    def test_only_negative_has_no_normal_example(self):
        for i in (1, 2):
            case = json.loads(self.plan['tests'][i]['case_json']); case.pop('acceptance')
            self.plan['tests'][i]['case_json'] = json.dumps(case)
        self.assert_prelock_incomplete()

    def test_labels_do_not_make_valid_input_negative(self):
        case = json.loads(self.plan['tests'][-1]['case_json']); case['args'] = ['3']
        self.plan['tests'][-1]['case_json'] = json.dumps(case)
        self.assert_prelock_incomplete()

    def test_only_negative_file_tool_is_incomplete_without_usage(self):
        self.plan['file_io'] = True
        negative = self.plan['tests'][-1]
        negative['layer'] = 'interface'
        case = json.loads(negative['case_json'])
        case.update(output_file='report.txt', capture_stdout=True, input_files={'invalid.txt':'abc'})
        negative['case_json'] = json.dumps(case)
        self.plan['tests'] = [self.plan['tests'][0], negative]
        self.assert_prelock_incomplete()

    def test_not_applicable_requires_source_and_scope(self):
        self.policy.update(invalid_input='not_applicable', checks=[], scope='no-input report', purposes=['report'])
        self.plan['acceptance_json'] = json.dumps(self.policy)
        self.plan['tests'].pop()
        self.plan['tests'] = [self.plan['tests'][0], self.plan['tests'][2]]
        self.plan['entrypoint'] = ['python', '-c', 'print(6)']
        case = json.loads(self.plan['tests'][1]['case_json']); case['args'] = []
        case['acceptance']['purpose'] = 'report'; case['acceptance']['assertion']['role'] = 'report'
        self.plan['tests'][1]['layer'] = 'interface'
        self.plan['tests'][1]['case_json'] = json.dumps(case)
        tool, cases = self.generated()
        self.assertTrue(acceptance_coverage(tool, cases)['complete'])
        bad = copy.deepcopy(self.plan); policy = dict(self.policy, source_quote='invented exemption')
        bad['acceptance_json'] = json.dumps(policy)
        with self.assertRaises(ValueError): planner.validate_plan(bad, planner.inventory(self.source, planner.options({})), self.source)

    def test_computation_scope_cannot_be_satisfied_by_report(self):
        self.policy['purposes'] = ['computation']; self.plan['acceptance_json'] = json.dumps(self.policy)
        self.assert_prelock_incomplete()

    def test_contract_and_input_policy_locked(self):
        tool, cases = self.generated()
        changed = copy.deepcopy(self.plan); policy = dict(self.policy, invalid_input='not_applicable')
        changed['acceptance_json'] = json.dumps(policy)
        with self.assertRaisesRegex(ValueError, 'locked'):
            planner.validate_plan(changed, planner.inventory(self.source, planner.options({})), self.source, cases)
        changed = copy.deepcopy(self.plan); case = json.loads(changed['tests'][2]['case_json'])
        case['acceptance']['assertion']['value'] = 'wrong'; changed['tests'][2]['case_json'] = json.dumps(case)
        with self.assertRaisesRegex(ValueError, 'locked'):
            planner.validate_plan(changed, planner.inventory(self.source, planner.options({})), self.source, cases)


DOC_test_runtime_interfaces = ('Use --value with an integer, or --file with one integer per line; --out persists the result. '
       'Non-integer input is rejected with invalid and exit 7. Normal completion emits 6. '
       'Both operations are business calculations, not environment probes.')

class InterfaceTests(MigratedFixture):
    def configure(self, forms=('direct', 'file')):
        (self.source/'README.md').write_text(DOC_test_runtime_interfaces)
        evidence = dict(source_path='README.md', source_quote=DOC_test_runtime_interfaces)
        checks = []
        operations = []
        tests = [self.plan['tests'][0]]
        for form in forms:
            is_file = form == 'file'
            checks.append(dict(evidence, id=form, channel='input_files' if is_file else 'args',
                               key='values.txt' if is_file else 1, pattern=r'-?[0-9]+',
                               **({'argument_index': 1, 'mode': 'each_line'} if is_file else {})))
            operations.append(dict(evidence, id=form, selector={'args':[{'index':0,'equals':'--file' if is_file else '--value'}]},
                                   checks=[form], purposes=['computation'], require_persistence=is_file))
            for bad in (False, True):
                contract = dict(evidence, purpose='input_rejection' if bad else 'computation',
                                assertion=dict(evidence, role='rejection' if bad else 'completion',
                                               kind='stdout_equals', value='invalid' if bad else '6'))
                if bad:contract.update(violates=form, invalid_input_reason='bad is not an integer')
                case = dict(args=['--value', 'bad' if bad else '3'], expected_exit=7 if bad else 0,
                            stdout_equals='invalid' if bad else '6', acceptance=contract)
                if is_file:
                    case.update(args=['--file','/input/values.txt','--out','/output/result.txt'],
                                input_files={'values.txt':'3\nbad\n' if bad else '3\n4\n'}, output_file='result.txt')
                tests.append(dict(name=form+('-bad' if bad else '-ok'), layer='interface' if form==forms[0] else 'behavior',
                                  kind='derived', source_paths=['README.md'], basis=DOC_test_runtime_interfaces, oracle_status='supported',
                                  tolerance=0, limitations=['Mechanism fixture only'], case_json=json.dumps(case)))
        self.policy = dict(evidence, invalid_input='required', scope='All declared input forms',
                           purposes=['computation'], constraint='integer input', checks=checks, operations=operations)
        self.plan.update(tests=tests, file_io='file' in forms, acceptance_json=json.dumps(self.policy))
        self.plan["resource_assessment"]["source_quote"] = DOC_test_runtime_interfaces

    def checked(self):
        cases, _, _ = planner.validate_plan(self.plan, planner.inventory(self.source, planner.options({})), self.source)
        tool = dict(acceptance_version=2, acceptance_policy=self.policy, entrypoint=self.plan['entrypoint'],
                    behavior={'file_io':self.plan['file_io']})
        return tool, cases

    def test_direct_only_file_only_and_combined(self):
        for forms in [('direct',),('file',),('direct','file')]:
            with self.subTest(forms=forms):
                self.configure(forms);tool,cases=self.checked()
                coverage=acceptance_coverage(tool,cases)
                self.assertTrue(coverage['complete'],coverage)
                self.assertEqual(set(coverage['operations']),set(forms))
                self.assertIn(select_usage_case(tool,cases)[0]['name'],coverage['normal_cases'])

    def test_multiline_one_invalid_row_and_binding_must_be_real(self):
        self.configure();tool,cases=self.checked();bad=next(c for c in cases if c['name']=='file-bad')
        check=self.policy['checks'][1]
        self.assertIs(input_check(bad,check,bad['args']),False)
        bad['args'][1]='/input/unrelated.txt'
        self.assertIsNone(input_check(bad,check,bad['args']))
        self.assertFalse(acceptance_coverage(tool,cases)['complete'])

    def test_no_case_label_can_exempt_actual_input(self):
        self.configure();tool,cases=self.checked()
        next(c for c in cases if c['name']=='file-ok')['input_files']['values.txt']='3\nbad\n'
        self.assertFalse(acceptance_coverage(tool,cases)['complete'])

    def test_each_operation_requires_distinct_rejection_outcome(self):
        self.configure();tool,cases=self.checked()
        bad=next(c for c in cases if c['name']=='file-bad')
        normal=next(c for c in cases if c['name']=='file-ok')
        bad['expected_exit']=normal['expected_exit']
        bad['acceptance']['assertion']=copy.deepcopy(normal['acceptance']['assertion'])
        coverage=acceptance_coverage(tool,cases)
        self.assertIn('rejection for file',coverage['operations']['file']['missing'])
        self.assertFalse(coverage['complete'])

    def test_probe_and_upstream_runner_cannot_cover_business_purpose(self):
        self.configure(('direct',));self.policy['purposes'].append('operation')
        self.plan['acceptance_json']=json.dumps(self.policy)
        case=json.loads(self.plan['tests'][0]['case_json'])
        case['acceptance']=dict(source_path='README.md',source_quote=DOC_test_runtime_interfaces,purpose='operation',
            assertion=dict(source_path='README.md',source_quote=DOC_test_runtime_interfaces,role='result',kind='stdout_equals',value='available'))
        self.plan['tests'][0]['case_json']=json.dumps(case)
        with self.assertRaises(planner.AcceptancePlanError):self.checked()

    def test_file_capability_does_not_hide_valid_direct_example(self):
        self.configure();tool,cases=self.checked()
        direct=[c for c in cases if c['name'].startswith('direct')]
        self.assertEqual(select_usage_case(tool,direct)[0]['name'],'direct-ok')
        self.assertFalse(acceptance_coverage(tool,direct)['complete'])


class HardeningTests(MigratedFixture):
    def test_owned_container_labels_are_propagated(self):
        with patch.dict(os.environ, {"SKILLNET_EXECUTION_SCOPE": "test-owned"}):
            command = runner.invocation({"behavior": {"file_io": False}}, "image", [], "name")
        self.assertIn("skillnet.scope=test-owned", command)

    def test_stdout_capture_is_explicit_and_preserves_file_checks(self):
        tool = {"behavior": {"file_io": True}}
        case = {"name": "stdout-tool", "args": ["/input/a.txt"], "input_files": {"a.txt": "abc"},
                "output_file": "sum.txt", "stdout_equals": "golden", "origin": "model_proposed", "basis": "reference"}
        with patch("creation_pipeline.runtime.runner.run", return_value={"exit_code": 0, "stdout": "golden\n", "stderr": ""}):
            old = runner.run_case(self.skill, tool, "image", case)
            captured = runner.run_case(self.skill, tool, "image", dict(case, capture_stdout=True))
        self.assertEqual(old["status"], "failed", "Missing tool-created files must remain a failure")
        self.assertEqual(captured["status"], "passed")
        self.assertEqual(captured["persisted_output"], "golden\n")
        with patch("creation_pipeline.runtime.runner.run", return_value={"exit_code": 0, "stdout": "wrong", "stderr": ""}):
            self.assertEqual(runner.run_case(self.skill, tool, "image", dict(case, capture_stdout=True))["status"], "failed")


class LinuxRuntimeTests(MigratedFixture):
    def test_cleanup_failure_retains_scope_for_recovery(self):
        with patch.object(runner.subprocess,'run',side_effect=OSError('endpoint unavailable')):
            observations=runner.cleanup_scope('owned-scope')
        self.assertEqual(observations[0]['phase'],'cleanup_failed')
        self.assertEqual(observations[0]['scope'],'owned-scope')

    @unittest.skipUnless(os.name=='posix','Native POSIX mode semantics')
    def test_new_output_is_explicitly_shared_despite_restrictive_umask(self):
        previous=os.umask(0o077)
        try:
            output=runner.output_directory(self.root/'shared-output')
        finally:os.umask(previous)
        self.assertEqual(output.stat().st_mode&0o7777,0o1777)

    @unittest.skipUnless(os.name=='posix','Native POSIX mode semantics')
    def test_existing_private_output_is_not_silently_widened(self):
        if os.getuid()==10001 or os.getgid()==10001:self.skipTest('Test assumes host differs from the container identity')
        output=self.root/'private-output';output.mkdir();output.chmod(0o700)
        with self.assertRaisesRegex(ValueError,'permissions were not changed'):
            runner.output_directory(output)
        self.assertEqual(output.stat().st_mode&0o777,0o700)
