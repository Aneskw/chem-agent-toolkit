"""Cancellation cleans only owned processes/containers; never starts Docker."""
import subprocess
import unittest
from unittest.mock import MagicMock, patch
from creation_pipeline.runtime import runner


class ProcessCancellationTests(unittest.TestCase):
    def test_direct_docker_interrupt_retains_owned_container_cleanup_and_scope(self):
        interrupted=KeyboardInterrupt('cancel active business')
        with patch.object(runner,'process',side_effect=[interrupted,{'exit_code':0}]) as command:
            with self.assertRaises(KeyboardInterrupt) as raised:
                runner.run({'limits':{},'behavior':{'file_io':False},'execution_scope':'current-attempt'},
                           'sha256:dedicated',[],timeout=2)
        self.assertEqual(raised.exception.scope,'current-attempt')
        self.assertEqual(raised.exception.cleanup,[{'exit_code':0}])
        created=command.call_args_list[0].args[0]
        owned=created[created.index('--name')+1]
        self.assertEqual(command.call_args_list[1].args[0],['docker','rm','--force',owned])

    def test_interrupt_has_same_owned_cleanup_as_timeout(self):
        for exception in (KeyboardInterrupt('cancel'), subprocess.TimeoutExpired('runner', 1)):
            with self.subTest(exception=type(exception).__name__):
                child = MagicMock()
                child.communicate.side_effect = [exception, ('partial', 'stderr')]
                child.returncode = -1
                job = MagicMock()
                with patch.object(runner, 'WindowsProcessJob', return_value=job), \
                     patch.object(runner.subprocess, 'Popen', return_value=child), \
                     patch.object(runner, 'stop_process_tree') as stop, \
                     patch.object(runner, 'cleanup_scope', return_value=[{'phase':'owned'}]) as cleanup:
                    with self.assertRaises(type(exception)) as raised:
                        runner.process(['python','runner.py'], timeout=1)
                cleanup.assert_called_once_with(raised.exception.scope)
                self.assertTrue(raised.exception.scope)
                self.assertEqual(raised.exception.output, 'partial')
                self.assertIn({'phase':'owned'}, raised.exception.cleanup)
                self.assertTrue(job.terminate.called or stop.called)

    def test_cancelled_unscoped_command_never_removes_containers(self):
        child = MagicMock(); child.communicate.side_effect = [KeyboardInterrupt(), ('','')]
        with patch.object(runner, 'WindowsProcessJob', return_value=MagicMock()), \
             patch.object(runner.subprocess, 'Popen', return_value=child), \
             patch.object(runner, 'stop_process_tree'), patch.object(runner, 'cleanup_scope') as cleanup:
            with self.assertRaises(KeyboardInterrupt):
                runner.process(['docker','build'], timeout=1)
        cleanup.assert_not_called()
