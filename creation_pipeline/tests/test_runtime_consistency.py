"""Publication, explicit example ownership and immutable image reference regressions."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import publish_run
import publication_transaction as publication
import runtime_model_lifecycle as lifecycle
import runtime_package as runner
from runtime_common import read, write
import test_runtime_model as baseline


class PublicationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.pipeline = self.root / "creation_pipeline"
        self.out = self.root / "published"
        self.out.mkdir()
        self.drafts = self.pipeline / "runs/run/drafts-v03"
        for name in ("alpha", "beta"):
            path = self.drafts / name
            path.mkdir(parents=True)
            (path / "SKILL.md").write_text("new " + name)
        write(self.pipeline / "results/run.json", {"status": "method_drafts_created"})
        self.archive = self.out / "skills/generated/run"
        self.alpha = self.out / "tools-skills/generated/alpha"
        self.beta = self.out / "tools-skills/generated/beta"

    def publish(self, replace=False):
        with patch.object(publish_run, "HERE", self.pipeline), patch.object(publish_run, "ROOT", self.out), \
             patch("sys.argv", ["publish_run.py", "--success-policy", "archive", "--run-id", "run", "--category", "tool"] + (["--replace-existing"] if replace else [])):
            return publish_run.main()

    def old(self, path):
        path.mkdir(parents=True)
        (path / "sentinel").write_text("old")

    def test_later_classification_conflict_leaves_no_partial_publication(self):
        self.old(self.beta)
        with self.assertRaises(SystemExit):
            self.publish()
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.alpha.exists())
        self.assertEqual((self.beta / "sentinel").read_text(), "old")

    def test_copy_failure_does_not_destroy_existing_replacement(self):
        for p in (self.archive, self.alpha, self.beta): self.old(p)
        real_copy = shutil.copytree
        def copy(source, destination, *args, **kwargs):
            if Path(source).name == "beta": raise OSError("injected copy failure")
            return real_copy(source, destination, *args, **kwargs)
        with patch.object(publish_run.shutil, "copytree", side_effect=copy), self.assertRaises(OSError):
            self.publish(replace=True)
        for p in (self.archive, self.alpha, self.beta): self.assertEqual((p / "sentinel").read_text(), "old")

    def test_acceptance_exception_leaves_no_published_targets(self):
        with patch.object(publish_run, "validate_execution", side_effect=[{"status": "passed"}, RuntimeError("injected evidence exception")]), \
             self.assertRaises(RuntimeError):
            self.publish()
        for p in (self.archive, self.alpha, self.beta): self.assertFalse(p.exists())

    def test_first_conflict_is_detected_before_any_copy(self):
        self.old(self.alpha)
        with patch.object(publish_run.shutil, 'copytree') as copy, self.assertRaises(SystemExit):
            self.publish()
        copy.assert_not_called()
        self.assertFalse(self.archive.exists())

    def test_commit_failure_restores_all_existing_targets(self):
        for p in (self.archive, self.alpha, self.beta): self.old(p)
        real_move = publication.move
        def move(source, target):
            if Path(target) == self.beta and Path(source).name.startswith('stage-'):
                raise OSError('injected second install failure')
            return real_move(source, target)
        with patch.object(publication, 'move', side_effect=move), self.assertRaises(OSError):
            self.publish(replace=True)
        for p in (self.archive, self.alpha, self.beta): self.assertEqual((p / 'sentinel').read_text(), 'old')
        self.assertFalse((self.out/'.publication-transactions/lock').exists())

    def test_commit_failure_removes_new_targets(self):
        real_move = publication.move
        def move(source, target):
            if Path(target) == self.archive: raise OSError('injected last install failure')
            return real_move(source, target)
        with patch.object(publication, 'move', side_effect=move), self.assertRaises(OSError):
            self.publish()
        for p in (self.archive, self.alpha, self.beta): self.assertFalse(p.exists())

    def test_exception_after_rename_still_restores_backup(self):
        for p in (self.archive,self.alpha,self.beta): self.old(p)
        real_move=publication.move
        def move(source,target):
            real_move(source,target)
            if Path(target)==self.beta and Path(source).name.startswith('stage-'):
                raise OSError('injected failure after completed rename')
        with patch.object(publication,'move',side_effect=move),self.assertRaises(OSError):
            self.publish(replace=True)
        for p in (self.archive,self.alpha,self.beta): self.assertEqual((p/'sentinel').read_text(),'old')

    def test_explicit_replacement_commits_identical_checked_mirrors(self):
        for p in (self.archive, self.alpha, self.beta): self.old(p)
        self.assertEqual(self.publish(replace=True), 0)
        manifest = read(self.archive/'PUBLISHING.json')
        self.assertTrue(manifest['publication_complete'])
        for name,target in [('alpha',self.alpha),('beta',self.beta)]:
            self.assertEqual((target/'SKILL.md').read_bytes(),(self.archive/name/'SKILL.md').read_bytes())
            self.assertEqual(read(target/'reports/execution.json'),read(self.archive/name/'reports/execution.json'))
            self.assertFalse((target/'sentinel').exists())
        self.assertFalse(list((self.out/'.publication-transactions').iterdir()))

    def test_lock_prevents_concurrent_publications(self):
        lock = self.out/'.publication-transactions/lock'
        lock.parent.mkdir(); lock.write_text('other owner')
        with self.assertRaises(FileExistsError): self.publish()
        self.assertEqual(lock.read_text(),'other owner')
        self.assertFalse(self.archive.exists())

    def test_failed_rollback_preserves_original_backup_and_recovery_journal(self):
        for p in (self.archive,self.alpha,self.beta): self.old(p)
        real_move=publication.move
        def move(source,target):
            if Path(target)==self.beta and Path(source).name.startswith('stage-'):
                raise OSError('injected install failure')
            if Path(target)==self.alpha and Path(source).name.startswith('backup-'):
                raise OSError('injected restore lock')
            return real_move(source,target)
        with patch.object(publication,'move',side_effect=move),self.assertRaisesRegex(RuntimeError,'recovery'):
            self.publish(replace=True)
        journals=list((self.out/'.publication-transactions').glob('txn-*/transaction.json'))
        self.assertEqual(len(journals),1)
        journal=read(journals[0]);self.assertEqual(journal['state'],'recovery_required')
        alpha=next(e for e in journal['entries'] if Path(e['target'])==self.alpha)
        self.assertEqual((Path(alpha['backup'])/'sentinel').read_text(),'old')
        self.assertEqual((self.archive/'sentinel').read_text(),'old')
        with self.assertRaisesRegex(RuntimeError,'recovery required'):
            self.publish(replace=True)
        self.assertEqual((Path(alpha['backup'])/'sentinel').read_text(),'old')

    def test_batch_duplicate_candidate_reports_conflict_without_overwrite(self):
        import batch_pipeline
        manifest=self.root/'batch.json'
        write(manifest, {'jobs':[{'paper_id':'one','sources':[]},{'paper_id':'two','sources':[]}]})
        def process(argv, **kwargs):
            run_id=argv[argv.index('--run-id')+1]
            if Path(argv[1]).name=='run_pipeline.py':
                path=self.pipeline/'runs'/run_id/'drafts-v03/shared'
                path.mkdir(parents=True);(path/'SKILL.md').write_text(run_id)
                write(self.pipeline/'results'/f'{run_id}.json',{'status':'method_drafts_created','candidate_count':1})
                return subprocess.CompletedProcess(argv,0,'','')
            stderr=io.StringIO()
            with patch.object(publish_run,'HERE',self.pipeline), patch.object(publish_run,'ROOT',self.out), \
                 patch('sys.argv',['publish_run.py','--success-policy','archive','--run-id',run_id]), contextlib.redirect_stderr(stderr):
                try: code=publish_run.main()
                except SystemExit as exc: code=exc.code
            return subprocess.CompletedProcess(argv,code,'',stderr.getvalue())
        with patch.object(batch_pipeline,'HERE',self.pipeline),patch.object(batch_pipeline,'ROOT',self.out), \
             patch.object(batch_pipeline.subprocess,'run',side_effect=process), \
             patch('sys.argv',['batch_pipeline.py','--manifest',str(manifest),'--prefix','collision']):
            self.assertEqual(batch_pipeline.main(),1)
        report=read(self.pipeline/'results/collision-batch.json')
        self.assertEqual(report['status'],'finished_with_errors')
        self.assertEqual(report['published_candidates'],1)
        self.assertEqual(report['runs'][1]['publish_error_kind'],'target_conflict')
        self.assertFalse((self.out/'skills/generated/collision-two-r01').exists())
        self.assertEqual((self.out/'workflows/generated/shared/SKILL.md').read_text(),'collision-one-r01')


class ExampleAndImageTests(unittest.TestCase):
    setUp = baseline.ModelRuntimeTests.setUp
    generate = baseline.ModelRuntimeTests.generate
    fake_process = baseline.ModelRuntimeTests.fake_process
    fake_case = baseline.ModelRuntimeTests.fake_case
    verified = baseline.ModelRuntimeTests.verified

    def multi(self):
        self.settings['tools'] = {key: {"root": str(self.source)} for key in ("calc", "calc-extra")}
        self.settings['bindings'][0]['tools'] = ["calc", "calc-extra"]
        write(self.bindings, self.settings)
        self.plan['tests'][1]['name'] = 'build'
        self.plan['tests'][2]['name'] = 'usage'
        self.generate()

    def test_prefix_tools_and_reserved_test_names_run_exactly_once(self):
        self.multi()
        commands = []
        def process(argv, timeout=60, cwd=None):
            commands.append(argv)
            return {"exit_code": 0, "stdout": "6", "stderr": ""}
        with patch.object(runner, 'process', side_effect=process):
            results = lifecycle.verify_examples(self.skill, 'calc', time.monotonic()+60)
        self.assertEqual(len(results), 5)  # four case commands (including rejection) + one raw usage
        self.assertEqual(sum('--case' in c and c[c.index('--case')+1]=='build' for c in commands), 1)
        self.assertTrue(all(c[c.index('--tool')+1]=='calc' for c in commands))
        examples = read(self.skill/'runtime/examples.json')['examples']
        self.assertTrue(all('tool_id' in e and 'kind' in e for e in examples))
        for key in ('calc', 'calc-extra'):
            self.assertEqual(sum(e['tool_id']==key and e['kind']=='build' for e in examples), 1)
            self.assertEqual(sum(e['tool_id']==key and e['kind']=='usage' for e in examples), 1)

    def test_same_plan_different_context_does_not_share_build_tag(self):
        self.generate()
        first = read(self.skill/'runtime/package.json')['tools']['double']['local_tag']
        (self.source/'cli.py').write_text("print(6) # different source bytes\n")
        self.generate()
        second = read(self.skill/'runtime/package.json')['tools']['double']['local_tag']
        self.assertNotEqual(first, second)

    def test_preparation_failure_counts_only_the_command_that_ran(self):
        from runtime_examples import counts, identity
        failed={**identity('calc','usage','build'), 'executed':False, 'preparation':[{'exit_code':2}]}
        result=counts([failed])
        self.assertEqual(result['commands'],1)
        self.assertEqual(result['preparation_commands'],1)
        self.assertEqual(result['run_commands'],0)

    def test_prepare_inputs_rejects_another_tools_usage_example(self):
        self.multi()
        with patch.object(runner,'__file__',str(self.skill/'runtime/runner.py')), \
             patch('sys.argv',['runner.py','prepare-inputs','--tool','calc','--example','calc-extra-usage']), \
             contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            runner.main()

    def test_documentation_engine_failure_is_not_a_dependency_repair(self):
        self.generate()
        with patch.object(runner,'process',return_value={'exit_code':1,'stdout':'','stderr':'Cannot connect to the Docker daemon'}), \
             self.assertRaises(lifecycle.InfrastructureFailure):
            lifecycle.verify_examples(self.skill,'double',time.monotonic()+60)

    def test_runner_run_case_test_all_use_the_accepted_id(self):
        report=self.verified(); expected=report['tools'][0]['image_id']
        tool=read(self.skill/'runtime/package.json')['tools']['double']
        for action in ('run','case','test'):
            argv=['runner.py',action,'--tool','double']
            if action=='case': argv+=['--case','double']
            if action=='run': argv+=['--','3']
            result={'exit_code':0,'stdout':'6','stderr':'','status':'passed' if action=='case' else 'execution_passed'}
            operation={'run':'run','case':'run_case','test':'tests'}[action]
            with patch.object(runner,'__file__',str(self.skill/'runtime/runner.py')),patch('sys.argv',argv), \
                 patch.object(runner,'process',side_effect=self.fake_process),patch.object(runner,operation,return_value=result) as call,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(),0)
                self.assertEqual(call.call_args.args[1 if action=='run' else 2],expected)
                self.assertNotEqual(expected,tool['local_tag'])

    def test_missing_binding_never_falls_back_to_build_tag(self):
        self.generate()
        with patch.object(runner,'process') as process,self.assertRaisesRegex(ValueError,'No verified image binding'):
            runner.verified_image(self.skill,'double')
        process.assert_not_called()

    def test_context_drift_blocks_both_runner_and_publication_evidence(self):
        self.verified()
        (self.skill/'runtime/tools/double/context/cli.py').write_text('print(999)')
        with patch.object(runner,'process') as process,self.assertRaisesRegex(ValueError,'inputs changed'):
            runner.verified_image(self.skill,'double')
        process.assert_not_called()
        self.assertEqual(lifecycle.evidence(self.skill)['status'],'needs_review')

    def test_missing_or_moved_retention_reference_never_falls_back(self):
        self.verified()
        for response in ({'exit_code':1,'stdout':'','stderr':'missing'}, {'exit_code':0,'stdout':'sha256:'+'b'*64,'stderr':''}):
            with patch.object(runner,'process',return_value=response) as process,self.assertRaisesRegex(ValueError,'no tag fallback'):
                runner.verified_image(self.skill,'double')
            self.assertEqual(process.call_count,1)

    def test_rebuild_only_returns_new_id_and_preserves_acceptance_binding(self):
        original=self.verified(); binding=(self.skill/'runtime/images.json').read_bytes()
        tool=read(self.skill/'runtime/package.json')['tools']['double']
        def build(argv,*args,**kwargs):
            Path(argv[argv.index('--iidfile')+1]).write_text('sha256:'+'b'*64)
            return {'exit_code':0,'stdout':'built B','stderr':''}
        with patch.object(runner,'process',side_effect=build):
            result=runner.build(self.skill,tool)
        self.assertEqual(result['image_id'],'sha256:'+'b'*64)
        self.assertEqual((self.skill/'runtime/images.json').read_bytes(),binding)
        with patch.object(runner,'process',side_effect=self.fake_process):
            self.assertEqual(runner.verified_image(self.skill,'double'),original['tools'][0]['image_id'])

    def test_build_id_is_inspected_instead_of_mutable_tag(self):
        report=self.verified()
        self.assertEqual(read(self.skill/'runtime/images.json')['tools']['double']['image_id'],report['tools'][0]['image_id'])
        with patch.object(runner,'process',side_effect=self.fake_process) as process:
            self.assertEqual(lifecycle.evidence(self.skill)['status'],'execution_passed')
        tool=read(self.skill/'runtime/package.json')['tools']['double']
        self.assertNotIn(tool['local_tag'],[str(a) for call in process.call_args_list for a in call.args[0]])

    def test_legacy_schema_three_cannot_be_recertified_with_an_old_runner(self):
        from runtime_common import artifacts
        self.generate()
        package=read(self.skill/'runtime/package.json');package.pop('image_binding_version')
        write(self.skill/'runtime/package.json',package)
        prepared=read(self.skill/'runtime/prepared.json');prepared['artifacts']=artifacts(self.skill)
        write(self.skill/'runtime/prepared.json',prepared)
        with patch.object(runner,'process',side_effect=AssertionError('Must stop before Docker')):
            result=lifecycle.validate(self.skill)
        self.assertEqual(result['status'],'needs_review')
        self.assertTrue(result['requires_prepare'])
        self.assertIn('Legacy schema 3',result['error'])

    def test_build_receipt_and_inspected_id_mismatch_stops_without_repair(self):
        self.generate()
        def process(argv,*args,**kwargs):
            result=self.fake_process(argv,*args,**kwargs)
            if argv[:3]==['docker','image','inspect'] and '--format' not in argv:
                info=json.loads(result['stdout']);info[0]['Id']='sha256:'+'b'*64;result['stdout']=json.dumps(info)
            return result
        with patch.object(runner,'process',side_effect=process),patch('model_call.call',side_effect=AssertionError('No integrity bypass')):
            result=lifecycle.validate(self.skill)
        self.assertEqual(result['status'],'needs_review')
        self.assertTrue(result['requires_prepare'])

    def test_legacy_examples_withdraw_stale_claims_during_staged_publication(self):
        self.verified()
        examples=read(self.skill/'runtime/examples.json')
        for example in examples['examples']: example.pop('tool_id',None)
        write(self.skill/'runtime/examples.json',examples)
        pipeline=self.root/'pipeline'; draft=pipeline/'runs/legacy/drafts-v03'/self.skill.name
        shutil.copytree(self.skill,draft)
        write(pipeline/'results/legacy.json',{'status':'method_drafts_created','runtime_mode':'docker'})
        output=self.root/'local-publish';output.mkdir()
        with patch.object(publish_run,'HERE',pipeline),patch.object(publish_run,'ROOT',output), \
             patch('sys.argv',['publish_run.py','--success-policy','archive','--run-id','legacy']):
            self.assertEqual(publish_run.main(),0)
        manifest=read(output/'skills/generated/legacy/PUBLISHING.json')
        self.assertFalse(manifest['execution_validated'])
        published=output/'skills/generated/legacy'/self.skill.name
        self.assertIn('NOT been accepted',(published/'SKILL.md').read_text())
        self.assertIn('not accepted',(published/'DOCKER.md').read_text())


if __name__ == '__main__':
    unittest.main()
