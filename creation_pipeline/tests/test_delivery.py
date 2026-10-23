"""Delivery policy tests. Planner/engine mocks are not real Docker acceptance."""
import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import delivery
import candidate_identity
import run_pipeline
import publish_run
import run_public_pipeline
import inspect_run
import workflow_state
from runtime_common import read, write
from render_drafts_v03 import render
from test_creation_contract import candidate, bundle, cited

GOOD={'status':'execution_passed','acceptance_version':2,'current_acceptance_validated':True,
      'tools':[{'tool_id':'tool','image_id':'sha256:'+'a'*64}]}


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2])
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.skill=self.root/'drafts/example-procedure'
        self.bindings=self.root/'bindings.json'
        self.c=candidate();self.c['unknowns']=[]
        self.c['tool_requirement']={'status':'not_required','reason':cited('Only read the supplied evidence and choose a documented branch.')}
        self.b=bundle()
        self.make(self.skill,self.c)

    def make(self,path,c):
        path.mkdir(parents=True,exist_ok=True)
        c=copy.deepcopy(c);c['name']=path.name
        (path/'SKILL.md').write_text(render(c,self.b,{'state':'draft_unexecuted'}),encoding='utf-8')
        write(path/'candidate.json',candidate_identity.identity(c,self.b,'paper-1'))
        delivery.seal_content(path,c,self.b)

    def decide(self,path=None,bindings=None):
        path=path or self.skill
        write(path/'delivery/requirement.json',delivery.determine(path,'paper-1',bindings))

    def tool(self):
        self.c['kind']='tool_usage';self.c.pop('tool_requirement')
        self.make(self.skill,self.c)
        write(self.bindings,{'schema_version':3,'tools':{'tool':{'root':str(self.root)}},
            'bindings':[{'job_id':'paper-1','candidate':self.skill.name,'requirement':'required','tools':['tool']}]})

    def test_text_delivers_without_docker_and_not_execution_accepted(self):
        with patch.object(delivery.runtime_docker,'prepare',side_effect=AssertionError('no Docker')):
            report=delivery.stage(self.skill.parent,'paper-1')
        self.assertTrue(report['delivery_accepted'])
        row=report['delivery_checks'][self.skill.name]
        self.assertFalse(row['execution_accepted'])
        self.assertEqual(row['stages']['docker_build'],'not_required')

    def test_empty_requirements_is_unknown_not_no_tool(self):
        self.c.pop('tool_requirement');self.make(self.skill,self.c)
        report=delivery.stage(self.skill.parent,'paper-1')
        self.assertFalse(report['delivery_accepted'])
        self.assertEqual(report['delivery_checks'][self.skill.name]['requirement'],'unknown')

    def test_resolved_reading_resource_does_not_force_docker(self):
        self.b['repo_files']=['guide.md']
        self.c['requirements']=[{'kind':'repo_file','path':'guide.md','reason':cited('Read the supplied guide; no command execution.')}]
        self.make(self.skill,self.c)
        with patch.object(delivery.runtime_docker,'prepare',side_effect=AssertionError('Reading is not execution')):
            self.assertTrue(delivery.stage(self.skill.parent,'paper-1')['delivery_accepted'])

    def test_no_tool_exemption_cannot_hide_tool_usage(self):
        self.c['kind']='tool_usage';self.make(self.skill,self.c)
        self.assertFalse(delivery.stage(self.skill.parent,'paper-1')['delivery_accepted'])

    def test_unresolved_dependencies_block_no_tool(self):
        self.c['unknowns']=['Required implementation not available'];self.make(self.skill,self.c)
        self.assertFalse(delivery.stage(self.skill.parent,'paper-1')['delivery_accepted'])

    def test_binding_cannot_override_known_candidate_requirement(self):
        for declared, bound in [('not_required','required'), ('required','not_required')]:
            with self.subTest(declared=declared):
                self.c['tool_requirement']['status']=declared
                self.make(self.skill,self.c)
                write(self.bindings,{'schema_version':3,'tools':{'tool':{'root':str(self.root)}},
                    'bindings':[{'job_id':'paper-1','candidate':self.skill.name,
                        'requirement':bound,'tools':['tool'] if bound=='required' else [],'reason':cited()}]})
                with patch.object(delivery.runtime_docker,'prepare') as prepare:
                    report=delivery.stage(self.skill.parent,'paper-1',self.bindings)
                    self.assertFalse(report['delivery_accepted'])
                    self.assertIn('contradicts',report['delivery_checks'][self.skill.name]['error'])
                    prepare.assert_not_called()

    def test_binding_cannot_mask_internal_contract_conflict(self):
        self.tool()
        self.c['tool_requirement']={'status':'not_required','reason':cited()}
        self.make(self.skill,self.c)
        with patch.object(delivery.runtime_docker,'prepare') as prepare:
            self.assertFalse(delivery.stage(self.skill.parent,'paper-1',self.bindings)['delivery_accepted'])
            prepare.assert_not_called()

    def test_missing_source_dependency_cannot_hide_behind_binding(self):
        self.tool()
        self.c['requirements']=[{'kind':'repo_file','path':'missing-model.py','reason':cited()}]
        self.make(self.skill,self.c)
        with patch.object(delivery.runtime_docker,'prepare') as prepare:
            self.assertFalse(delivery.stage(self.skill.parent,'paper-1',self.bindings)['delivery_accepted'])
            prepare.assert_not_called()

    def test_legacy_off_requires_explicit_draft(self):
        with patch.object(sys,'argv',['run_pipeline','--paper-id','paper-1','--runtime-mode','off']), \
             contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
            run_pipeline.main()
        self.assertEqual(error.exception.code,2)

    def test_missing_binding_blocks_required_tool(self):
        self.tool()
        with patch.object(delivery.runtime_docker,'prepare') as prepare:
            self.assertFalse(delivery.stage(self.skill.parent,'paper-1')['delivery_accepted'])
            prepare.assert_not_called()

    def test_tool_default_runs_preparation_and_validation(self):
        self.tool()
        with patch.object(delivery.runtime_docker,'prepare',return_value={'status':'prepared'}) as prepare, \
             patch.object(delivery.runtime_docker,'validate',return_value=GOOD) as validate, \
             patch.object(delivery.runtime_docker,'evidence',return_value=GOOD):
            report=delivery.stage(self.skill.parent,'paper-1',self.bindings)
        self.assertTrue(report['delivery_accepted']);prepare.assert_called_once();validate.assert_called_once()

    def test_build_validation_missing_or_legacy_evidence_cannot_deliver(self):
        self.tool();self.decide(bindings=self.bindings)
        for bad in [{'status':'build_failed'},{'status':'execution_failed'},dict(GOOD,current_acceptance_validated=False),
                    dict(GOOD,acceptance_version=1),{'status':'execution_passed'}]:
            with self.subTest(bad=bad),patch.object(delivery.runtime_docker,'evidence',return_value=bad):
                self.assertFalse(delivery.evaluate([self.skill],1)['delivery_accepted'])

    def test_mixed_candidates_and_partial_failure(self):
        text=self.root/'drafts/text-procedure';self.make(text,self.c);self.decide(text)
        self.tool();self.decide(bindings=self.bindings)
        with patch.object(delivery.runtime_docker,'evidence',return_value=GOOD):
            self.assertTrue(delivery.evaluate([text,self.skill],2)['delivery_accepted'])
        with patch.object(delivery.runtime_docker,'evidence',return_value={'status':'execution_failed'}):
            result=delivery.evaluate([text,self.skill],2)
            self.assertFalse(result['delivery_accepted']);self.assertEqual(result['delivered_candidates'],1)

    def test_draft_never_calls_runtime_or_claims_delivery(self):
        self.tool()
        with patch.object(delivery.runtime_docker,'prepare',side_effect=AssertionError('draft')), \
             patch.object(delivery.runtime_docker,'evidence',side_effect=AssertionError('draft')):
            result=delivery.stage(self.skill.parent,'paper-1',self.bindings,draft_only=True)
        self.assertEqual(result['delivery_status'],'draft_only');self.assertFalse(result['delivery_accepted'])

    def test_modified_text_and_source_rejected(self):
        self.decide()
        (self.skill/'SKILL.md').write_text((self.skill/'SKILL.md').read_text()+'\nUnreviewed instruction\n')
        self.assertFalse(delivery.evaluate([self.skill],1)['delivery_accepted'])

    def test_binding_hash_drift_blocks_retry_without_reprepare(self):
        self.tool();self.decide(bindings=self.bindings)
        self.bindings.write_text(self.bindings.read_text()+'\n')
        with patch.object(delivery.runtime_docker,'validate') as validate:
            with self.assertRaisesRegex(ValueError,'Changed requirement'):
                delivery.retry(self.skill)
            validate.assert_not_called()

    def test_retry_reuses_valid_stage_without_generation(self):
        self.tool();self.decide(bindings=self.bindings)
        with patch.object(delivery.runtime_docker,'evidence',return_value={'status':'execution_failed'}), \
             patch.object(delivery.runtime_docker,'prepare') as prepare, \
             patch.object(delivery.runtime_docker,'validate',return_value=GOOD) as validate:
            delivery.retry(self.skill)
            prepare.assert_not_called();validate.assert_called_once()

    def test_retry_does_not_rerun_accepted_candidate(self):
        self.decide()
        with patch.object(delivery.runtime_docker,'validate') as validate:
            self.assertTrue(delivery.retry(self.skill)['reused']);validate.assert_not_called()

    def test_batch_rechecks_evidence_not_delivery_boolean(self):
        self.decide()
        record={'status':'method_drafts_created','candidate_count':1,'candidate_paths':[str(self.skill)],
                'publish_status':'published_locally','delivery_accepted':False}
        self.assertEqual(workflow_state.batch_exit([record],'delivery'),0)
        (self.skill/'SKILL.md').write_text('changed')
        record['delivery_accepted']=True
        self.assertEqual(workflow_state.batch_exit([record],'delivery'),2)

    def test_public_entry_forwards_default_delivery_and_propagates_failure(self):
        here=self.root/'pipeline';here.mkdir()
        catalog=self.root/'catalog.json';write(catalog,{'jobs':[]})
        commands=[]
        def process(argv,**kwargs):
            commands.append(argv)
            if Path(argv[1]).name=='ingest_sources.py':
                write(Path(argv[argv.index('--out')+1])/'manifest.json',{'jobs':[]})
                return subprocess.CompletedProcess(argv,0)
            return subprocess.CompletedProcess(argv,2)
        with patch.object(run_public_pipeline,'HERE',here),patch.object(run_public_pipeline.subprocess,'run',side_effect=process), \
             patch.object(sys,'argv',['public','--catalog',str(catalog)]):
            self.assertEqual(run_public_pipeline.main(),2)
        last=commands[-1]
        self.assertEqual(last[last.index('--success-policy')+1],'delivery')
        self.assertEqual(last[last.index('--runtime-mode')+1],'auto')

    def test_selected_candidate_recovery_still_checks_whole_run(self):
        self.decide()
        here=self.root/'pipeline';drafts=here/'runs/run/drafts-v03'
        shutil.copytree(self.skill,drafts/self.skill.name)
        other=drafts/'unresolved';c=copy.deepcopy(self.c);c.pop('tool_requirement');self.make(other,c)
        write(other/'delivery/requirement.json',delivery.determine(other,'paper-1'))
        write(here/'results/run.json',{'status':'method_drafts_created','paper_id':'paper-1','candidate_count':2})
        with patch.object(inspect_run,'HERE',here),patch.object(sys,'argv',
             ['inspect','--run-id','run','--candidate',self.skill.name,'--action','retry-runtime']),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(inspect_run.main(),2)
        result=read(here/'results/run.json')
        self.assertEqual(result['delivered_candidates'],1);self.assertFalse(result['delivery_accepted'])

    def test_publisher_default_and_archive_are_distinct(self):
        self.decide()
        here=self.root/'creation_pipeline';run=here/'runs/run'
        shutil.copytree(self.skill,run/'drafts-v03'/self.skill.name)
        write(here/'results/run.json',{'status':'method_drafts_created','candidate_count':1,'paper_id':'paper-1'})
        argv=['publish_run','--run-id','run']
        with patch.object(publish_run,'HERE',here),patch.object(publish_run,'ROOT',self.root),patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(publish_run.main(),0)
        manifest=read(self.root/'skills/generated/run/PUBLISHING.json')
        self.assertTrue(manifest['delivery_accepted']);self.assertEqual(manifest['delivery_publication_state'],'accepted_delivery')

    def test_legacy_execution_recovery_cannot_hide_unselected_failure(self):
        self.decide()
        here=self.root/'pipeline';drafts=here/'runs/run/drafts-v03'
        shutil.copytree(self.skill,drafts/self.skill.name)
        other=drafts/'unresolved';c=copy.deepcopy(self.c);c.pop('tool_requirement');self.make(other,c)
        write(other/'delivery/requirement.json',delivery.determine(other,'paper-1'))
        write(here/'results/run.json',{'candidate_count':2})
        selected={'candidates':[{'path':str(drafts/self.skill.name),'runtime_status':'execution_passed','current_acceptance_validated':True}]}
        with patch.object(inspect_run,'HERE',here),patch.object(inspect_run,'inspect',return_value=selected), \
             patch('strict_acceptance.evaluate',return_value={'current_acceptance_validated':True}), \
             patch.object(sys,'argv',['inspect','--run-id','run','--candidate',self.skill.name,'--action','retry-runtime','--success-policy','execution']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(inspect_run.main(),2)
        result=read(here/'results/run.json')
        self.assertFalse(result['delivery_accepted'])
        self.assertEqual(result['delivered_candidates'],1)

    def test_real_main_default_text_and_draft(self):
        source=self.root/'paper.txt';source.write_text('Supported procedural evidence for the method.\n')
        config=self.root/'source.json'
        write(config,{'jobs':[{'paper_id':'paper-1','title':'Example','source_type':'paper',
                              'sources':[{'path':str(source),'role':'paper'}]}]})
        response=self.root/'response.json'
        write(response,{'contract_version':'1.1','schema_version':3,'paper_id':'paper-1','candidates':[self.c],'no_skill_reason':''})
        here=self.root/'pipeline';here.mkdir()
        original=Path(run_pipeline.__file__).parent
        def call(*args):
            script=Path(args[0]); actual=original/'core'/script.name if script.name=='creation.py' else original/script.name
            result=subprocess.run([sys.executable,str(actual),*args[1:]],capture_output=True,text=True,encoding='utf-8')
            if result.returncode:raise subprocess.CalledProcessError(result.returncode,args,output=result.stdout,stderr=result.stderr)
        for name,extra in [('default',[]),('draft',['--draft-only'])]:
            with patch.object(run_pipeline,'HERE',here),patch.object(run_pipeline,'call',side_effect=call), \
                 patch.object(sys,'argv',['run_pipeline','--config',str(config),'--response-file',str(response),'--run-id',name,*extra]),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run_pipeline.main(),0)
            result=read(here/'results'/f'{name}.json')
            self.assertEqual(result['delivery_accepted'],name=='default')


