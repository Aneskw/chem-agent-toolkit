"""Mechanism regressions for observed planning failures; no live-model claims."""
import copy
import contextlib
import io
import json
import os
import stat
import time
import unittest
from unittest.mock import patch

import test_runtime_model as base
import runtime_model as planner
import runtime_model_lifecycle as lifecycle
import runtime_package as runner
from runtime_common import read,write,digest


def patch_answer(path,value,op='add'):
    return {'action':'patch','requested_files':[],'reason':'diagnosed change',
            'operations':[{'op':op,'path':path,'value_json':json.dumps(value)}]}


class PlanningFollowupTests(unittest.TestCase):
    setUp=base.ModelRuntimeTests.setUp
    generate=base.ModelRuntimeTests.generate
    fake_process=base.ModelRuntimeTests.fake_process
    fake_case=base.ModelRuntimeTests.fake_case

    def test_static_retry_receives_rejected_candidate_and_read_material(self):
        bad=copy.deepcopy(self.plan);bad['source_files']=[]
        responses=[({'action':'plan','plan':bad},{}),(patch_answer('/source_files/-','cli.py'),{})]
        with patch('model_call.call',side_effect=responses) as model:
            result=lifecycle.prepare(self.skill,'job',self.bindings)
        self.assertEqual(result['status'],'prepared')
        material=json.loads(model.call_args.args[0].split('\nINPUT\n',1)[1])
        self.assertEqual(material['base_kind'],'rejected_candidate')
        self.assertEqual(material['previous_plan']['source_files'],[])
        self.assertIn('README.md',material['materials'])
        self.assertIn('cli.py',material['diagnostic']['error'])
        self.assertEqual(read(self.skill/'runtime/tools/double/environment_plan.json')['tests'],self.plan['tests'])

    def test_compact_prompt_retains_complete_hash_inventory_on_disk(self):
        for n in range(120):(self.source/f'data-{n}.txt').write_text('unread data'*30)
        with patch('model_call.call',return_value=({'action':'plan','plan':self.plan},{})) as model:
            lifecycle.prepare(self.skill,'job',self.bindings)
        material=json.loads(model.call_args.args[0].split('\nINPUT\n',1)[1])
        inventory=read(self.skill/'runtime/tools/double/attempts/0001/inventory.json')
        self.assertNotIn('sha256',material['index']['files']['cli.py'])
        self.assertIn('sha256',inventory['files']['cli.py'])
        self.assertEqual(set(inventory['files']),set(material['index']['files']))
        self.assertNotIn('not_read',material)
        self.assertLess(len(json.dumps(material['index'])),len(json.dumps(inventory))*.6)

    def test_installation_and_build_metadata_precede_test_flood(self):
        (self.source/'setup.py').write_text('declared_build_dependency')
        for n in range(15):(self.source/f'test-{n}.txt').write_text('x'*400)
        with patch('model_call.call',return_value=({'action':'plan','plan':self.plan},{})) as model:
            planner.plan(self.source,{},self.root/'audit',planner.options({'context_chars':2000}),time.monotonic()+30)
        material=json.loads(model.call_args.args[0].split('\nINPUT\n',1)[1])
        self.assertIn('setup.py',material['materials'])
        self.assertIn('README.md',material['materials'])

    def test_repair_patch_is_small_and_cannot_change_locked_tests(self):
        (self.source/'needed.conf').write_text('required file')
        answer=patch_answer('/source_files/-','needed.conf')
        with patch('model_call.call',return_value=(answer,{})) as model:
            p,index,_=planner.plan(self.source,{},self.root/'audit',planner.options({}),time.monotonic()+30,
                                   {'phase':'build_failed'},self.plan)
        self.assertEqual(p['tests'],self.plan['tests'])
        self.assertIn('needed.conf',p['source_files'])
        self.assertEqual(model.call_args.args[1],planner.PATCH_SCHEMA)
        for path in ['/tests','/tests/0/tolerance','/unknown','/source_files/999']:
            with self.assertRaises(planner.PlanningError):planner.patch_plan(self.plan,patch_answer(path,0,'replace'),True)

    def test_patch_cannot_bypass_context_path_validation(self):
        p=planner.patch_plan(self.plan,patch_answer('/generated_files/-',{'path':'../outside','content':'bad'}),True)
        index=planner.inventory(self.source,planner.options({}))
        with self.assertRaises(planner.PlanningError):planner.validate_plan(p,index,self.source)

    def test_bad_patch_schema_is_a_bounded_plan_error(self):
        with self.assertRaises(planner.PlanningError):planner.patch_plan(self.plan,{'action':'patch'},True)

    def test_changed_source_between_static_attempts_stops_before_next_model_call(self):
        bad=copy.deepcopy(self.plan);bad['source_files']=[]
        def change(*args,**kwargs):
            (self.source/'cli.py').write_text('changed source')
            return {'action':'plan','plan':bad},{}
        with patch('model_call.call',side_effect=change) as model:
            result=lifecycle.prepare(self.skill,'job',self.bindings)
        self.assertEqual(model.call_count,1)
        self.assertEqual(result['tools'][0]['failure_kind'],'integrity')

    def test_source_change_after_read_cannot_be_sealed_as_new_evidence(self):
        def change(*args,**kwargs):
            (self.source/'cli.py').write_text('changed source')
            return {'action':'plan','plan':self.plan},{}
        with patch('model_call.call',side_effect=change) as model:
            result=lifecycle.prepare(self.skill,'job',self.bindings)
        self.assertEqual(model.call_count,1)
        self.assertEqual(result['tools'][0]['failure_kind'],'integrity')

    def test_initial_planning_reserves_time_for_actual_validation(self):
        self.settings['planner'].update(total_seconds=100,validation_reserve_seconds=35)
        write(self.bindings,self.settings);observed=[]
        def plan(source,config,audit,opts,deadline,*args):
            observed.append(deadline-time.monotonic())
            return self.plan,planner.inventory(source,opts),'fixture'
        with patch.object(planner,'plan',side_effect=plan):result=lifecycle.prepare(self.skill,'job',self.bindings)
        self.assertEqual(result['status'],'prepared')
        self.assertTrue(60 < observed[0] <= 65)
        with self.assertRaises(planner.PlanningError):planner.options({'total_seconds':10,'validation_reserve_seconds':10})

    def test_retry_budget_is_reported_without_rewriting_prepared_input(self):
        self.generate();before=(self.skill/'runtime/prepared.json').read_bytes()
        with patch.object(runner,'process',side_effect=self.fake_process),patch.object(runner,'run_case',side_effect=self.fake_case),patch.object(lifecycle,'verify_examples',return_value=[]):
            result=lifecycle.validate(self.skill,budget={'total_seconds':120,'build_seconds':60,'model_timeout':20})
        self.assertEqual(result['status'],'execution_passed')
        self.assertEqual(result['effective_options']['total_seconds'],120)
        self.assertEqual((self.skill/'runtime/prepared.json').read_bytes(),before)
        self.assertEqual(result['prepared_sha256'],digest(read(self.skill/'runtime/prepared.json')))
        with self.assertRaises(ValueError):lifecycle.validate(self.skill,budget={'model':'different'})

    def test_nested_real_build_log_is_decoded_before_truncation(self):
        nested={'command':['docker','build'],'exit_code':1,'stdout':'','stderr':'progress\n'*4000+'configure: required.conf: file not found'}
        outer={'command':['python','runtime/runner.py','build'],'exit_code':1,'stdout':json.dumps(nested),'stderr':''}
        diagnostic=lifecycle.diagnostic_result(outer)
        self.assertTrue(diagnostic['logs_truncated'])
        self.assertIn('required.conf: file not found',diagnostic['stderr'])
        self.assertEqual(diagnostic['command'],['docker','build'])
        self.assertLessEqual(len(diagnostic['stdout'])+len(diagnostic['stderr']),12000)

    def failed_package(self):
        self.settings['planner']['max_attempts']=1;write(self.bindings,self.settings);self.generate()
        def fail(argv,*args,**kwargs):
            if len(argv)>2 and argv[1:3]==['runtime/runner.py','build']:
                return {'command':argv,'exit_code':1,'stdout':json.dumps({'command':['docker','build'],
                    'exit_code':1,'stdout':'','stderr':'configure: missing required.conf'}),'stderr':''}
            return self.fake_process(argv,*args,**kwargs)
        with patch.object(runner,'process',side_effect=fail):report=lifecycle.validate(self.skill)
        self.assertEqual(report['status'],'budget_exhausted')
        return report

    def test_sealed_history_can_repair_before_first_new_build(self):
        self.failed_package();events=[]
        def answer(*args,**kwargs):
            events.append('model');return patch_answer('/language_version','3.11','replace'),{}
        def execute(argv,*args,**kwargs):
            if len(argv)>2 and argv[1:3]==['runtime/runner.py','build']:events.append('build')
            return self.fake_process(argv,*args,**kwargs)
        with patch('model_call.call',side_effect=answer),patch.object(runner,'process',side_effect=execute), \
             patch.object(runner,'run_case',side_effect=self.fake_case),patch.object(lifecycle,'verify_examples',return_value=[]):
            result=lifecycle.validate(self.skill,repair_from_history=True)
        self.assertEqual(result['status'],'execution_passed')
        self.assertEqual(events,['model','build'])
        self.assertIn('historical_diagnostic',result['tools'][0])
        self.assertEqual(result['tools'][0]['locked_cases'],read(self.skill/'runtime/prepared.json')['tools'][0]['locked_cases'])

    def test_history_does_not_bypass_invalidated_input(self):
        self.failed_package();(self.source/'cli.py').write_text('changed')
        with patch('model_call.call') as model:
            result=lifecycle.validate(self.skill,repair_from_history=True)
        self.assertEqual(result['status'],'needs_review');self.assertTrue(result['requires_prepare']);model.assert_not_called()

    def test_history_refuses_infra_success_and_unbuilt_plan(self):
        report=self.failed_package();tool=self.skill/'runtime/tools/double';item=report['tools'][0]
        self.assertIsNotNone(lifecycle.historical_build_failure(self.skill,tool,item))
        for extra in [{'failure_kind':'infrastructure'},{'status':'execution_passed'},{'pending_attempt':'runtime/unbuilt'}]:
            self.assertIsNone(lifecycle.historical_build_failure(self.skill,tool,dict(item,**extra)))
        p=read(tool/'environment_plan.json');p['language_version']='new unbuilt value';write(tool/'environment_plan.json',p)
        self.assertIsNone(lifecycle.historical_build_failure(self.skill,tool,item))

    def test_materialization_preserves_release_mtime_and_executable_mode(self):
        source=self.source/'cli.py'
        if os.name=='posix':source.chmod(0o755)
        os.utime(source,ns=(1700000000000000000,1700000000000000000))
        self.generate();target=self.skill/'runtime/tools/double/context/cli.py'
        self.assertEqual(target.stat().st_mtime_ns,source.stat().st_mtime_ns)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode),stat.S_IMODE(source.stat().st_mode))
        self.assertEqual(read(target.parent/'.skillnet/source-metadata.json')['cli.py']['mtime_ns'],target.stat().st_mtime_ns)

    def test_metadata_only_source_change_changes_context_cache_identity(self):
        self.generate();first=read(self.skill/'runtime/package.json')['tools']['double']['local_tag']
        source=self.source/'cli.py';status=source.stat();os.utime(source,ns=(status.st_atime_ns,status.st_mtime_ns+10000000000))
        self.generate();second=read(self.skill/'runtime/package.json')['tools']['double']['local_tag']
        self.assertNotEqual(first,second)

    def test_context_metadata_drift_stops_before_model_or_docker(self):
        self.generate();target=self.skill/'runtime/tools/double/context/cli.py';status=target.stat()
        os.utime(target,ns=(status.st_atime_ns,status.st_mtime_ns+10000000000))
        with patch('model_call.call') as model,patch.object(runner,'process',side_effect=self.fake_process):
            report=lifecycle.validate(self.skill,repair_from_history=True)
        self.assertEqual(report['status'],'needs_review');self.assertTrue(report['requires_prepare']);model.assert_not_called()

    def test_mounted_fixture_preserves_declared_lf_and_crlf_bytes(self):
        case={'name':'numeric-file','origin':'model_proposed','basis':'Declared fixture bytes must reach the tool unchanged','args':[],
              'input_files':{'lf.tsv':'1\n2\n','crlf.tsv':'1\r\n2\r\n'},'stdout_equals':'3'}
        observed=[]
        def invoke(tool,image,args,input_dir,output_dir,*rest):
            observed.append({name:(input_dir/name).read_bytes() for name in case['input_files']})
            return {'exit_code':0,'stdout':'3\n','stderr':''}
        with patch.object(runner,'run',side_effect=invoke):result=runner.run_case(self.skill,{},'image',case)
        self.assertEqual(result['status'],'passed')
        self.assertEqual(observed,[{'lf.tsv':b'1\n2\n','crlf.tsv':b'1\r\n2\r\n'}])

    def test_documented_preparation_preserves_bytes_and_refuses_normalized_overwrite(self):
        self.generate()
        write(self.skill/'runtime/examples.json',{'examples':[{'name':'sample','kind':'usage','tool_id':'double',
            'input_dir':'../sample-input','output_dir':'../sample-output','input_files':{'numbers.tsv':'1\n2\n'}}]})
        with patch.object(runner,'__file__',str(self.skill/'runtime/runner.py')), \
             patch('sys.argv',['runner.py','prepare-inputs','--tool','double','--example','sample']),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(),0)
            path=self.root/'sample-input/numbers.tsv';self.assertEqual(path.read_bytes(),b'1\n2\n')
            path.write_bytes(b'1\r\n2\r\n')
            with self.assertRaisesRegex(ValueError,'Refusing to overwrite'):runner.main()
            self.assertEqual(path.read_bytes(),b'1\r\n2\r\n')


if __name__=='__main__':unittest.main()
