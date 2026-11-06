"""Caller layout obligations remain effective across receipts, freeze and qualification.

Offline only: stage decisions are simulated; no model or Docker may be started.
"""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.artifacts.layout import extract, problems, validate
from creation_pipeline.artifacts.delivery import validate_package
from creation_pipeline.artifacts.package import install, manifest
from creation_pipeline.cli import main
from creation_pipeline.contracts import fingerprint, qualify, versioned
from creation_pipeline.models import load_legacy_config as load_config
from creation_pipeline.records import read_json, write_json
from tests.pipeline import test_discovery as fixtures
from tests.pipeline.test_delivery_protocol import configure_text, text_artifact


class LayoutContractTests(unittest.TestCase):
    def test_explicit_list_is_generic_and_keeps_original_provenance(self):
        prompt = 'Deliver exactly SKILL.md, scripts/main.py and deps.lock; preserve the source bytes.'
        layout = extract({'prompt': prompt})
        self.assertEqual(layout['required_files'], ['SKILL.md', 'deps.lock', 'scripts/main.py'])
        self.assertEqual(layout['exact_files'], layout['required_files'])
        self.assertEqual(layout['inputs'], [{'field': 'prompt', 'text': prompt}])
        self.assertIn('Deliver exactly', layout['origins']['deps.lock'][0]['quote'])

    def test_required_root_and_nested_paths_without_exact_file_list(self):
        for text in ('`deps.lock` must be at package root.', 'deps.lock is required in the package root.',
                     '`deps.lock`必须位于包根目录。'):
            with self.subTest(text=text):
                value = extract({'prompt': text, 'constraints': {'delivery_layout': {
                    'required_files': ['scripts/sub/main.py']}}})
                self.assertEqual(value['required_files'], ['deps.lock', 'scripts/sub/main.py'])
                self.assertIsNone(value['exact_files'])

    def test_numbered_and_chinese_explicit_file_lists(self):
        for text in ('Deliver EXACTLY two files: SKILL.md and scripts/run.py. Preserve bytes.',
                     '交付仅包含：SKILL.md、scripts/run.py。不要重写源码。',
                     'Required delivered files: SKILL.md, scripts/run.py; extras allowed.'):
            with self.subTest(text=text):
                self.assertEqual(extract({'prompt': text})['required_files'], ['SKILL.md', 'scripts/run.py'])

    def test_a_dependency_or_source_mention_does_not_assign_a_root_path(self):
        value = extract({'prompt': 'Preserve requirements.txt pins; inspect execution/fixtures.json.'})
        self.assertEqual(value['required_files'], [])
        self.assertIsNone(value['exact_files'])

    def test_structured_arbitrary_paths_and_runtime_candidate_scope(self):
        value = extract({'constraints': {'delivery_layout': {'required_files': ['data files/input.bin']}},
            'runtime': {'a': {'constraints': ['Required files: scripts/a.py;']},
                        'b': {'constraints': ['Required files: scripts/b.py;']}}}, 'a')
        self.assertIn('data files/input.bin', value['required_files'])
        self.assertIn('scripts/a.py', value['required_files'])
        self.assertNotIn('scripts/b.py', value['required_files'])

    def test_unsafe_paths_conflicts_and_ambiguous_explicit_lists_fail_closed(self):
        for path in ('../secret.txt', '/tmp/file', 'C:/file', 'x\\file', '.env', 'x//a', 'a/*'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                extract({'constraints': {'delivery_layout': {'required_files': [path]}}})
        for text in ('Deliver exactly the files needed for this tool.',
                     'Deliver exactly SKILL.md; other.lock must be at package root.',
                     'Deliver exactly SKILL.md, a.py; Deliver exactly SKILL.md, b.py;'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                extract({'prompt': text})

    def test_actual_path_and_case_are_checked_independently_of_file_bytes(self):
        value = extract({'prompt': 'Deliver exactly SKILL.md and deps.lock;'})
        for actual in ('resources/deps.lock', 'Deps.lock'):
            with self.subTest(actual=actual):
                findings = problems([{'path': 'SKILL.md'}, {'path': actual}], value)
                missing = findings[0]
                self.assertEqual(missing['path'], 'deps.lock')
                self.assertTrue(missing['expected']['present'])
                self.assertFalse(missing['actual']['present'])
                self.assertEqual(missing['actual']['other_paths'], [actual])
                self.assertEqual(findings[1]['code'], 'unexpected_delivery_file')

    def test_removed_obligation_cannot_be_hidden_by_rehashing_only_the_contract(self):
        value = extract({'prompt': 'Deliver exactly SKILL.md and deps.lock;'})
        value['required_files'].remove('deps.lock')
        with self.assertRaisesRegex(ValueError, 'original requirement snapshots'):
            validate(value)

    def test_explicit_path_exception_preserves_default_roles_and_exclusions(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            (package/'SKILL.md').write_text('A skill', encoding='utf-8')
            (package/'deps.lock').write_text('version=1', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unsupported file role: deps.lock'):
                validate_package(package)
            value = extract({'prompt': 'deps.lock must be at package root.'})
            self.assertEqual(len(validate_package(package, layout=value)), 2)
            (package/'extra.txt').write_text('extra', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unsupported file role: extra.txt'):
                validate_package(package, layout=value)


class LayoutPipelineTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.DiscoveryTests()
        self.case.setUp()
        configure_text(self.case)
        self.case.options['prompt'] = 'Deliver exactly SKILL.md and deps.lock; retain the reading checklist.'
        self.case.options['limits']['repair_rounds'] = 0
        self.case.options['adoption']['enabled'] = True
        write_json(self.case.config, self.case.options)
        self.block_models = patch('creation_pipeline.runtime.model_call.call', side_effect=AssertionError('Live model'))
        self.block_docker = patch('creation_pipeline.runtime.local.process', side_effect=AssertionError('Live Docker'))
        self.block_models.start()
        self.block_docker.start()

    def tearDown(self):
        self.block_models.stop()
        self.block_docker.stop()
        self.case.tearDown()

    def artifact(self, path):
        artifact = text_artifact()
        artifact['files'].append({'path': path, 'content': 'version=1\n', 'purpose': 'Caller-required file'})
        return artifact

    def run_layout(self, path):
        result, _ = self.case.run_case(fixtures.discovery(fixtures.candidate()), self.artifact(path))
        output = Path(result['output'])
        return result, read_json(output/'records/add-numbers.json')

    def cli(self, *argv):
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main(list(argv))
        return code, json.loads(stream.getvalue())

    def test_wrong_layout_is_refused_before_review_planning_and_publication(self):
        result, record = self.run_layout('resources/deps.lock')
        self.assertEqual(result['status'], 'failed', result)
        self.assertIn('deps.lock', record['error'])
        self.assertIn('resources/deps.lock', record['error'])
        self.assertFalse(record['delivery']['qualification']['accepted'])
        self.assertEqual([r['phase'] for r in record['model_calls']], ['author'])

    def test_correct_layout_is_reviewed_frozen_installable_and_cli_audited(self):
        result, record = self.run_layout('deps.lock')
        self.assertEqual(result['status'], 'ready', result)
        self.assertEqual(record['delivery']['protocol'], 2)
        self.assertIn('review', [r['phase'] for r in record['model_calls']])
        self.assertTrue(qualify(record['delivery'])[0])
        self.assertEqual(record['delivery']['inputs']['layout']['payload'], extract(load_config(self.case.config), record['name']))
        installed = install(result['output'], self.case.root/'installed')
        self.assertTrue(installed)
        for path in (result['output'], str(Path(result['output'])/'bundle/skills/add-numbers')):
            code, audit = self.cli('check', path, '--config', str(self.case.config))
            self.assertEqual(code, 0, audit)
            self.assertEqual(next(c for c in audit['checks'] if c['name']=='delivery_layout')['status'], 'pass')

    def test_passed_review_and_business_flags_cannot_waive_missing_file(self):
        _, record = self.run_layout('deps.lock')
        delivery = copy.deepcopy(record['delivery'])
        next(f for f in delivery['inputs']['files'] if f['path']=='deps.lock')['path'] = 'resources/deps.lock'
        delivery['fingerprints']['files'] = fingerprint(delivery['inputs']['files'])
        delivery['revision_id'] = 'rev-' + fingerprint(delivery['inputs'])
        delivery['content']['status'] = 'passed'
        delivery['execution']['status'] = 'passed'
        delivery['qualification'] = {'accepted': True, 'reason': 'untrusted old flag'}
        with patch('creation_pipeline.runtime.service.verify_attempt', side_effect=AssertionError('Layout was not checked first')):
            ok, reason = qualify(delivery)
        self.assertFalse(ok)
        self.assertIn('Delivery layout mismatch', reason)
        self.assertIn('resources/deps.lock', reason)

    def test_protocol_two_cannot_omit_layout_and_protocol_one_remains_readable(self):
        _, record = self.run_layout('deps.lock')
        delivery = copy.deepcopy(record['delivery'])
        del delivery['inputs']['layout']
        del delivery['fingerprints']['layout']
        delivery['revision_id'] = 'rev-' + fingerprint(delivery['inputs'])
        self.assertIn('requires the frozen caller layout', qualify(delivery)[1])
        delivery['protocol'] = 1
        self.assertTrue(qualify(delivery)[0])

    def test_cli_original_config_detects_legacy_layout_without_changing_old_qualification(self):
        # A legacy package has no frozen caller layout. Re-audit using the original
        # config, rather than assuming its recorded ready flag proves that request.
        self.case.options['prompt'] = 'Retain the reading checklist.'
        write_json(self.case.config, self.case.options)
        result, record = self.run_layout('resources/deps.lock')
        self.assertEqual(result['status'], 'ready')
        before = manifest(Path(result['output']))
        self.case.options['prompt'] = 'Deliver exactly SKILL.md and deps.lock; retain the reading checklist.'
        write_json(self.case.config, self.case.options)
        code, audit = self.cli('check', result['output'], '--config', str(self.case.config))
        self.assertEqual(code, 1)
        self.assertEqual(audit['scope'], 'static_only_not_new_qualification')
        finding = next(c for c in audit['checks'] if c['name']=='delivery_layout')['findings'][0]
        self.assertEqual(finding['path'], 'deps.lock')
        self.assertEqual(finding['actual']['other_paths'], ['resources/deps.lock'])
        self.assertEqual(manifest(Path(result['output'])), before)
        self.assertTrue(qualify(record['delivery'])[0])

    def test_contract_obligation_tampering_is_rejected_even_with_a_valid_hash(self):
        _, record = self.run_layout('deps.lock')
        delivery = copy.deepcopy(record['delivery'])
        changed = delivery['inputs']['layout']['payload']
        changed['exact_files'] = None
        changed['required_files'] = ['SKILL.md']
        delivery['inputs']['layout'] = versioned(changed)
        delivery['fingerprints']['layout'] = fingerprint(delivery['inputs']['layout'])
        delivery['revision_id'] = 'rev-' + fingerprint(delivery['inputs'])
        self.assertIn('original requirement snapshots', qualify(delivery)[1])

    def test_cli_config_cannot_waive_a_frozen_layout_obligation(self):
        result, _ = self.run_layout('resources/deps.lock')
        self.case.options['prompt'] = 'Retain the reading checklist.'
        write_json(self.case.config, self.case.options)
        code, audit = self.cli('check', result['output'], '--config', str(self.case.config))
        self.assertEqual(code, 1, audit)
        states = {c['name']: c['status'] for c in audit['checks']}
        self.assertEqual(states['frozen_delivery_layout'], 'fail')
        self.assertEqual(states['delivery_layout'], 'pass')

    def test_corrupted_layout_envelopes_fail_closed_without_execution(self):
        _, record = self.run_layout('deps.lock')
        for value in (None, {}, {'version': True}, {'version': 1, 'payload': {}, 'sha256': 'wrong'}):
            with self.subTest(value=value):
                delivery = copy.deepcopy(record['delivery'])
                delivery['inputs']['layout'] = value
                delivery['fingerprints']['layout'] = fingerprint(value)
                delivery['revision_id'] = 'rev-' + fingerprint(delivery['inputs'])
                self.assertEqual(qualify(delivery), (False, 'Invalid layout contract'))


class LayoutRuntimeBoundaryTests(unittest.TestCase):
    def test_invalid_layout_stops_before_planning_and_revokes_content(self):
        from tests.pipeline.test_runtime_build import RuntimeBuildTests
        from creation_pipeline.runtime.preparation import prepare
        from creation_pipeline.runtime.local import LocalExecutor
        case = RuntimeBuildTests()
        case.setUp()
        try:
            delivery = case.record['delivery']
            delivery['inputs']['layout'] = versioned(extract({'prompt': 'Required files: main.py, deps.lock;'}))
            delivery['revision_id'] = 'rev-' + fingerprint(delivery['inputs'])
            delivery['fingerprints']['layout'] = fingerprint(delivery['inputs']['layout'])
            with patch('creation_pipeline.runtime.model_call.call', side_effect=AssertionError('Live model')), \
                 patch('creation_pipeline.runtime.local.process', side_effect=AssertionError('Live Docker')):
                prepare(case.record, case.package, case.sources, case.root/'invalid-layout', {}, LocalExecutor())
            result = case.record['runtime_preparation']
            self.assertEqual(result['model_calls'], 0)
            self.assertEqual(result['gaps'][0]['code'], 'delivery_layout_mismatch')
            self.assertEqual(result['gaps'][0]['repair_lane'], 'content')
            self.assertIn('deps.lock', result['gaps'][0]['detail'])
            self.assertEqual(delivery['content']['status'], 'failed')
            self.assertFalse(qualify(delivery)[0])
        finally:
            case.tearDown()
