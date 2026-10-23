"""Interface-contract mechanisms with mocked planner/engine; no real chemistry."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_runtime_model as base
import runtime_model as planner
import runtime_model_lifecycle as lifecycle
import runtime_package as runner
from runtime_common import read, write, artifacts
from runtime_examples import select_usage_case, NoUsageCase
from workflow_state import batch_exit

DOC = ('Use --value with an integer, or --file with one integer per line; --out persists the result. '
       'Non-integer input is rejected with invalid and exit 7. Normal completion emits 6. '
       'Both operations are business calculations, not environment probes.')


class InterfaceTests(unittest.TestCase):
    setUp = base.ModelRuntimeTests.setUp
    generate = base.ModelRuntimeTests.generate

    def configure(self, forms=('direct', 'file')):
        (self.source/'README.md').write_text(DOC)
        evidence = dict(source_path='README.md', source_quote=DOC)
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
                                  kind='derived', source_paths=['README.md'], basis=DOC, oracle_status='supported',
                                  tolerance=0, limitations=['Mechanism fixture only'], case_json=json.dumps(case)))
        self.policy = dict(evidence, invalid_input='required', scope='All declared input forms',
                           purposes=['computation'], constraint='integer input', checks=checks, operations=operations)
        self.plan.update(tests=tests, file_io='file' in forms, acceptance_json=json.dumps(self.policy))

    def checked(self):
        cases, _, _ = planner.validate_plan(self.plan, planner.inventory(self.source, planner.options({})), self.source)
        tool = dict(acceptance_version=2, acceptance_policy=self.policy, entrypoint=self.plan['entrypoint'],
                    behavior={'file_io':self.plan['file_io']})
        return tool, cases

    def test_direct_only_file_only_and_combined(self):
        for forms in [('direct',),('file',),('direct','file')]:
            with self.subTest(forms=forms):
                self.configure(forms);tool,cases=self.checked()
                coverage=runner.acceptance_coverage(tool,cases)
                self.assertTrue(coverage['complete'],coverage)
                self.assertEqual(set(coverage['operations']),set(forms))
                self.assertIn(select_usage_case(tool,cases)[0]['name'],coverage['normal_cases'])

    def test_multiline_one_invalid_row_and_binding_must_be_real(self):
        self.configure();tool,cases=self.checked();bad=next(c for c in cases if c['name']=='file-bad')
        check=self.policy['checks'][1]
        self.assertIs(runner.input_check(bad,check,bad['args']),False)
        bad['args'][1]='/input/unrelated.txt'
        self.assertIsNone(runner.input_check(bad,check,bad['args']))
        self.assertFalse(runner.acceptance_coverage(tool,cases)['complete'])

    def test_no_case_label_can_exempt_actual_input(self):
        self.configure();tool,cases=self.checked()
        next(c for c in cases if c['name']=='file-ok')['input_files']['values.txt']='3\nbad\n'
        self.assertFalse(runner.acceptance_coverage(tool,cases)['complete'])

    def test_each_operation_requires_distinct_rejection_outcome(self):
        self.configure();tool,cases=self.checked()
        bad=next(c for c in cases if c['name']=='file-bad')
        normal=next(c for c in cases if c['name']=='file-ok')
        bad['expected_exit']=normal['expected_exit']
        bad['acceptance']['assertion']=copy.deepcopy(normal['acceptance']['assertion'])
        coverage=runner.acceptance_coverage(tool,cases)
        self.assertIn('rejection for file',coverage['operations']['file']['missing'])
        self.assertFalse(coverage['complete'])

    def test_probe_and_upstream_runner_cannot_cover_business_purpose(self):
        self.configure(('direct',));self.policy['purposes'].append('operation')
        self.plan['acceptance_json']=json.dumps(self.policy)
        case=json.loads(self.plan['tests'][0]['case_json'])
        case['acceptance']=dict(source_path='README.md',source_quote=DOC,purpose='operation',
            assertion=dict(source_path='README.md',source_quote=DOC,role='result',kind='stdout_equals',value='available'))
        self.plan['tests'][0]['case_json']=json.dumps(case)
        with self.assertRaises(planner.AcceptancePlanError):self.checked()

    def test_file_capability_does_not_hide_valid_direct_example(self):
        self.configure();tool,cases=self.checked()
        direct=[c for c in cases if c['name'].startswith('direct')]
        self.assertEqual(select_usage_case(tool,direct)[0]['name'],'direct-ok')
        self.assertFalse(runner.acceptance_coverage(tool,direct)['complete'])

    def test_no_example_is_not_metadata_damage(self):
        self.configure(('direct',));self.assertEqual(self.generate()['status'],'prepared')
        package=read(self.skill/'runtime/package.json');tool=package['tools']['double']
        target=self.skill/tool['context']/tool['fixtures'];cases=read(target)['cases']
        for c in cases:
            if c['name']=='direct-ok':c['args']=[]
        tool['acceptance_policy'].update(checks=[],operations=[])
        write(self.skill/'runtime/package.json',package)
        self.assertIn('direct-ok',runner.acceptance_coverage(tool,cases)['normal_cases'])
        with self.assertRaises(NoUsageCase):select_usage_case(tool,cases)
        write(target,{'cases':cases})
        write(self.skill/'runtime/examples.json',{'examples':lifecycle.examples(dict(package,_root=self.skill))})
        lifecycle.refresh_docs(self.skill,'validation_incomplete')
        self.assertIn('No verified normal invocation',(self.skill/'DOCKER.md').read_text())

    def test_real_missing_example_metadata_is_still_rejected(self):
        self.configure();self.assertEqual(self.generate()['status'],'prepared')
        path=self.skill/'runtime/examples.json';data=read(path)
        data['examples']=[e for e in data['examples'] if e['kind']!='usage'];write(path,data)
        with self.assertRaisesRegex(ValueError,'ownership'):lifecycle.refresh_docs(self.skill,'prepared')

    def test_incomplete_plan_feedback_bounded_and_prepared_record_saved(self):
        self.configure();self.plan['tests']=[t for t in self.plan['tests'] if t['name']!='file-bad']
        index=planner.inventory(self.source,planner.options({}))
        with patch.object(planner,'plan',return_value=(self.plan,index,'fixture')) as call:
            result=lifecycle.prepare(self.skill,'job',self.bindings)
        self.assertEqual(call.call_count,2)
        self.assertIn('acceptance_diagnostics',call.call_args.args[5])
        self.assertEqual(result['status'],'validation_incomplete')
        saved=read(self.skill/'runtime/prepared.json')
        self.assertEqual(saved['status'],'validation_incomplete')
        self.assertEqual(saved['tools'][0]['source_root'],str(self.source.resolve()))
        self.assertTrue(saved['tools'][0]['acceptance_diagnostics']['planning_attempts_exhausted'])
        self.assertEqual(read(self.skill/'runtime/package.json')['tools'],{})
        self.assertFalse(list(self.skill.glob('runtime/tools/*/context')))
        record=dict(status='method_drafts_created',candidate_count=1,execution_checks={'x':result['status']},
                    candidate_paths=[str(self.skill)],current_acceptance_validated=False)
        self.assertEqual(batch_exit([record],'execution'),2)

    def test_documentation_exception_leaves_durable_failed_preparation(self):
        self.configure()
        with patch.object(lifecycle,'refresh_docs',side_effect=ValueError('ownership damaged')):
            result=self.generate()
        self.assertEqual(result['status'],'needs_review')
        self.assertEqual(read(self.skill/'runtime/prepared.json')['failure_kind'],'documentation')
        self.assertEqual(result['artifacts'],artifacts(self.skill))
        self.assertTrue(all(t['status']=='needs_review' for t in result['tools']))

    def test_locked_operation_selector_and_line_rules_cannot_change(self):
        self.configure();_,cases=self.checked()
        self.policy['checks'][1]['mode']='full_text';self.plan['acceptance_json']=json.dumps(self.policy)
        with self.assertRaisesRegex(ValueError,'locked'):
            planner.validate_plan(self.plan,planner.inventory(self.source,planner.options({})),self.source,cases)

    def test_real_failed_plan_rejected_before_context_or_lock(self):
        fixture=Path(__file__).parent/'fixtures/atommap_failed_plan'
        plan=read(fixture/'plan.json');source=fixture/'source'
        with self.assertRaises(planner.AcceptancePlanError) as caught:
            planner.validate_plan(plan,planner.inventory(source,planner.options({})),source)
        self.assertIn('Declared purposes are not covered',str(caught.exception))

    def test_unsupported_operation_selector_source_is_rejected(self):
        self.configure();self.policy['operations'][0]['selector']['args'][0]['equals']='undocumented'
        self.plan['acceptance_json']=json.dumps(self.policy)
        with self.assertRaisesRegex(ValueError,'documented'):self.checked()

    def test_legitimate_negative_result_is_not_input_rejection_or_runtime_error(self):
        self.configure(('direct',));tool,cases=self.checked()
        business=copy.deepcopy(next(c for c in cases if c['name']=='direct-ok'))
        business.update(name='negative-result',expected_exit=2,stdout_equals='negative')
        business['acceptance']['assertion']['value']='negative'
        cases.append(business)
        coverage=runner.acceptance_coverage(tool,cases)
        self.assertEqual(coverage['completed_negative_cases'],['negative-result'])
        self.assertTrue(coverage['complete'])
        self.assertTrue(runner.output_matches(business,dict(exit_code=2,stdout='negative',stderr=''),'negative'))
        self.assertFalse(runner.output_matches(business,dict(exit_code=2,stdout='',stderr='runtime failed'),''))

    def test_prelock_patch_cannot_shrink_declared_scope(self):
        self.configure();smaller=copy.deepcopy(self.policy);smaller['operations'].pop()
        with self.assertRaisesRegex(ValueError,'cannot remove'):
            planner.patch_plan(self.plan,dict(action='patch',requested_files=[],reason='fixture',operations=[
                dict(op='replace',path='/acceptance_json',value_json=json.dumps(json.dumps(smaller)))]),False)

    def test_jsonl_rejection_asserts_actual_invalid_row_not_any_error_string(self):
        case={'acceptance':{'assertion':{'kind':'jsonl','record_index':1,'path':['reason'],
                                       'allowed_values':['invalid integer']}}}
        text='{"ok":true}\n{"ok":false,"reason":"invalid integer"}\n'
        self.assertTrue(runner.output_matches(case,{'stdout':text},text))
        for bad in ['{"reason":"invalid integer"}\n',
                    '{"reason":"invalid integer"}\n{"reason":"environment unavailable"}\n']:
            self.assertFalse(runner.output_matches(case,{'stdout':bad},bad))

    def test_changed_example_case_identity_is_rejected(self):
        self.configure();self.assertEqual(self.generate()['status'],'prepared')
        path=self.skill/'runtime/examples.json';data=read(path)
        next(e for e in data['examples'] if e['kind']=='usage')['case_id']='other-case'
        write(path,data)
        with self.assertRaisesRegex(ValueError,'ownership'):lifecycle.refresh_docs(self.skill,'prepared')

    def test_structured_prelock_feedback_can_repair_within_same_budget(self):
        self.configure();bad=copy.deepcopy(self.plan)
        bad['tests']=[t for t in bad['tests'] if t['name']!='file-bad']
        index=planner.inventory(self.source,planner.options({}))
        with patch.object(planner,'plan',side_effect=[(bad,index,'bad'),(self.plan,index,'added missing rejection')]) as call:
            result=lifecycle.prepare(self.skill,'job',self.bindings)
        self.assertEqual(result['status'],'prepared')
        self.assertEqual(call.call_count,2)
        self.assertTrue(call.call_args.args[5]['acceptance_diagnostics']['operations']['file']['missing'])
        self.assertEqual(len(list(self.skill.glob('runtime/tools/*/attempts/*/rejection.json'))),1)
