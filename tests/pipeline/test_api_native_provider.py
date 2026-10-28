"""Opt-in single-shot API execution for the native discovery/author/review stages.

The Codex CLI remains the default and is not exercised here (no process is spawned).
These tests pin the switch, the prompt additions, the author file contract and the
host-side materialisation, so the same stage contracts hold whichever provider runs.
"""
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from creation_pipeline.agent import api_provider, backend
from creation_pipeline.schemas import DELIVERY
from creation_pipeline.records import write_json

OK = {'ok': True}
AUTHOR_ANSWER = {
    'completed': True, 'summary': 'wrote the package',
    'files': [{'path': 'SKILL.md', 'content': '---\nname: demo\ndescription: demo\n---\n\nUse it.\n'},
              {'path': 'scripts/run.py', 'content': 'print(1)\n'}],
    'tests': [], 'issues': [], 'notes': [], 'runtime_requirement': {'status': 'not_required', 'reason': 'n/a', 'citations': []},
}


def session(tmp, backend_name='deepseek_api'):
    work = Path(tmp) / 'work'
    work.mkdir(parents=True, exist_ok=True)
    instance = object.__new__(backend.NativeSession)
    instance.config = {'model': {'backend': backend_name, 'api_model': 'deepseek-chat'}}
    instance.sources = SimpleNamespace(manifest=lambda: [], entries={}, evidence=[], limits={})
    instance.limits = {'model_calls': 12, 'total_seconds': 600, 'model_timeout': 30,
                       'agent_progress_timeout': None, 'agent_events': 1000}
    instance.work = work
    instance.receipts = []
    instance.state = {'sessions': {}, 'completed': {}}
    instance.state_path = work / 'agent-state.json'
    instance.model_name = 'deepseek-chat'
    instance.notify = lambda message: None
    instance.started = time.monotonic()
    instance.workspace = {'run': str(work), 'resource_count': 0}
    return instance


class SwitchTests(unittest.TestCase):
    def test_codex_stays_the_default_and_api_is_opt_in(self):
        self.assertEqual(api_provider.provider({}), 'codex_cli')
        self.assertFalse(api_provider.is_api({'model': {}}))
        self.assertFalse(api_provider.is_api({'model': {'backend': 'codex_cli'}}))
        self.assertTrue(api_provider.is_api({'model': {'backend': 'deepseek_api'}}))

    def test_the_author_schema_carries_the_files(self):
        schema = api_provider.author_schema(DELIVERY)
        self.assertIn('files', schema['properties'])
        self.assertIn('files', schema['required'])
        self.assertEqual(schema['properties']['files']['items']['required'], ['path', 'content'])
        # The original schema object is not mutated.
        self.assertNotIn('files', DELIVERY['properties'])

    def test_source_texts_are_inlined_and_budgeted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'a.py').write_text('print(1)\n', encoding='utf-8')
            (root / 'b.bin').write_bytes(b'\xff\xfe\x00binary')
            sources = [{'id': 's', 'path': str(root), 'inventory': [
                {'path': 'a.py', 'bytes': 9, 'sha256': 'x'},
                {'path': 'b.bin', 'bytes': 9, 'sha256': 'y'}]}]
            texts = api_provider.source_texts(sources, budget=40)
        self.assertEqual(texts[0]['text'], 'print(1)\n')
        self.assertEqual(texts[1]['omitted'], 'not UTF-8 text')

    def test_materialisation_writes_files_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging, metadata = Path(tmp) / 'pkg', Path(tmp) / 'meta.json'
            written = api_provider.materialize(AUTHOR_ANSWER, staging, metadata)
            self.assertEqual(sorted(written), ['SKILL.md', 'scripts/run.py'])
            self.assertTrue((staging / 'scripts/run.py').is_file())
            data = json.loads(metadata.read_text(encoding='utf-8'))
            self.assertEqual(data['runtime_requirement']['status'], 'not_required')
            self.assertNotIn('files', data)

    def test_materialisation_refuses_traversal_and_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging, metadata = Path(tmp) / 'pkg', Path(tmp) / 'meta.json'
            for bad in ({'completed': True, 'summary': '', 'files': [{'path': '../escape.py', 'content': 'x'}]},
                        {'completed': True, 'summary': '', 'files': [{'path': 'a.py', 'content': '\udcff'}]},
                        {'completed': True, 'summary': '', 'files': [{'path': '/abs.py', 'content': 'x'}]}):
                with self.assertRaises(ValueError):
                    api_provider.materialize(bad, staging, metadata)


