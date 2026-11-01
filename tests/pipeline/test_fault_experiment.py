"""Offline regression for the actual library-interruption worker dispatch."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from creation_pipeline.records import read_json


class FaultExperimentTests(unittest.TestCase):
    def test_library_interrupt_worker_does_not_require_fixture_record(self):
        path=Path(__file__).resolve().parents[2]/'validation/deepseek-api/verify_tool_fault_isolation.py'
        spec=importlib.util.spec_from_file_location('fault_experiment',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            with patch.object(module,'resume_build',side_effect=KeyboardInterrupt('active execution')) as resume, \
                 patch.object(module.local,'process',side_effect=AssertionError('No Docker')):
                module.worker(directory,directory,'interrupt-execution')
            resume.assert_called_once_with(directory/'library','slow',reuse_image=True)
            self.assertEqual(read_json(directory/'interruption.json')['type'],'KeyboardInterrupt')
            self.assertFalse((directory/'record.json').exists())
        self.assertTrue(module.execution_command(['docker','run','--name','owned','sha256:tool'],'sha256:tool'))
        self.assertFalse(module.execution_command(['docker','run','--entrypoint','python','sha256:tool'],'sha256:tool'))
        self.assertFalse(module.execution_command(['python','runner.py'],'sha256:tool'))
