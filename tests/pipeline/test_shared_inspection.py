import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from creation_pipeline.contracts import fingerprint
from creation_pipeline.records import write_json
from creation_pipeline.runtime.shared_inspection import inspect_registry


class SharedInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'registry'; self.root.mkdir()
        self.recipe={'platform':'linux/amd64','base':'python@sha256:'+'a'*64}
        self.key=fingerprint(self.recipe); self.image='sha256:'+'b'*64
        self.path=self.root/(self.key+'.json')
        write_json(self.path,{'recipe':self.recipe,'image_id':self.image,'daemon_id':'one','complete_rebuild_lock':False})
        self.executor=Mock(); self.executor.host.return_value={'status':'available','engine_id':'one'}
        self.probe=Mock(return_value={'exit_code':0,'stdout':json.dumps([{'Id':self.image,'Os':'linux','Architecture':'amd64',
            'Config':{'Labels':{'chem.shared.recipe':self.key}}}])})

    def inspect(self):
        return inspect_registry(self.root,executor=self.executor,probe=self.probe)

    def test_available_is_identity_observation_not_skill_pass(self):
        before=self.path.read_bytes(); result=self.inspect()
        self.assertEqual(result['counts'],{'available':1})
        self.assertEqual(result['qualification'],'not_evaluated')
        self.assertEqual(self.path.read_bytes(),before)
        self.assertFalse(result['entries'][0]['complete_rebuild_lock'])

    def test_offline_never_calls_daemon_or_probe(self):
        result=inspect_registry(self.root,offline=True,executor=self.executor,probe=self.probe)
        self.executor.host.assert_not_called(); self.probe.assert_not_called()
        self.assertEqual(result['entries'][0]['status'],'historical_unverified')

    def test_foreign_daemon_is_not_local_available_image(self):
        self.executor.host.return_value['engine_id']='two'
        self.assertEqual(self.inspect()['entries'][0]['status'],'different_daemon')
        self.probe.assert_not_called()

    def test_corrupt_record_and_partial_build_never_available(self):
        self.path.write_text('{broken')
        (self.root/('c'*64+'.lock')).write_text('123')
        result=self.inspect()
        self.assertEqual(result['counts'],{'invalid_record':1,'pending_or_interrupted':1})
        self.probe.assert_not_called()

    def test_missing_image_and_label_mismatch_are_unavailable(self):
        self.probe.return_value={'exit_code':1,'stdout':''}
        self.assertEqual(self.inspect()['entries'][0]['status'],'image_unavailable_or_changed')
        self.probe.return_value={'exit_code':0,'stdout':json.dumps([{'Id':self.image,'Os':'linux','Architecture':'amd64','Config':{'Labels':{}}}])}
        self.assertEqual(self.inspect()['entries'][0]['status'],'image_unavailable_or_changed')

    def test_cli_offline_route_and_missing_root_do_not_create_records(self):
        from creation_pipeline.cli import main
        missing=Path(self.temp.name)/'absent'
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):
            code=main(['runtime-shared-inspect','--root',str(missing),'--offline'])
        self.assertEqual(code,0); self.assertFalse(missing.exists())
        self.assertEqual(json.loads(stream.getvalue())['entries'],[])

    def test_historical_metadata_output_uses_existing_redaction(self):
        self.path.unlink()
        self.recipe['base']='https://user:dummy-private-value@example.com/image'
        key=fingerprint(self.recipe)
        write_json(self.root/(key+'.json'),{'recipe':self.recipe,'image_id':self.image,'daemon_id':'one'})
        result=inspect_registry(self.root,offline=True)
        self.assertNotIn('dummy-private-value',json.dumps(result))
        self.assertIn('[REDACTED]',result['entries'][0]['base'])