import test_runtime_model as baseline
import runtime_model_lifecycle as lifecycle
import runtime_package as runner
import relocate_runtime


class DeliveryRecoveryTests(unittest.TestCase):
    setUp=baseline.ModelRuntimeTests.setUp
    generate=baseline.ModelRuntimeTests.generate
    verified=baseline.ModelRuntimeTests.verified
    fake_process=baseline.ModelRuntimeTests.fake_process
    fake_case=baseline.ModelRuntimeTests.fake_case

    def seal(self):
        self.settings['tools']['double']['root']='source'
        write(self.bindings,self.settings)
        b=bundle();b['paper_id']='job'
        write(self.skill/'candidate.json',candidate_identity.identity(candidate(),b,'job'))
        delivery.seal_content(self.skill,candidate(),b)
        write(self.skill/'delivery/requirement.json',delivery.determine(self.skill,'job',self.bindings))

    def test_failed_validation_reuses_build_but_reexecutes_locked_business_cases(self):
        self.seal();self.verified()
        prior=read(self.skill/'runtime/execution.json');prior['status']='execution_failed'
        prior['tools'][0]['status']='execution_failed';write(self.skill/'runtime/execution.json',prior)
        def process(argv,*args,**kwargs):
            self.assertFalse(len(argv)>2 and argv[1:3]==['runtime/runner.py','build'],'Must reuse unchanged built image')
            return self.fake_process(argv,*args,**kwargs)
        with patch.object(runner,'process',side_effect=process),patch.object(runner,'run_case',side_effect=self.fake_case) as cases, \
             patch.object(lifecycle,'verify_examples',return_value=[]):
            result=delivery.retry(self.skill)
        self.assertEqual(result['status'],'execution_passed')
        self.assertGreaterEqual(cases.call_count,3)

    def relocated(self):
        self.seal();self.generate()
        destination=self.root/'relocated';destination.mkdir()
        shutil.copytree(self.source,destination/'source')
        shutil.copytree(self.skill,destination/self.skill.name)
        shutil.copyfile(self.bindings,destination/'bindings.json')
        return destination/self.skill.name,destination/'bindings.json'

    def test_portable_rebind_keeps_test_contract_and_invalidates_acceptance(self):
        skill,bindings=self.relocated()
        old=read(skill/'runtime/prepared.json')
        moved=relocate_runtime.relocate(skill,bindings)
        self.assertEqual(old['tools'][0]['locked_cases'],moved['tools'][0]['locked_cases'])
        self.assertEqual(moved['bindings_path'],str(bindings.resolve()))
        self.assertEqual(read(skill/'runtime/images.json')['tools'],{})
        self.assertFalse((skill/'runtime/execution.json').exists())

    def test_relocation_rejects_changed_sources_before_mutation(self):
        skill,bindings=self.relocated()
        original=(skill/'runtime/prepared.json').read_bytes()
        (bindings.parent/'source/cli.py').write_text('print(999)')
        with self.assertRaisesRegex(ValueError,'source inventory'):
            relocate_runtime.relocate(skill,bindings)
        self.assertEqual((skill/'runtime/prepared.json').read_bytes(),original)

    def test_relocation_rejects_changed_bindings(self):
        skill,bindings=self.relocated();bindings.write_text(bindings.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'byte-identical'):
            relocate_runtime.relocate(skill,bindings)

    def test_portable_cli_cannot_replan_after_build_failure(self):
        with patch.object(relocate_runtime,'relocate'),patch.object(delivery.runtime_docker,'validate',return_value={'status':'build_failed'}) as validate, \
             patch.object(delivery,'evaluate',return_value={'delivery_accepted':False}), \
             patch.object(sys,'argv',['relocate','candidate','--tool-bindings','bindings.json']),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(relocate_runtime.main(),2)
        self.assertEqual(validate.call_args.kwargs['budget']['max_attempts'],1)

    def test_zip_precision_restored_without_relaxing_context_guard(self):
        self.seal();self.generate()
        target=self.root/'zip-extracted';target.mkdir()
        archive=self.root/'sample.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for path in self.skill.rglob('*'):
                if path.is_file():z.write(path,Path(self.skill.name)/path.relative_to(self.skill))
        with zipfile.ZipFile(archive) as z:z.extractall(target)
        shutil.copytree(self.source,target/'source')
        shutil.copyfile(self.bindings,target/'bindings.json')
        skill=target/self.skill.name;tool=read(skill/'runtime/package.json')['tools']['double']
        with self.assertRaisesRegex(ValueError,'source context metadata'):runner.context(skill,tool)
        relocate_runtime.relocate(skill,target/'bindings.json')
        self.assertTrue(runner.context(skill,tool).is_dir())


if __name__=='__main__':unittest.main()
