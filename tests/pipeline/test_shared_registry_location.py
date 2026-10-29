"""Explicit host sharing does not alter frozen inputs or ordinary build paths."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock,patch

from creation_pipeline.cli import main
from creation_pipeline.paths import ROOT
from creation_pipeline.runtime.shared_environment import CACHE_ROOT_ENV,registry_root,resolve
from tests.pipeline import test_shared_environment as fixtures


class SharedRegistryLocationTests(unittest.TestCase):
    def fixture(self):
        fixture=fixtures.SharedEnvironmentTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def test_default_and_explicit_absolute_location_are_pure_host_configuration(self):
        with patch.dict(os.environ,{CACHE_ROOT_ENV:''}):
            self.assertEqual(registry_root(),ROOT/'.pipeline/shared-environments')
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'common-cache'
            with patch.dict(os.environ,{CACHE_ROOT_ENV:str(target)}):
                self.assertEqual(registry_root(),target)
            self.assertFalse(target.exists())

    def test_two_resolutions_use_the_configured_root_without_changing_frozen_materials(self):
        fixture=self.fixture()
        target=fixture.root/'host-common-cache'
        before=(fixture.materials/'shared-environment.json').read_bytes()
        observations=[]
        with patch.dict(os.environ,{CACHE_ROOT_ENV:str(target)}):
            for name in ('first','second'):
                attempt=fixture.root/name; attempt.mkdir()
                _,observation,_=resolve(fixture.materials,None,{'engine_id':'daemon-a'},
                    fixture.process,time.monotonic()+30,attempt)
                observations.append(observation)
        self.assertEqual([o['status'] for o in observations],['built','hit'])
        self.assertEqual(fixture.builds,1)
        self.assertTrue(all(o['registry']==str(target) for o in observations))
        self.assertEqual((fixture.materials/'shared-environment.json').read_bytes(),before)
        self.assertFalse(fixture.cache.exists())

    def test_relative_host_setting_is_rejected_only_when_sharing_is_applicable(self):
        fixture=self.fixture()
        process=Mock(side_effect=AssertionError('No Docker call expected'))
        with patch.dict(os.environ,{CACHE_ROOT_ENV:'relative-cache'}):
            attempt=fixture.root/'first'; attempt.mkdir()
            with self.assertRaisesRegex(ValueError,'absolute shared environment directory'):
                resolve(fixture.materials,None,{'engine_id':'daemon-a'},process,time.monotonic()+30,attempt)
            (fixture.materials/'shared-environment.json').unlink()
            _,observation,_=resolve(fixture.materials,None,{'engine_id':'daemon-a'},process,
                                    time.monotonic()+30,attempt)
        self.assertEqual(observation,{'status':'not_applicable'})
        process.assert_not_called()

    def test_cli_default_uses_host_setting_and_explicit_root_can_override_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'host-cache'
            with patch.dict(os.environ,{CACHE_ROOT_ENV:str(target)}), \
                 patch('creation_pipeline.runtime.shared_inspection.inspect_registry',return_value={'status':'inspected'}) as inspect, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['runtime-shared-inspect','--offline']),0)
            inspect.assert_called_once_with(target,offline=True)
            with patch.dict(os.environ,{CACHE_ROOT_ENV:'relative-invalid'}), \
                 patch('creation_pipeline.runtime.shared_inspection.inspect_registry',return_value={'status':'inspected'}) as inspect, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['runtime-shared-inspect','--root',str(target),'--offline']),0)
            inspect.assert_called_once_with(str(target),offline=True)


if __name__=='__main__':
    unittest.main()
