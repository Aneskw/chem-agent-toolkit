"""Execution-policy boundaries: mock engine/model, actual pipeline control flow."""
import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_runtime_model as base
from test_creation_contract import candidate
import strict_acceptance as strict
import workflow_state
import run_pipeline
import publish_run
import batch_pipeline
from runtime_common import read, write

GOOD = {'status':'execution_passed','acceptance_version':2,'current_acceptance_validated':True}


class StrictTests(unittest.TestCase):
    setUp = base.ModelRuntimeTests.setUp
    generate = base.ModelRuntimeTests.generate
    verified = base.ModelRuntimeTests.verified
    fake_process = base.ModelRuntimeTests.fake_process
    fake_case = base.ModelRuntimeTests.fake_case

    def record(self, paths=None, flag=True):
        paths = paths or [self.skill]
        return dict(status='method_drafts_created',candidate_count=len(paths),publish_status='published_locally',
                    execution_checks={str(i):'execution_passed' for i in range(len(paths))},
                    candidate_paths=[str(p) for p in paths],current_acceptance_validated=flag)

    def test_false_missing_and_legacy_markers_rejected(self):
        for report in [dict(GOOD,current_acceptance_validated=False),
                       {'status':'execution_passed','acceptance_version':2},
                       dict(GOOD,acceptance_version=1)]:
            with patch.object(strict,'evidence',return_value=report):
                self.assertFalse(strict.record_passes(self.record()))
                self.assertEqual(workflow_state.batch_exit([self.record()],'execution'),2)
        with patch.object(strict,'evidence',return_value=GOOD):
            record=self.record();record.pop('current_acceptance_validated')
            self.assertFalse(strict.record_passes(record))

    def test_mixed_candidates_and_all_current(self):
        paths=[self.skill,self.root/'second'];record=self.record(paths)
        with patch.object(strict,'evidence',side_effect=[GOOD,dict(GOOD,current_acceptance_validated=False)]):
            self.assertFalse(strict.record_passes(record))
        with patch.object(strict,'evidence',return_value=GOOD):
            self.assertTrue(strict.record_passes(record))
            self.assertEqual(workflow_state.batch_exit([record],'execution'),0)
        record['candidate_count']=3
        self.assertFalse(strict.record_passes(record))

    def test_real_input_drift_overrides_true_marker(self):
        self.verified()
        with patch('runtime_package.process',side_effect=self.fake_process):
            self.assertTrue(strict.record_passes(self.record()))
            (self.source/'cli.py').write_text('changed input')
            self.assertFalse(strict.record_passes(self.record()))

    def test_creation_policy_does_not_require_execution(self):
        with patch.object(strict,'evidence',side_effect=AssertionError('creation must not inspect Docker')):
            self.assertEqual(workflow_state.batch_exit([self.record(flag=False)],'creation'),2)

    def main_pipeline(self, report, policy='execution', publish=False):
        here=self.root/('pipeline-'+str(len(list(self.root.glob('pipeline-*')))))
        here.mkdir()
        source=self.root/'paper.txt';source.write_text('Supported procedural evidence for the method.\n')
        config=self.root/'source.json'
        write(config,{'jobs':[{'paper_id':'job','title':'Example','source_type':'paper',
                              'sources':[{'path':str(source),'role':'paper'}]}]})
        response=self.root/'response.json'
        write(response,{'contract_version':'1.1','schema_version':3,'paper_id':'job','candidates':[candidate()],'no_skill_reason':''})
        original=Path(run_pipeline.__file__).parent;calls=[]
        def call(*args):
            calls.append(args)
            script=Path(args[0])
            if script.name=='publish_run.py':
                write(here.parent/'skills/generated/run/PUBLISHING.json',{'execution_passed_candidates':1})
                if not report.get('current_acceptance_validated') and policy=='execution':
                    raise subprocess.CalledProcessError(2,args,output='{"status":"published_locally"}')
                return
            actual=original/'core'/script.name if script.name=='creation.py' else original/script.name
            result=subprocess.run([sys.executable,str(actual),*args[1:]],capture_output=True,text=True,encoding='utf-8')
            if result.returncode:raise subprocess.CalledProcessError(result.returncode,args,output=result.stdout,stderr=result.stderr)
        argv=['run_pipeline.py','--config',str(config),'--response-file',str(response),'--run-id','run',
              '--runtime-mode','docker','--tool-bindings',str(self.bindings),'--success-policy',policy]
        if publish:argv.append('--publish-local')
        def stage(drafts,job,bindings,**kwargs):
            import delivery
            for folder in Path(drafts).iterdir():
                write(folder/'delivery/requirement.json',delivery.determine(folder,job,bindings))
            return {'runtime_checks':{'example-procedure':'execution_passed'}}
        with patch.object(run_pipeline,'HERE',here),patch.object(run_pipeline,'call',side_effect=call), \
             patch('delivery.stage',side_effect=stage), \
             patch.object(strict,'evidence',return_value=report),patch('delivery.runtime_docker.evidence',return_value=report),patch('sys.argv',argv),contextlib.redirect_stdout(io.StringIO()):
            code=run_pipeline.main()
        return code,calls,read(here/'results/run.json')

    def test_strict_main_without_publish_false_missing_mixed_evidence(self):
        for report in [dict(GOOD,current_acceptance_validated=False),{'status':'execution_passed'},dict(GOOD,status='needs_review')]:
            code,_,record=self.main_pipeline(report)
            self.assertEqual(code,2);self.assertEqual(record['archive_status'],'not_requested')
        self.assertEqual(self.main_pipeline(GOOD)[0],0)

    def test_main_forwards_policy_and_preserves_creation(self):
        code,calls,_=self.main_pipeline(GOOD,publish=True)
        self.assertEqual(code,0)
        publish=next(c for c in calls if Path(c[0]).name=='publish_run.py')
        self.assertEqual(publish[publish.index('--success-policy')+1],'execution')
        code,_,record=self.main_pipeline(dict(GOOD,current_acceptance_validated=False),publish=True)
        self.assertEqual(code,2);self.assertEqual(record['archive_status'],'completed')
        self.assertEqual(self.main_pipeline({'status':'needs_review'},policy='creation')[0],2)

    def test_strict_publisher_checks_current_evidence_again(self):
        self.generate()
        for number,report in enumerate([GOOD,dict(GOOD,current_acceptance_validated=False),{'status':'execution_passed'}]):
            here=self.root/f'pub-{number}'
            draft=here/'runs/run/drafts-v03'/self.skill.name;shutil.copytree(self.skill,draft)
            write(here/'results/run.json',{'status':'method_drafts_created','runtime_mode':'docker'})
            output=self.root/f'output-{number}';output.mkdir()
            with patch.object(publish_run,'HERE',here),patch.object(publish_run,'ROOT',output), \
                 patch.object(publish_run,'evidence',return_value=report),patch.object(strict,'evidence',return_value=report), \
                 patch('sys.argv',['publish_run.py','--run-id','run','--success-policy','execution']),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(publish_run.main(),2)  # Legacy package has no source/requirement delivery proof.

    def test_batch_forwards_strict_policy_and_rechecks(self):
        for number,flag in enumerate([True,False,None]):
            here=self.root/f'batch-{number}';here.mkdir();output=self.root/f'batch-out-{number}';output.mkdir()
            config=self.root/f'batch-{number}.json';write(config,{'jobs':[{'paper_id':'job','sources':[]}]})
            calls=[]
            def process(argv,**kwargs):
                calls.append(argv);run=argv[argv.index('--run-id')+1]
                folder=output/'skills/generated'/run/'candidate';folder.mkdir(parents=True,exist_ok=True)
                (folder/'SKILL.md').write_text('fixture')
                report=dict(status='method_drafts_created',candidate_count=1,runtime_checks={'candidate':'execution_passed'},
                            execution_checks={'candidate':'execution_passed'},candidate_paths=[str(folder)])
                if flag is not None:report['current_acceptance_validated']=flag
                if Path(argv[1]).name=='run_pipeline.py':write(here/'results'/f'{run}.json',report)
                else:write(folder.parent/'PUBLISHING.json',report)
                return subprocess.CompletedProcess(argv,0,'','')
            with patch.object(batch_pipeline,'HERE',here),patch.object(batch_pipeline,'ROOT',output), \
                 patch.object(batch_pipeline.subprocess,'run',side_effect=process),patch.object(strict,'evidence',return_value=GOOD), patch('delivery.record_passes',return_value=True), \
                 patch('sys.argv',['batch_pipeline.py','--manifest',str(config),'--prefix','batch','--success-policy','execution']),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(batch_pipeline.main(),0 if flag is True else 2)
            self.assertTrue(all(c[c.index('--success-policy')+1]=='execution' for c in calls))
