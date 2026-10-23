"""POSIX permissions plus platform-independent cleanup recovery evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_runtime_model as baseline
import runtime_package as runner
import runtime_model_lifecycle as lifecycle
import runtime_model as planner
import model_call
from runtime_common import read
from probe_runtime_posix import backend_started


class LinuxRuntimeTests(unittest.TestCase):
    setUp=baseline.ModelRuntimeTests.setUp
    generate=baseline.ModelRuntimeTests.generate
    fake_process=baseline.ModelRuntimeTests.fake_process

    def test_model_process_failure_blocks_without_replanning(self):
        with patch('model_call.call',side_effect=model_call.ModelExecutionError('quota unavailable')) as call:
            report=lifecycle.prepare(self.skill,'job',self.bindings)
        self.assertEqual(call.call_count,1)
        self.assertEqual(report['status'],'blocked_resources')
        self.assertEqual(report['tools'][0]['failure_kind'],'model_service')
        self.assertTrue(next(self.skill.glob('runtime/tools/*/attempts/*/model-unavailable.json')))

    def test_repair_model_unavailable_retains_build_failure_without_blind_retries(self):
        for misconfigured_receipt in (False,True):
            with self.subTest(misconfigured_receipt=misconfigured_receipt):
                self.generate()
                def failed_build(argv,*args,**kwargs):
                    if 'build' in argv:return {'command':argv,'exit_code':0 if misconfigured_receipt else 1,
                                              'stdout':'invalid receipt' if misconfigured_receipt else 'missing build dependency','stderr':''}
                    return self.fake_process(argv,*args,**kwargs)
                with patch.object(runner,'process',side_effect=failed_build), \
                     patch('model_call.call',side_effect=model_call.ModelExecutionError('quota unavailable')) as call:
                    report=lifecycle.validate(self.skill)
                self.assertEqual(call.call_count,1)
                self.assertEqual(report['status'],'blocked_resources')
                self.assertEqual(report['tools'][0]['failure_kind'],'model_service')
                self.assertEqual(report['tools'][0]['cases'],[])
                self.assertTrue(next(self.skill.glob('runtime/tools/*/attempts/*/build.json')))

    def test_model_client_nonzero_is_typed_separately_from_invalid_answer(self):
        failed=subprocess.CompletedProcess(['codex'],1,stdout='',stderr='quota unavailable')
        with patch('model_call.subprocess.run',return_value=failed):
            with self.assertRaises(model_call.ModelExecutionError):model_call.call('prompt',{},'fake')
        invalid=subprocess.CompletedProcess(['codex'],0,stdout='malformed',stderr='')
        with patch('model_call.subprocess.run',return_value=invalid):
            with self.assertRaises(ValueError) as error:model_call.call('prompt',{},'fake')
        self.assertNotIsInstance(error.exception,model_call.ModelExecutionError)

    def test_backend_start_requires_executed_output_not_command_echo(self):
        self.assertFalse(backend_started('#5 [2/2] RUN echo START_token\n','token'))
        self.assertTrue(backend_started('#5 0.220 START_token\n','token'))

    def test_large_selected_source_tree_uses_one_copy_layer(self):
        names=[]
        for i in range(400):
            name=f'nested/unit{i}.c';path=self.source/name;path.parent.mkdir(exist_ok=True)
            path.write_text(f'int value{i} = {i};');names.append(name)
        self.plan['source_files']+=names
        self.generate()
        context=self.skill/'runtime/tools/double/context'
        self.assertEqual(sum(line.startswith('COPY ') for line in (context/'Dockerfile').read_text().splitlines()),1)
        for name in names:self.assertEqual((context/name).read_bytes(),(self.source/name).read_bytes())

    def test_unread_test_basis_feedback_names_the_missing_material(self):
        index=planner.inventory(self.source,planner.options({}))
        index['read_files']=['cli.py']
        with self.assertRaisesRegex(planner.PlanningError,'environment.*README.md'):
            planner.validate_plan(self.plan,index,self.source)

    def test_cleanup_failure_retains_scope_for_recovery(self):
        with patch.object(runner.subprocess,'run',side_effect=OSError('endpoint unavailable')):
            observations=runner.cleanup_scope('owned-scope')
        self.assertEqual(observations[0]['phase'],'cleanup_failed')
        self.assertEqual(observations[0]['scope'],'owned-scope')

    def test_timeout_saves_logs_and_scope_even_when_cleanup_failed(self):
        self.generate()
        def process(argv,*args,**kwargs):
            if 'build' in argv:
                exc=subprocess.TimeoutExpired(argv,1,output=b'actual build output',stderr=b'actual failure')
                exc.scope='recoverable-scope';exc.cleanup=[{'phase':'list_owned_containers','exit_code':1,'scope':exc.scope}]
                raise exc
            return self.fake_process(argv,*args,**kwargs)
        with patch.object(runner,'process',side_effect=process): result=lifecycle.validate(self.skill)
        self.assertEqual(result['status'],'budget_exhausted')
        self.assertEqual(result['tools'][0]['process_scope'],'recoverable-scope')
        saved=next(self.skill.glob('runtime/tools/*/attempts/*/timeout.json'))
        self.assertEqual(read(saved)['stdout'],'actual build output')
        self.assertEqual(read(saved)['scope'],'recoverable-scope')

    def test_retry_archives_timeout_scope_without_displaying_it_as_current_cleanup(self):
        self.generate()
        def timeout(argv,*args,**kwargs):
            if 'build' in argv:
                exc=subprocess.TimeoutExpired(argv,1)
                exc.scope='previous-scope';exc.cleanup=[{'phase':'cleanup_failed','scope':exc.scope}]
                raise exc
            return self.fake_process(argv,*args,**kwargs)
        with patch.object(runner,'process',side_effect=timeout):lifecycle.validate(self.skill)
        with patch.object(runner,'process',side_effect=self.fake_process), \
             patch.object(runner,'run_case',side_effect=lambda *a,**kw:baseline.ModelRuntimeTests.fake_case(self,*a,**kw)), \
             patch.object(lifecycle,'verify_examples',return_value=[{'status':'passed'}]):
            current=lifecycle.validate(self.skill)
        self.assertEqual(current['status'],'execution_passed')
        self.assertNotIn('process_scope',current['tools'][0])
        self.assertNotIn('process_cleanup',current['tools'][0])
        history=read(self.skill/current['previous_execution']['path'])
        self.assertEqual(history['tools'][0]['process_scope'],'previous-scope')

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

    @unittest.skipUnless(os.name=='posix','Native POSIX mode semantics')
    def test_prepare_input_modes_nested_files_and_existing_user_data(self):
        self.plan['file_io']=True
        self.plan['tests'][1]['case_json']=json.dumps({'args':['3'],'input_files':{'nested/deep/n.txt':'3'},
            'output_file':'result.txt','capture_stdout':True,'stdout_equals':'6'})
        self.generate()
        example=next(e for e in read(self.skill/'runtime/examples.json')['examples'] if e['kind']=='usage')
        previous=os.umask(0o077)
        try:
            result=subprocess.run([sys.executable,str(self.skill/'runtime/runner.py'),*example['preparation_argv'][2:]],cwd=self.skill,capture_output=True)
        finally:os.umask(previous)
        self.assertEqual(result.returncode,0,result.stderr)
        directory=self.skill/example['input_dir']
        self.assertEqual((directory/'nested/deep').stat().st_mode&0o777,0o755)
        path=directory/'nested/deep/n.txt';self.assertEqual(path.stat().st_mode&0o777,0o644)
        path.chmod(0o600)
        result=subprocess.run([sys.executable,str(self.skill/'runtime/runner.py'),*example['preparation_argv'][2:]],cwd=self.skill,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(path.stat().st_mode&0o777,0o600,'Do not widen existing user files')


if __name__=='__main__':unittest.main()
