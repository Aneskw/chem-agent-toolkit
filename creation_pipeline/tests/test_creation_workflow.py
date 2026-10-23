"""Mechanism coverage for source association, independent outcomes and continuation."""
import contextlib
import copy
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import candidate_identity as identity
import workflow_state
import inspect_run
import batch_pipeline
import publish_run
import runtime_model_lifecycle as lifecycle
import runtime_model as planner
import runtime_package as runner
from runtime_common import read,write
import test_runtime_model as base
from test_creation_contract import candidate,bundle


class AssociationTests(unittest.TestCase):
    setUp=base.ModelRuntimeTests.setUp
    generate=base.ModelRuntimeTests.generate

    def selector(self):
        write(self.skill/'candidate.json',identity.identity(candidate(),bundle(),'job'))
        self.settings['bindings']=[{'selector':{'job_id':'job','source_ids':['s1']},'requirement':'required','tools':['double']}]
        write(self.bindings,self.settings)

    def test_source_selector_needs_no_guessed_candidate_name(self):
        self.selector();self.skill=self.skill.rename(self.root/'unpredicted-name')
        path=self.skill/'SKILL.md';path.write_text(path.read_text().replace('name: example-procedure','name: unpredicted-name'))
        result=self.generate();self.assertEqual(result['status'],'prepared')
        self.assertEqual(result['association']['method'],'cited_source_selector')

    def test_identity_survives_name_change_but_not_source_or_job_change(self):
        a=candidate();b=copy.deepcopy(a);b['name']='renamed'
        self.assertEqual(identity.identity(a,bundle(),'job'),identity.identity(b,bundle(),'job'))
        self.assertNotEqual(identity.identity(a,bundle(),'job')['candidate_id'],identity.identity(a,bundle(),'other')['candidate_id'])
        other=bundle();other['sources'][0]['sha256']='changed'
        self.assertNotEqual(identity.identity(a,bundle(),'job')['candidate_id'],identity.identity(a,other,'job')['candidate_id'])

    def test_explicit_identity_selector_and_exact_binding_precedence(self):
        self.selector();value=identity.load(self.skill)
        self.settings['bindings'][0]['selector']={'job_id':'job','candidate_id':value['candidate_id']}
        self.settings['bindings'].append({'job_id':'job','candidate':self.skill.name,'requirement':'not_required','tools':[]})
        write(self.bindings,self.settings);self.assertEqual(self.generate()['status'],'not_required')

    def test_unrelated_tool_is_not_implicitly_bound(self):
        self.selector();self.settings['tools']['other']={'root':str(self.root/'missing')}
        self.settings['bindings'].append({'selector':{'job_id':'job','source_ids':['s2']},'requirement':'required','tools':['other']})
        write(self.bindings,self.settings);result=self.generate()
        self.assertEqual([t['tool_id'] for t in result['tools']],['double'])

    def test_any_source_selector_still_requires_a_cited_source(self):
        self.selector();self.settings['bindings'][0]['selector']={'job_id':'job','source_ids_any':['s2','s1']};write(self.bindings,self.settings)
        self.assertEqual(self.generate()['status'],'prepared')
        self.settings['bindings'][0]['selector']['source_ids_any']=['s2'];write(self.bindings,self.settings)
        self.assertIn('unresolved',self.generate()['error'])

    def test_ambiguous_bindings_do_not_union_tools(self):
        self.selector();self.settings['bindings']*=2;write(self.bindings,self.settings)
        with patch('model_call.call') as call:result=lifecycle.prepare(self.skill,'job',self.bindings)
        self.assertEqual(result['status'],'needs_review');self.assertIn('ambiguous',result['error']);call.assert_not_called()

    def test_job_wildcard_is_not_an_implicit_all_candidates_binding(self):
        self.selector();self.settings['bindings'][0]['selector']={'job_id':'job'};write(self.bindings,self.settings)
        with patch('model_call.call') as call:result=lifecycle.prepare(self.skill,'job',self.bindings)
        self.assertEqual(result['status'],'needs_review');self.assertIn('wildcard',result['error']);call.assert_not_called()

    def test_malformed_selector_is_a_reported_configuration_error(self):
        self.selector();self.settings['bindings'][0]['selector']='job';write(self.bindings,self.settings)
        with patch('model_call.call') as call:result=lifecycle.prepare(self.skill,'job',self.bindings)
        self.assertEqual(result['status'],'needs_review');self.assertIn('selector must be an object',result['error']);call.assert_not_called()

    def test_missing_identity_and_tampered_metadata_stop(self):
        self.selector();(self.skill/'candidate.json').unlink()
        self.assertIn('unresolved',self.generate()['error'])
        self.selector();value=read(self.skill/'candidate.json');value['source_ids']=['s2'];write(self.skill/'candidate.json',value)
        with patch('model_call.call') as call:result=lifecycle.prepare(self.skill,'job',self.bindings)
        self.assertIn('identity metadata',result['error']);call.assert_not_called()

    def test_invalid_positive_python_probe_is_rejected_before_locking(self):
        self.plan['tests'][0]['case_json']='{"entrypoint":"python","args":["-c","print(\\\"\\n\\\")"],"stdout_equals":"available"}'
        result=self.generate();self.assertEqual(result['status'],'needs_review');self.assertIn('probe syntax',result['tools'][0]['error'])

    def test_explicit_negative_and_non_python_arguments_are_not_rewritten(self):
        planner.check_probe_syntax({'entrypoint':'python','expected_exit':1,'args':['-c','print(\'\n\')']},[])
        planner.check_probe_syntax({'args':['-c','not Python code']},['python','tool.py'])
        with self.assertRaises(planner.PlanningError):planner.check_probe_syntax({'entrypoint':'python','args':['-c','print(\'\n\')']},[])


