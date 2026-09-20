import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from network_env import model_environment

class NetworkTests(unittest.TestCase):
    def test_explicit_proxy_wins(self):
        with patch.dict(os.environ,{'HTTPS_PROXY':'http://explicit:8888'},clear=True), patch('network_env.subprocess.run') as run:
            self.assertEqual(model_environment()['HTTPS_PROXY'],'http://explicit:8888');run.assert_not_called()
    def test_system_proxy_is_inherited_for_child_only(self):
        state='HTTPSEnable : 1\nHTTPSProxy : 127.0.0.1\nHTTPSPort : 7890\n'
        with patch.dict(os.environ,{},clear=True),patch('network_env.sys.platform','darwin'),patch('network_env.subprocess.run',return_value=SimpleNamespace(stdout=state)):
            env=model_environment();self.assertEqual(env['HTTPS_PROXY'],'http://127.0.0.1:7890')
            self.assertNotIn('HTTPS_PROXY',os.environ)
    def test_disabled_system_proxy_not_used(self):
        with patch.dict(os.environ,{},clear=True),patch('network_env.sys.platform','darwin'),patch('network_env.subprocess.run',return_value=SimpleNamespace(stdout='HTTPSEnable : 0\nHTTPSProxy : 127.0.0.1\nHTTPSPort : 7890\n')):
            self.assertNotIn('HTTPS_PROXY',model_environment())

if __name__=='__main__':unittest.main()
