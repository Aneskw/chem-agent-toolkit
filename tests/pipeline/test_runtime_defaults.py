"""Shared runtime defaults: the provider options a normal creation needs up front."""
import json
import tempfile
import unittest
from pathlib import Path

from creation_pipeline.models import load_config
from creation_pipeline.pipeline import runtime_spec_for

BASE = {
    'sources': [{'path': '.'}],
    'prompt': 'demo',
    'model': {'name': 'm', 'transport': 'https', 'reasoning_effort': 'medium',
              'service_tier': 'default'},
}


class RuntimeDefaultsTests(unittest.TestCase):
    def load(self, extra):
        directory = tempfile.mkdtemp(prefix='runtime-defaults-')
        path = Path(directory) / 'input.json'
        path.write_text(json.dumps({**BASE, **extra}), encoding='utf-8', newline='\n')
        return load_config(path)

    def test_shared_defaults_survive_configuration_loading(self):
        config = self.load({'runtime_defaults': {'options': {
            'backend': 'deepseek_api', 'api_retries': 0, 'model_timeout': 600}}})
        self.assertEqual(config['runtime_defaults']['options']['backend'], 'deepseek_api')
        self.assertEqual(config['runtime'], {})

    def test_defaults_apply_when_no_candidate_spec_exists(self):
        config = self.load({'runtime_defaults': {'options': {'backend': 'deepseek_api'}}})
        spec = runtime_spec_for(config, 'anything-discovered')
        self.assertEqual(spec['options']['backend'], 'deepseek_api')

    def test_per_candidate_options_override_the_defaults_without_erasing_them(self):
        config = self.load({
            'runtime_defaults': {'options': {'backend': 'deepseek_api', 'api_retries': 0,
                                             'api_stream': True}},
            'runtime': {'named': {'options': {'backend': 'codex_cli'}}}})
        spec = runtime_spec_for(config, 'named')
        self.assertEqual(spec['options']['backend'], 'codex_cli')
        self.assertEqual(spec['options']['api_retries'], 0)
        self.assertTrue(spec['options']['api_stream'])

    def test_an_explicit_binding_in_a_candidate_spec_is_kept(self):
        config = self.load({
            'runtime_defaults': {'options': {'backend': 'deepseek_api'}},
            'runtime': {'named': {'binding': {'entry': 'scripts/x.py',
                                              'association': 'explicit',
                                              'source_id': 's', 'source_path': 'p.py',
                                              'quote': 'q', 'reason': 'r'}}}})
        spec = runtime_spec_for(config, 'named')
        self.assertEqual(spec['binding']['entry'], 'scripts/x.py')
        self.assertEqual(spec['options']['backend'], 'deepseek_api')

    def test_invalid_defaults_are_rejected(self):
        for bad in ({'options': {'backend': 'ollama'}},
                    {'options': {'api_retries': 9}},
                    {'unsupported': {}},
                    ['not', 'a', 'mapping']):
            with self.assertRaises(ValueError, msg=repr(bad)):
                self.load({'runtime_defaults': bad})


if __name__ == '__main__':
    unittest.main()