class StageTests(unittest.TestCase):
    def test_a_discovery_stage_makes_one_api_call_and_records_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = session(tmp)
            instance.sources = SimpleNamespace(
                manifest=lambda: [], entries={}, limits={},
                evidence=[{'id': 'e1', 'source': 'recap', 'path': 'document.py'},
                          {'id': 'e2', 'source': 'license', 'path': 'document.txt'}])
            with patch.object(api_provider, 'call', return_value=(dict(OK), {'usage': {'total_tokens': 5},
                                                                            'finish_reason': 'stop',
                                                                            'elapsed_seconds': 0.1})) as call:
                answer = instance.stage('INSTRUCTIONS', {'_phase': 'discovery'}, schema={'type': 'object'})
            self.assertEqual(answer, OK)
            call.assert_called_once()
            receipt = instance.receipts[0]
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(receipt['phase'], 'discovery')
            folder = Path(tmp) / 'work/agent-turns/001-discovery'
            self.assertTrue((folder / 'prompt.txt').is_file())
            prompt = (folder / 'prompt.txt').read_text(encoding='utf-8')
            self.assertIn('API PROVIDER MODE', prompt)
            self.assertIn('SOURCE TEXTS', prompt)
            # The model can only cite locator ids it can see (run 20 invented one).
            self.assertIn('SOURCE EVIDENCE', prompt)
            self.assertIn('"e1"', prompt)
            self.assertIn('cite these ids only', prompt)
            self.assertEqual(json.loads((folder / 'result.json').read_text(encoding='utf-8')), OK)

    def test_an_author_stage_materialises_the_package_and_passes_host_finalisation(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = session(tmp)
            staging = Path(tmp) / 'bundle/skills/demo'
            metadata = Path(tmp) / 'deliveries' / 'demo-metadata.json'
            (Path(tmp) / 'resource-state.json').write_text(
                json.dumps({'config': {'limits': {'package_bytes': None}}}), encoding='utf-8')
            (Path(tmp) / 'active-phase.json').write_text(json.dumps({'phase': 'author'}), encoding='utf-8')
            context = {'_phase': 'author', 'plan': {'name': 'demo'},
                       'output_directory': str(staging), 'metadata_path': str(metadata)}
            with patch.object(api_provider, 'call', return_value=(dict(AUTHOR_ANSWER),
                                                                  {'usage': None, 'elapsed_seconds': 0.1})):
                answer = instance.stage('INSTRUCTIONS', context, schema=DELIVERY)
            self.assertTrue(answer['completed'])
            self.assertEqual(sorted(p.name for p in staging.iterdir()), ['SKILL.md', 'scripts'])
            from creation_pipeline.artifacts.delivery import finish
            result = finish(Path(tmp), staging, 'token', metadata)
            self.assertEqual(result['status'], 'saved')

    def test_a_failed_api_call_is_recorded_not_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = session(tmp)
            error = backend.ModelCallError('usage limit')
            with patch.object(api_provider, 'call', side_effect=error):
                with self.assertRaises(backend.ModelCallError):
                    instance.stage('INSTRUCTIONS', {'_phase': 'review'}, schema={'type': 'object'})
            self.assertEqual(instance.receipts[0]['status'], 'failed')
            self.assertIn('usage limit', instance.receipts[0]['error'])

    def test_codex_mode_still_reaches_the_cli_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = session(tmp, backend_name='codex_cli')
            with patch.object(backend, 'codex_command', side_effect=AssertionError('CLI path chosen')), \
                    patch.object(instance, 'refresh_sources', return_value=None):
                with self.assertRaises(AssertionError):
                    instance.stage('INSTRUCTIONS', {'_phase': 'discovery'}, schema={'type': 'object'})


if __name__ == '__main__':
    unittest.main()