class ResourceReviewTests(unittest.TestCase):
    setUp=base.ModelRuntimeTests.setUp
    generate=base.ModelRuntimeTests.generate

    def blocked(self):
        self.plan['resources']=[{'kind':'weight','description':'Optional predictor not used by selected CLI','available':False,'evidence':'README'}]
        self.assertEqual(self.generate()['status'],'blocked_resources')

    def test_optional_unavailable_resource_is_recorded_without_inventing_availability(self):
        self.blocked()
        self.plan['resources'][0]['required_for_execution']=False
        self.assertEqual(self.generate()['status'],'prepared')
        plan=read(self.skill/'runtime/tools/double/environment_plan.json')
        self.assertFalse(plan['resources'][0]['available'])

    def test_legacy_missing_flag_and_explicit_required_remain_blocked(self):
        self.blocked()
        self.assertNotIn('required_for_execution',read(self.skill/'runtime/tools/double/environment_plan.json')['resources'][0])
        self.plan['resources'][0]['required_for_execution']=True
        self.assertEqual(self.generate()['status'],'blocked_resources')
        self.plan['resources'][0]['required_for_execution']='no'
        self.assertEqual(self.generate()['status'],'needs_review')

    def test_review_uses_model_patch_and_locks_tests_and_archives_first_plan(self):
        self.blocked();original=read(self.skill/'runtime/tools/double/provenance.json')['cases']
        response={'action':'patch','requested_files':[],'reason':'Source proves predictor is outside CLI scope',
                  'operations':[{'op':'add','path':'/resources/0/required_for_execution','value_json':'false'}]}
        with patch('model_call.call',return_value=(response,{'model':'fake'})) as call:
            result=lifecycle.prepare(self.skill,'job',self.bindings,review_blocked=True)
        self.assertEqual(result['status'],'prepared');self.assertEqual(call.call_count,1)
        self.assertEqual(result['tools'][0]['locked_cases'],original)
        saved=self.skill/result['resource_review']['previous_runtime']
        self.assertEqual(read(saved/'prepared.json')['status'],'blocked_resources')
        self.assertNotIn('required_for_execution',read(saved/'tools/double/environment_plan.json')['resources'][0])

    def test_review_drift_stops_before_model_or_archival(self):
        for target in ('source','bindings','generated'):
            with self.subTest(target=target):
                self.blocked();old=read(self.skill/'runtime/prepared.json')
                path={'source':self.source/'README.md','bindings':self.bindings,'generated':self.skill/'DOCKER.md'}[target]
                content=path.read_bytes();path.write_bytes(content+b' ')
                with patch('model_call.call') as call,self.assertRaises(lifecycle.IntegrityFailure):
                    lifecycle.prepare(self.skill,'job',self.bindings,review_blocked=True)
                call.assert_not_called();self.assertEqual(read(self.skill/'runtime/prepared.json'),old)
                path.write_bytes(content)

    def test_required_resource_cannot_be_supplied_by_a_review(self):
        self.blocked()
        response={'action':'patch','requested_files':[],'reason':'Resource still required',
                  'operations':[{'op':'add','path':'/resources/0/required_for_execution','value_json':'true'}]}
        with patch('model_call.call',return_value=(response,{})):
            result=lifecycle.prepare(self.skill,'job',self.bindings,review_blocked=True)
        self.assertEqual(result['status'],'blocked_resources');self.assertTrue(result['tools'][0]['blockers'])

    def test_review_cannot_rebuild_prepared_or_accepted_siblings(self):
        self.generate()
        with patch('model_call.call') as call,self.assertRaisesRegex(ValueError,'wholly resource-blocked'):
            lifecycle.prepare(self.skill,'job',self.bindings,review_blocked=True)
        call.assert_not_called()


