"""Budget and immutable-base mechanism regressions; not live tool evidence."""
import json
import unittest
import contextlib
import io
import time
from unittest.mock import patch
import test_runtime_model as base
import runtime_model as planner
import runtime_package as runner
import runtime_reproducibility as repro
from runtime_common import write, read
from runtime_examples import usage_example
import inspect_run
import runtime_model_lifecycle as lifecycle


class RoundTwoTests(unittest.TestCase):
    setUp=base.ModelRuntimeTests.setUp
    generate=base.ModelRuntimeTests.generate
    def test_long_case_requires_explicit_budget_and_preserves_contract(self):
        self.plan['tests'][2]['case_json']=json.dumps(dict(json.loads(self.plan['tests'][2]['case_json']),timeout_seconds=600))
        index=planner.inventory(self.source,planner.options({}))
        with self.assertRaisesRegex(planner.PlanningError,'test_seconds'):
            planner.materialize(self.source,{},self.skill/'runtime/tools/double/context','double',self.plan,index,planner.options({}))
        self.settings['planner']['test_seconds']=600;write(self.bindings,self.settings)
        result=self.generate();self.assertEqual(result['status'],'prepared')
        tool=read(self.skill/'runtime/package.json')['tools']['double']
        case=read(self.skill/tool['context']/tool['fixtures'])['cases'][2]
        with patch.object(runner,'run',return_value={'exit_code':0,'stdout':'6','stderr':''}) as call:
            self.assertEqual(runner.run_case(self.skill,tool,'image',case,deadline=time.monotonic()+90)['status'],'passed')
            self.assertGreater(call.call_args.args[-1],60);self.assertLessEqual(call.call_args.args[-1],90)

    def test_base_manifest_digest_enters_new_dockerfile_and_inputs(self):
        self.settings['planner']['pin_base_image']=True;write(self.bindings,self.settings)
        manifest={'digest':'sha256:'+'b'*64,'manifests':[{'digest':'sha256:'+'c'*64,'platform':{'os':'linux','architecture':'amd64'}}]}
        receipt={'exit_code':0,'stdout':json.dumps(manifest),'stderr':''}
        with patch.object(runner,'process',return_value=receipt):self.generate()
        context=self.skill/'runtime/tools/double/context'
        self.assertIn('@sha256:'+'c'*64,(context/'Dockerfile').read_text())
        self.assertEqual(read(context/'.skillnet/base-lock.json')['requested'],'python:3.11-slim')

    def test_digest_resolution_fails_closed(self):
        with patch.object(runner,'process',return_value={'exit_code':1,'stdout':'','stderr':'offline'}):
            with self.assertRaises(OSError):repro.resolve_base('python:3.11','linux/amd64',120)

    def test_missing_platform_fails_closed(self):
        manifest={'digest':'sha256:'+'a'*64,'manifests':[{'platform':{'os':'linux','architecture':'arm64'}}]}
        with patch.object(runner,'process',return_value={'exit_code':0,'stdout':json.dumps(manifest),'stderr':''}):
            with self.assertRaises(ValueError):repro.resolve_base('python:3.11','linux/amd64',120)

    def test_inventory_is_never_full_lock(self):
        self.generate();tool=read(self.skill/'runtime/package.json')['tools']['double']
        with patch.object(runner,'run',return_value={'exit_code':0,'stdout':'a==1','stderr':''}):
            observed=repro.observe(tool,{'Id':'image'},self.skill/'runtime/tools/double',time.monotonic()+100)
        self.assertFalse(observed['complete_rebuild_lock'])
        self.assertEqual(observed['inventories']['pip']['classification'],'observed_inventory')

    def test_usage_timeout_is_forwarded(self):
        self.generate();tool=read(self.skill/'runtime/package.json')['tools']['double']
        example=usage_example(self.skill,'double',tool)
        self.assertIn('--timeout-seconds',example['argv'])

    def test_declared_dependency_prefix_preserves_step_order(self):
        self.plan['generated_files']=[{'path':'requirements.txt','content':'example==1\n'}]
        self.plan['steps']=[{'command':'echo dependency','purpose':'install','evidence':'test'},
                            {'command':'echo source','purpose':'compile','evidence':'test'}]
        self.plan['build_layout']={'dependency_files':['requirements.txt'],'prefix_steps':1,'reason':'explicit dependencies'}
        self.generate();text=(self.skill/'runtime/tools/double/context/Dockerfile').read_text()
        self.assertLess(text.index('RUN echo dependency'),text.index('COPY . ./'))
        self.assertLess(text.index('COPY . ./'),text.index('RUN echo source'))
        self.assertIn('dependency-metadata.json',text)

    def test_unknown_dependency_input_is_rejected(self):
        self.plan['build_layout']={'dependency_files':['missing.txt'],'prefix_steps':0,'reason':'test'}
        index=planner.inventory(self.source,planner.options({}))
        with self.assertRaisesRegex(planner.PlanningError,'Dependency input absent'):
            planner.validate_plan(self.plan,index,self.source)

    def test_continuation_budget_is_shared_and_receipt_precedes_execution(self):
        write(self.root/'results/run.json',{'candidate_count':2})
        rows=[{'candidate':str(n),'path':str(self.skill),'runtime_status':'build_failed',
               'requires_input_resolution':False,'commands':{'retry_runtime':['validate']}} for n in range(2)]
        budgets=[]
        def validate(*args,**kwargs):
            receipt=next((self.root/'runs/run/continuations').glob('*.json'))
            self.assertEqual(read(receipt)['state'],'running')
            budgets.append(kwargs['budget']['total_seconds'])
            return {'status':'execution_passed'}
        with patch.object(inspect_run,'HERE',self.root),patch.object(inspect_run,'inspect',return_value={'candidates':rows}), \
             patch.object(inspect_run.time,'monotonic',side_effect=[0,1,41,42]), \
             patch.object(inspect_run.runtime_docker,'validate',side_effect=validate), \
             patch('delivery.evaluate',return_value={'delivery_accepted':True}), patch('strict_acceptance.evaluate',return_value={'current_acceptance_validated':True}), patch('sys.argv',['inspect_run.py','--run-id','run','--action','retry-runtime','--total-seconds','100','--success-policy','execution']),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(inspect_run.main(),0)
        self.assertEqual(budgets,[99,59])
        receipt=read(next((self.root/'runs/run/continuations').glob('*.json')))
        self.assertEqual(receipt['state'],'finished');self.assertEqual(receipt['elapsed_seconds'],42)

    def test_renderer_refresh_replays_plan_and_tests_without_model(self):
        before=self.generate();plan=read(self.skill/'runtime/tools/double/environment_plan.json')
        with patch('model_call.call',side_effect=AssertionError('No new model planning')):
            after=lifecycle.refresh_renderer(self.skill,'job',self.bindings)
        self.assertEqual(after['status'],'prepared')
        self.assertTrue((self.skill/after['renderer_refresh']['previous_runtime']/'prepared.json').exists())
        self.assertEqual(before['tools'][0]['locked_cases'],after['tools'][0]['locked_cases'])
        self.assertEqual(plan,read(self.skill/'runtime/tools/double/environment_plan.json'))
        self.assertFalse((self.skill/'runtime/execution.json').exists())
        self.assertIn('skillnet10001',(self.skill/'runtime/tools/double/context/Dockerfile').read_text())

    def test_renderer_refresh_stops_input_drift_before_archiving(self):
        self.generate();(self.source/'cli.py').write_text('changed')
        with self.assertRaises(lifecycle.IntegrityFailure):lifecycle.refresh_renderer(self.skill,'job',self.bindings)
        self.assertFalse(list((self.skill/'reports').glob('runtime-archive-*')))

    def test_retry_clears_old_reproducibility_observations(self):
        item={'status':'execution_passed','locked_cases':[],'reproducibility':{'image_id':'old'}}
        lifecycle.reset_observations(item)
        self.assertNotIn('reproducibility',item)

    def test_output_evidence_survives_failed_case_and_temp_cleanup(self):
        self.generate();tool=read(self.skill/'runtime/package.json')['tools']['double']
        case={'name':'failure','origin':'controlled','basis':'preserve failure evidence','args':[],
              'output_file':'report.json','expected_exit':0}
        def run(*args):
            (args[4]/'report.json').write_text('{"status":"failed"}')
            (args[4]/'worker.stderr.log').write_text('diagnostic')
            return {'exit_code':1,'stdout':'','stderr':'failure'}
        with patch.object(runner,'run',side_effect=run):
            result=runner.run_case(self.skill,tool,'image',case,artifact_dir=self.root/'retained')
        self.assertEqual(result['status'],'failed')
        self.assertEqual((self.root/'retained/worker.stderr.log').read_text(),'diagnostic')
        self.assertIn('report.json',result['output_artifacts']['files'])

    def test_stdout_capture_requires_no_container_file_mount(self):
        self.plan['tests'][2]['case_json']=json.dumps(dict(json.loads(self.plan['tests'][2]['case_json']),output_file='result.txt',capture_stdout=True))
        self.generate();tool=read(self.skill/'runtime/package.json')['tools']['double']
        case=read(self.skill/tool['context']/tool['fixtures'])['cases'][2]
        with patch.object(runner,'run',return_value={'exit_code':0,'stdout':'6','stderr':''}) as call:
            result=runner.run_case(self.skill,tool,'image',case)
        self.assertIsNone(call.call_args.args[4]);self.assertEqual(result['status'],'passed')
        example=usage_example(self.skill,'double',tool)
        self.assertIn('--stdout-file',example['argv']);self.assertNotIn('--output-dir',example['argv'])

    def test_usage_rejection_preserves_existing_context(self):
        self.generate();context=self.skill/'runtime/tools/double/context'
        before=(context/'Dockerfile').read_bytes();self.plan['file_io']=True
        self.plan['tests'][2]['case_json']=json.dumps(dict(json.loads(self.plan['tests'][2]['case_json']),output_file='result.txt',capture_stdout=True))
        index=planner.inventory(self.source,planner.options({}))
        with self.assertRaisesRegex(ValueError,'persisted-output'):
            planner.materialize(self.source,{},context,'double',self.plan,index,planner.options({}))
        self.assertEqual(before,(context/'Dockerfile').read_bytes())

    def test_multiline_library_invocation_stays_one_json_directive(self):
        code="import runpy\nrunpy.run_path('/opt/skill/cli.py')"
        self.plan['entrypoint']=['python','-c',code]
        self.assertEqual(self.generate()['status'],'prepared')
        lines=(self.skill/'runtime/tools/double/context/Dockerfile').read_text().splitlines()
        directives=[line for line in lines if line.startswith('ENTRYPOINT ')]
        self.assertEqual(len(directives),1)
        self.assertEqual(json.loads(directives[0][11:]),self.plan['entrypoint'])

    def test_multiline_executable_name_is_rejected(self):
        self.plan['entrypoint']=['python\nRUN invalid']
        with self.assertRaisesRegex(planner.PlanningError,'Invalid entrypoint'):
            planner.validate_plan(self.plan,planner.inventory(self.source,planner.options({})),self.source)
