"""Prerequisite gates are hermetic and cannot admit model calls or qualification."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline import readiness
from creation_pipeline.models import load_config
from creation_pipeline.pipeline import build
from creation_pipeline.records import write_json, file_digest
from tests.pipeline.test_shared_tool import declaration


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir()
        (self.source/'main.py').write_text('print(1)\n')
        self.path=self.root/'config.json'
        self.raw={'sources':[{'id':'tool','path':str(self.source)}],'runtime_defaults':{'shared_tool':declaration()}}
        self.host=patch('creation_pipeline.runtime.local.LocalExecutor.host',return_value={'status':'available','engine_id':'test'})
        self.host_mock=self.host.start();self.addCleanup(self.host.stop)
        self.client=patch('creation_pipeline.agent.command.codex_command',return_value=['codex-fixture'])
        self.client.start();self.addCleanup(self.client.stop)
        self.addCleanup(patch.stopall)
        patch('creation_pipeline.runtime.model_call.call',side_effect=AssertionError('Model inference forbidden')).start()
        patch('creation_pipeline.agent.backend.NativeSession.stage',side_effect=AssertionError('Model inference forbidden')).start()

    def config(self):
        write_json(self.path,self.raw);return load_config(self.path)

    def test_ready_is_observation_not_qualification_and_has_no_side_effects(self):
        report=readiness.check(self.config())
        self.assertEqual(report['status'],'ready');self.assertEqual(report['qualification'],'not_granted')
        self.assertEqual(report['model_calls'],0);self.assertEqual(report['build_calls'],0)
        self.assertFalse((self.root/'state').exists())

    def test_bad_source_blocks_before_session_or_state(self):
        self.raw['sources'][0]['path']=str(self.root/'absent');self.config()
        with patch('creation_pipeline.pipeline.NativeSession',side_effect=AssertionError('No session')):
            result=build(self.path,self.root/'state')
        self.assertEqual(result['phase'],'readiness');self.assertEqual(result['model_calls'],0)
        gap=next(g for g in result['errors'] if g['code']=='source_unavailable')
        self.assertIn('absent',gap['path']);self.assertFalse(gap['actual']['exists'])
        self.assertFalse((self.root/'state').exists())

    def test_docker_is_required_only_for_known_executable_build(self):
        self.host_mock.return_value={'status':'unavailable','gaps':[{'code':'docker_unavailable'}]}
        config=self.config();self.assertEqual(readiness.check(config)['status'],'blocked')
        for mode in ('draft','discover'):
            report=readiness.check(config,mode)
            self.assertEqual(report['status'],'deferred');self.assertFalse(report['gaps'])
        self.host_mock.reset_mock();report=readiness.check(config,offline=True)
        self.host_mock.assert_not_called();self.assertEqual(report['status'],'deferred')

    def test_empty_source_digest_and_budgets(self):
        (self.source/'main.py').unlink()
        self.assertIn('source_empty',[g['code'] for g in readiness.check(self.config())['gaps']])
        (self.source/'main.py').write_text('print(1)')
        self.raw['sources'][0].update(path=str(self.source/'main.py'),sha256='0'*64)
        self.assertIn('source_digest_mismatch',[g['code'] for g in readiness.check(self.config())['gaps']])
        self.raw['sources'][0].pop('sha256');self.raw['limits']={'source_bytes':1}
        self.assertTrue(any('byte budget' in str(g['actual']) for g in readiness.check(self.config())['gaps']))

    def test_imported_local_module_is_checked_before_inference(self):
        (self.source/'main.py').write_text('import helper\n')
        (self.source/'helper.py').write_text('import subprocess\n')
        report=readiness.check(self.config())
        gap=next(g for g in report['gaps'] if g['code']=='tool_support_unresolved')
        self.assertIn('package/helper.py',gap['actual']);self.assertIn('external process',gap['actual'])

    def test_declared_json_is_verified_and_misplaced_data_named(self):
        from creation_pipeline.runtime import bundled_data as bd
        code='from pathlib import Path\nprint((Path(__file__).resolve().parent / "rules.json").read_text(encoding="utf-8"))\n'
        (self.source/'main.py').write_text(code);(self.source/'rules.json').write_text('{}')
        d=self.raw['runtime_defaults']['shared_tool'];d.update(policy=bd.POLICY,bundled_data=[
            {'module':'main.py','path':'rules.json','sha256':file_digest(self.source/'rules.json')}])
        self.assertEqual(readiness.check(self.config())['status'],'ready')
        (self.source/'rules.json').write_text('{"changed":1}')
        gap=readiness.check(self.config())['gaps'][0]
        self.assertIn('rules.json',gap['actual']);self.assertIn('expected sha256=',gap['actual'])

    def test_missing_explicit_version_and_changed_declaration_block(self):
        self.raw['runtime_defaults']['tool_artifact']={'request_key':'0'*64,'artifact_id':'1'*64}
        report=readiness.check(self.config())
        self.assertTrue(any(g['code']=='tool_artifact_unavailable' for g in report['gaps']))

    def test_remote_source_deferred_then_acquired_snapshot_is_checked(self):
        self.raw['sources']=[{'id':'tool','url':'https://example.invalid/source'}]
        config=self.config();report=readiness.check(config)
        self.assertEqual(report['status'],'deferred');self.assertTrue(report['source_acquisition_pending'])
        report=readiness.check(config,snapshots=[{'id':'tool','path':str(self.source)}])
        self.assertEqual(report['status'],'ready')

    def test_bad_configuration_is_structured(self):
        self.path.write_text('{}')
        report=readiness.from_config(self.path)
        self.assertEqual(report['gaps'][0]['path'],str(self.path));self.assertEqual(report['model_calls'],0)

    def test_missing_client_is_named_without_auth_probe(self):
        with patch('creation_pipeline.agent.command.codex_command',side_effect=ValueError('missing executable')):
            report=readiness.check(self.config())
        self.assertIn('model_client_unavailable',[g['code'] for g in report['gaps']])