class OutcomeTests(unittest.TestCase):
    def test_later_creation_failure_preserves_validated_extraction_count(self):
        records=[{'status':'failed','extraction_succeeded':True,'candidate_count':2,'publish_status':'not_published'}]
        tally=workflow_state.counts(records)
        self.assertEqual(tally['extraction_succeeded_runs'],1);self.assertEqual(tally['extracted_candidates'],2)
        self.assertEqual(tally['creation_failed_runs'],1);self.assertEqual(tally['archived_candidates'],0)
        self.assertEqual(tally['execution_passed_candidates'],0)
        self.assertEqual(workflow_state.batch_exit(records,'execution'),1)

    def test_archive_count_uses_physical_manifest_count_and_empty_selection_is_explicit(self):
        record={'status':'method_drafts_created','candidate_count':2,'archived_candidate_count':1,'publish_status':'published_locally','execution_checks':{'one':'execution_passed'}}
        self.assertEqual(workflow_state.counts([record])['archived_candidates'],1)
        self.assertEqual(workflow_state.counts([record])['extracted_candidates'],2)
        self.assertEqual(workflow_state.batch_exit([],'creation'),2)
        self.assertEqual(workflow_state.batch_exit([],'execution'),2)

    def test_all_creation_failures_and_partial_failures_are_nonzero(self):
        for records in [[{'status':'failed'}],[{'status':'failed'},{'status':'method_drafts_created','candidate_count':1,'publish_status':'published_locally'}]]:
            self.assertEqual(workflow_state.batch_exit(records,'creation'),1)

    def test_failed_container_can_be_archived_without_being_executable(self):
        records=[{'status':'method_drafts_created','candidate_count':1,'publish_status':'published_locally','execution_checks':{'skill':'build_failed'}}]
        self.assertEqual(workflow_state.batch_exit(records,'creation'),2)
        self.assertEqual(workflow_state.batch_exit(records,'execution'),2)
        self.assertEqual(workflow_state.counts(records)['archived_candidates'],1)
        self.assertEqual(workflow_state.counts(records)['execution_passed_candidates'],0)

    def test_partial_container_acceptance_does_not_satisfy_strict_policy(self):
        records=[{'status':'method_drafts_created','candidate_count':2,'publish_status':'published_locally','execution_checks':{'ok':'execution_passed','bad':'budget_exhausted'}}]
        self.assertEqual(workflow_state.batch_exit(records,'execution'),2)
        self.assertEqual(workflow_state.counts(records)['execution_passed_candidates'],1)
        records[0]['execution_checks']['bad']='execution_passed';self.assertEqual(workflow_state.batch_exit(records,'execution'),2)
        # Status counts alone are insufficient under the current execution policy.


