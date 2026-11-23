"""Portable descriptions stay small without losing reuse or verification gates."""
import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.artifacts.package import manifest
from creation_pipeline.records import read_json, write_json
from creation_pipeline.shared.delivery import qualify
from creation_pipeline.shared.environment import EnvironmentLibrary, inventory
from creation_pipeline.shared.environment_metadata import describe, state_path
from tests.pipeline.test_shared_creation import env_plan, IMAGE, DIGEST


class EnvironmentMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        private = patch('creation_pipeline.shared.environment_state.STATE_ROOT', self.root / '.pipeline/tool-libraries')
        private.start()
        self.addCleanup(private.stop)
        self.tools = self.root / 'tools'
        self.context = self.tools / 'example/v1/context'
        self.context.mkdir(parents=True)
        (self.context / 'Dockerfile').write_text('FROM python:3.11\n', encoding='utf-8')
        plan = env_plan()
        plan['tools'] = [{'name': name, 'version': version, 'kind': 'python',
                          'probe': ['python', '/opt/probe.py', name, version]}
                         for name, version in [('numpy', '1.26.4'), ('pandas', '2.1.4')]]
        self.record = {**plan, 'id': 'example', 'version': 'v1', 'path': 'example/v1',
            'files': manifest(self.context), 'fingerprint': 'original-build-identity',
            'tag': 'chem-env:original-build-identity', 'content_id': 'sha256:local-config',
            'state': 'published', 'checks': 'passed', 'image': IMAGE, 'digest': DIGEST,
            'reuse': False, 'anonymous_access': {'status': 'verified', 'image': IMAGE, 'digest': DIGEST}}

    def client(self, tools=None):
        return EnvironmentLibrary({'environments': {'root': str(tools or self.tools),
            'operation_timeout': None, 'publish': False}}, self.root / 'run')

    def test_portable_description_omits_process_state_and_unused_defaults(self):
        value = describe(self.record)
        self.assertEqual(set(value), {'id', 'version', 'platform', 'base_image', 'files',
                                     'image', 'digest', 'probe', 'tools'})
        self.assertEqual(value['probe'], ['python', '/opt/probe.py'])
        self.assertTrue(all('probe' not in t for t in value['tools']))

    def test_custom_probe_and_active_requirements_survive_round_trip(self):
        custom = {'name': 'author-source', 'version': 'abcdef', 'kind': 'source',
                  'probe': ['python', '/opt/source_probe.py', 'abcdef']}
        self.record['tools'].append(custom)
        self.record['conditions']['minimum_memory_gib'] = 4
        self.record['resources'] = [{'name': 'config', 'included_in_image': True, 'url': 'https://example.com/config',
            'version': 'abcdef', 'usage': 'Training configuration'}]
        self.client().persist(self.record)
        value = read_json(self.tools / 'example/v1/environment.json')
        self.assertEqual(value['conditions'], {'minimum_memory_gib': 4})
        self.assertEqual(value['tools'][-1], custom)
        restored = inventory(self.tools)[0]
        for key in ('tools', 'conditions', 'resources', 'files', 'fingerprint', 'content_id', 'anonymous_access'):
            self.assertEqual(restored[key], self.record[key])

    def test_single_tool_keeps_explicit_probe(self):
        self.record['tools'] = self.record['tools'][:1]
        value = describe(self.record)
        self.assertNotIn('probe', value)
        self.assertEqual(value['tools'][0]['probe'], self.record['tools'][0]['probe'])

    def test_catalog_only_locates_environment_descriptions(self):
        client = self.client()
        client.persist(self.record)
        self.assertEqual(read_json(self.tools / 'catalog.json'), [{'id': 'example', 'version': 'v1', 'path': 'example/v1'}])
        stored = read_json(state_path(client.library_state, self.record))
        self.assertNotIn('tools', stored)
        self.assertNotIn('files', stored)
        self.assertNotIn('reuse', stored)
        qualify(client.records()[0])

    def test_cloned_materials_do_not_inherit_private_approval(self):
        self.client().persist(self.record)
        cloned = self.root / 'clone/tools'
        shutil.copytree(self.tools, cloned)
        restored = self.client(cloned).records()[0]
        self.assertEqual(restored['tools'], self.record['tools'])
        self.assertEqual(restored['tag'], IMAGE.split(':', 1)[0] + '@' + DIGEST)
        self.assertEqual(restored['anonymous_access']['status'], 'unverified')
        self.assertNotIn('content_id', restored)
        with self.assertRaises(ValueError):
            qualify(restored)

    def test_changed_metadata_cannot_inherit_anonymous_access_proof(self):
        client = self.client()
        client.persist(self.record)
        path = self.tools / 'example/v1/environment.json'
        metadata = read_json(path)
        metadata['digest'] = 'sha256:' + 'b' * 64
        write_json(path, metadata)
        restored = client.records()[0]
        self.assertEqual(restored['anonymous_access']['status'], 'unverified')
        self.assertNotIn('content_id', restored)

    def test_missing_private_state_requires_fresh_checks(self):
        client = self.client()
        client.persist(self.record)
        state_path(client.library_state, self.record).unlink()
        restored = client.records()[0]
        self.assertEqual(restored['checks'], 'unverified')
        self.assertEqual(restored['tools'], self.record['tools'])

    def test_cloned_environment_is_probed_and_reverified_without_rebuilding(self):
        image = 'ghcr.io/example/project:example-v1'
        self.record['image'] = image
        self.record['anonymous_access']['image'] = image
        self.client().persist(self.record)
        cloned = self.root / 'clone/tools'
        shutil.copytree(self.tools, cloned)
        client = self.client(cloned)
        client.settings['repository'] = 'ghcr.io/example/project'
        class Remote:
            def resolve(self, target, authenticated=False):
                return DIGEST if target == image else None
            def public(self, target, digest, platform):
                return {'status': 'verified', 'image': target, 'digest': digest}
        calls = []
        def run(command, timeout):
            import json
            calls.append(command)
            output = json.dumps({'version': command[-1]}) if command[:3] == ['docker', 'run', '--rm'] else ''
            return {'exit_code': 0, 'stdout': output, 'stderr': ''}
        client.registry, client.run = Remote(), run
        plan = {**self.record, 'environment_id': 'example', 'selection': 'reuse'}
        plan['skill_tools'] = [t['name'] for t in plan['tools']]
        plan['skill_resources'] = []
        reused = client.ensure(plan, self.root / 'reuse')
        qualified = client.publish(reused)
        qualify(qualified)
        self.assertEqual(qualified['checks'], 'passed')
        self.assertFalse(any(c[:2] in (['docker', 'build'], ['docker', 'push']) for c in calls))
        self.assertEqual(sum(c[:3] == ['docker', 'run', '--rm'] for c in calls), 2)

    def test_new_pipeline_can_use_a_cloned_tool_library_without_local_state(self):
        from creation_pipeline.shared.pipeline import build
        from tests.pipeline.test_shared_creation import Session
        self.record.update(id='env-python', tools=env_plan()['tools'])
        self.client().persist(self.record)
        cloned = self.root / 'clone/tools'
        shutil.copytree(self.tools, cloned)
        (self.root / 'source.txt').write_text('Documented print(2)', encoding='utf-8')
        config = self.root / 'input.json'
        write_json(config, {'sources': [{'id': 'code', 'path': 'source.txt'}],
            'environments': {'root': str(cloned), 'repository': 'ghcr.io/example/project'}})
        seen, commands = [], []
        test = self
        class FreshSession(Session):
            mode = 'exempt'
            calls = []
            def stage(self, instructions, context, schema=None):
                if context['_phase'] == 'environment':
                    seen.append(context['catalog'])
                    test.assertNotIn('content_id', context['catalog'][0])
                return super().stage(instructions, context, schema)
        class Remote:
            def resolve(self, target, authenticated=False):
                return DIGEST if target == IMAGE else None
            def public(self, target, digest, platform):
                return {'status': 'verified', 'image': target, 'digest': digest}
        def run(command, timeout):
            commands.append(command)
            return {'exit_code': 0, 'stdout': '{"version":"3.11"}' if command[:3] == ['docker', 'run', '--rm'] else '', 'stderr': ''}
        def library(config, state):
            return EnvironmentLibrary(config, state, run=run, registry=Remote())
        with patch('creation_pipeline.shared.pipeline.EnvironmentLibrary', library), patch(
                'creation_pipeline.shared.library.STATE_ROOT', self.root / '.pipeline/skill-libraries'):
            result = build(config, self.root / 'new-run', library_root=self.root / 'skills', _session_factory=FreshSession)
        self.assertEqual(result['status'], 'ready', result)
        self.assertEqual(result['counts'], {'verified': 1})
        self.assertTrue(seen)
        self.assertFalse(any(c[:2] in (['docker', 'build'], ['docker', 'push']) for c in commands))

    def test_changed_context_remains_an_integrity_error(self):
        self.client().persist(self.record)
        (self.context / 'Dockerfile').write_text('FROM different:1\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'materials changed'):
            inventory(self.tools)

    def test_changed_tool_contract_cannot_overwrite_a_version(self):
        client = self.client()
        client.persist(self.record)
        changed = copy.deepcopy(self.record)
        changed['tools'][0]['version'] = '2.0.0'
        with self.assertRaisesRegex(ValueError, 'Immutable'):
            client.persist(changed)

    def test_compaction_of_legacy_index_preserves_build_identity_and_proof(self):
        legacy = {**self.record, 'checked_at': '2026-11-13T00:00:00Z'}
        write_json(self.tools / 'catalog.json', [legacy])
        write_json(self.tools / 'example/v1/environment.json', legacy)
        client = self.client()
        client.compact()
        restored = client.records()[0]
        for key in ('tools', 'files', 'fingerprint', 'tag', 'content_id', 'anonymous_access', 'checked_at'):
            self.assertEqual(restored[key], legacy[key])
        self.assertEqual(client.compact()[0], client.records()[0])
        self.assertNotIn('anonymous_access', read_json(self.tools / 'example/v1/environment.json'))

    def test_conflicting_metadata_identity_and_duplicate_index_are_rejected(self):
        self.client().persist(self.record)
        path = self.tools / 'catalog.json'
        index = read_json(path)
        write_json(path, index + index)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            inventory(self.tools)
        write_json(path, [{**index[0], 'version': 'v2'}])
        with self.assertRaisesRegex(ValueError, 'differs from its index'):
            inventory(self.tools)

    def test_interrupted_compaction_keeps_the_old_index_readable(self):
        write_json(self.tools / 'catalog.json', [self.record])
        write_json(self.tools / 'example/v1/environment.json', self.record)
        client = self.client()
        def interrupted(path, value):
            if Path(path) == self.tools / 'catalog.json':
                raise OSError('Interrupted before index commit')
            write_json(path, value)
        with patch('creation_pipeline.shared.environment.write_json', interrupted):
            with self.assertRaisesRegex(OSError, 'Interrupted'):
                client.compact()
        qualify(client.records()[0])
        client.compact()
        qualify(client.records()[0])


if __name__ == '__main__':
    unittest.main()