class ContinuationTests(unittest.TestCase):
    setUp=base.ModelRuntimeTests.setUp
    generate=base.ModelRuntimeTests.generate
    fake_process=base.ModelRuntimeTests.fake_process
    fake_case=base.ModelRuntimeTests.fake_case

    def arrange(self):
        self.here=self.root/'pipeline';target=self.here/'runs/run/drafts-v03'/self.skill.name
        target.parent.mkdir(parents=True);self.skill=self.skill.rename(target)
        write(self.here/'results/run.json',{'status':'method_drafts_created','runtime_mode':'docker','candidate_count':1})
        from delivery import seal_content, determine
        source_bundle=bundle();source_bundle['paper_id']='job'
        write(self.skill/'candidate.json',identity.identity(candidate(),source_bundle,'job'))
        seal_content(self.skill,candidate(),source_bundle)
        write(self.skill/'delivery/requirement.json',determine(self.skill,'job',self.bindings))
        # Identity is part of prepared inputs, so create it before re-preparation.
        self.generate()

    def test_runtime_retry_never_reextracts(self):
        self.arrange()
        with patch.object(inspect_run,'HERE',self.here),patch.object(runner,'process',side_effect=self.fake_process), \
             patch.object(runner,'run_case',side_effect=self.fake_case),patch.object(lifecycle,'verify_examples',return_value=[]), \
             patch('sys.argv',['inspect_run.py','--run-id','run','--action','retry-runtime']),contextlib.redirect_stdout(io.StringIO()), \
             patch('model_call.call',side_effect=AssertionError('No extraction or replanning')):
            self.assertEqual(inspect_run.main(),0)
        self.assertEqual(read(self.skill/'runtime/execution.json')['status'],'execution_passed')

    def test_identity_query_and_drift_stop_without_retry(self):
        self.arrange();value=identity.load(self.skill)
        with patch.object(inspect_run,'HERE',self.here):self.assertEqual(len(inspect_run.inspect('run',value['candidate_id'])['candidates']),1)
        with patch.object(runner,'process',side_effect=self.fake_process),patch.object(runner,'run_case',side_effect=self.fake_case),patch.object(lifecycle,'verify_examples',return_value=[]):lifecycle.validate(self.skill)
        (self.source/'cli.py').write_text('drift')
        with patch.object(inspect_run,'HERE',self.here),patch.object(inspect_run.runtime_docker,'validate') as call, \
             patch('sys.argv',['inspect_run.py','--run-id','run','--action','retry-runtime']),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(inspect_run.main(),2);call.assert_not_called()

    def test_publication_retry_only_calls_existing_publication_entry(self):
        self.arrange()
        with patch.object(inspect_run,'HERE',self.here),patch.object(runner,'process',return_value={'exit_code':0,'stdout':'','stderr':''}) as call, \
             patch.object(inspect_run.runtime_docker,'validate',side_effect=AssertionError('No rebuild')), \
             patch('sys.argv',['inspect_run.py','--run-id','run','--action','retry-publish']),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(inspect_run.main(),2)
        self.assertEqual(Path(call.call_args.args[0][1]).name,'publish_run.py')

    def test_image_loss_is_not_misclassified_as_changed_source(self):
        self.arrange()
        with patch.object(runner,'process',side_effect=self.fake_process),patch.object(runner,'run_case',side_effect=self.fake_case),patch.object(lifecycle,'verify_examples',return_value=[]):lifecycle.validate(self.skill)
        with patch.object(inspect_run,'HERE',self.here),patch.object(inspect_run.runtime_docker,'evidence',return_value={'status':'needs_review','error':'Verified image is missing'}):
            row=inspect_run.inspect('run')['candidates'][0]
        self.assertFalse(row['requires_input_resolution']);self.assertIsNotNone(row['commands']['retry_runtime'])

    def test_old_locked_invalid_probe_stops_without_rebuilding_or_replanning(self):
        self.plan['tests'][0]['case_json']='{"entrypoint":"python","args":["-c","print(\\\"\\n\\\")"],"stdout_equals":"available"}'
        with patch.object(planner,'check_probe_syntax'):self.generate()
        with patch.object(runner,'process',side_effect=self.fake_process) as execute,patch('model_call.call') as model:
            result=lifecycle.validate(self.skill)
        self.assertEqual(result['status'],'needs_review');self.assertTrue(result['tools'][0]['requires_probe_review']);model.assert_not_called()
        self.assertFalse(any('build' in c.args[0] for c in execute.call_args_list))

    def test_strict_publication_keeps_failed_archive_and_returns_two(self):
        self.arrange();out=self.root/'publication';out.mkdir()
        with patch.object(publish_run,'HERE',self.here),patch.object(publish_run,'ROOT',out), \
             patch('sys.argv',['publish_run.py','--run-id','run','--success-policy','execution']),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(publish_run.main(),2)
        manifest=read(out/'skills/generated/run/PUBLISHING.json')
        self.assertEqual(manifest['archive_status'],'completed');self.assertEqual(manifest['execution_passed_candidates'],0)

    def test_observed_failed_layer_is_not_labelled_merely_unchecked(self):
        self.arrange();out=self.root/'publication';out.mkdir()
        observed={'schema_version':3,'backend':'docker','status':'budget_exhausted','validation':{'environment':'failed','interface':'passed','behavior':'passed'}}
        with patch.object(publish_run,'HERE',self.here),patch.object(publish_run,'ROOT',out),patch.object(publish_run,'evidence',return_value=observed), \
             patch('sys.argv',['publish_run.py','--run-id','run','--success-policy','archive']),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(publish_run.main(),0)
        report=read(out/'skills/generated/run/PUBLISHING.json')
        self.assertEqual(report['publication_state'],'tool_execution_failed_candidate')
        self.assertEqual(report['container_acceptance_status'],'not_accepted');self.assertEqual(report['execution_passed_candidates'],0)

    def batch(self,statuses,policy='creation',invalid_report=False):
        here=self.root/'batch-pipeline';root=self.root/'batch-output';root.mkdir(exist_ok=True)
        here.mkdir(exist_ok=True)
        manifest=self.root/'batch.json';write(manifest,{'jobs':[{'paper_id':str(i),'sources':[]} for i in range(len(statuses))]})
        def process(argv,**kwargs):
            run_id=argv[argv.index('--run-id')+1]
            if Path(argv[1]).name=='run_pipeline.py':
                state=statuses[int(run_id.split('-')[-2])]
                write(here/'results'/f'{run_id}.json',{'status':state,'candidate_count':1 if state=='method_drafts_created' else 0})
            else:
                report=root/'skills/generated'/run_id/'PUBLISHING.json'
                write(report,{'note':'IDPP Å∠ endpoint','execution_checks':{'candidate':'build_failed'},'execution_validated':False})
                if invalid_report:report.write_text('{invalid',encoding='utf-8')
            return subprocess.CompletedProcess(argv,0,'','')
        with patch.object(batch_pipeline,'HERE',here),patch.object(batch_pipeline,'ROOT',root), \
             patch.object(batch_pipeline.subprocess,'run',side_effect=process), \
             patch('sys.argv',['batch_pipeline.py','--manifest',str(manifest),'--prefix','batch','--success-policy',policy]),contextlib.redirect_stdout(io.StringIO()):
            code=batch_pipeline.main()
        return code,read(here/'results/batch-batch.json')

    def test_real_batch_control_flow_reports_all_creation_failed(self):
        code,report=self.batch(['failed','failed']);self.assertEqual(code,1)
        self.assertEqual(report['counts']['creation_failed_runs'],2);self.assertEqual(report['published_candidates'],0)

    def test_real_batch_mixed_creation_and_archived_container_failure(self):
        code,report=self.batch(['failed','method_drafts_created'],'execution');self.assertEqual(code,1)
        self.assertEqual(report['counts']['archived_candidates'],1);self.assertEqual(report['counts']['execution_passed_candidates'],0)
        self.assertEqual(report['status'],'finished_with_errors')

    def test_unicode_publication_uses_utf8_even_under_gbk_defaults(self):
        original=Path.read_text
        def default_gbk(path,*args,**kwargs):
            if not args and 'encoding' not in kwargs:kwargs['encoding']='gbk'
            return original(path,*args,**kwargs)
        with patch.object(Path,'read_text',new=default_gbk):code,report=self.batch(['method_drafts_created'],policy='draft')
        self.assertEqual(code,0);self.assertEqual(report['counts']['archived_candidates'],1)

    def test_unreadable_archive_report_is_recorded_and_batch_continues(self):
        code,report=self.batch(['method_drafts_created','failed'],invalid_report=True)
        self.assertEqual(code,1);self.assertEqual(len(report['runs']),2)
        self.assertEqual(report['runs'][0]['publish_error_kind'],'archive_report_unreadable')
        self.assertTrue((self.root/'batch-output/skills/generated/batch-0-r01/PUBLISHING.json').exists())


if __name__=='__main__':unittest.main()
