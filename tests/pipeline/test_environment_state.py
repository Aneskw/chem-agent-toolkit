"""Environment control state stays private across migration and normal operations."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from creation_pipeline.artifacts.package import manifest
from creation_pipeline.records import file_digest, lease, read_json, write_json
from creation_pipeline.shared.environment import EnvironmentLibrary, inventory
from creation_pipeline.shared.environment_state import locations, locked, migrate
from creation_pipeline.shared.investigation import Investigations
from tests.pipeline.test_shared_creation import env_plan


class EnvironmentStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        private = patch('creation_pipeline.shared.environment_state.STATE_ROOT', self.root / '.pipeline/tool-libraries')
        private.start()
        self.addCleanup(private.stop)
        self.library = self.root / 'tools'
        self.library.mkdir()

    def client(self):
        return EnvironmentLibrary({'environments': {'root': str(self.library),
            'operation_timeout': None, 'publish': False}}, self.root / 'run')

    def test_migration_preserves_cache_bytes_and_public_catalog(self):
        write_json(self.library / 'catalog.json', [])
        write_json(self.library / 'versions.json', {'rdkit': 4})
        write_json(self.library / 'prepared-plans.json', [{'key': 'source-bound', 'plan': {'evidence': ['e1']}}])
        original = {p.name: file_digest(p) for p in self.library.glob('*.json')}
        with lease(self.library, 'catalog'):
            pass
        self.assertEqual(inventory(self.library), [])
        private = locations(self.library)[1]
        for name in ('versions.json', 'prepared-plans.json'):
            self.assertEqual(file_digest(private / name), original[name])
            self.assertFalse((self.library / name).exists())
        self.assertEqual(file_digest(self.library / 'catalog.json'), original['catalog.json'])
        self.assertFalse((self.library / 'leases').exists())
        self.assertEqual(migrate(self.library), private)

    def test_version_allocation_uses_migrated_counter(self):
        write_json(self.library / 'versions.json', {'rdkit': 4})
        client = self.client()
        self.assertEqual(client.reserve('rdkit'), 'v5')
        self.assertEqual(client.reserve('rdkit'), 'v6')
        self.assertEqual(read_json(client.library_state / 'versions.json'), {'rdkit': 6})
        self.assertEqual(list(self.library.iterdir()), [])

    def test_investigation_remains_shared_and_private(self):
        cache = Investigations(self.library)
        plan = env_plan()
        sources = SimpleNamespace(evidence=[{'id': 'e1', 'kind': 'source_locator', 'sha256': 'a', 'path': 'source'}])
        cache.remember(plan, sources)
        second = Investigations(self.library)
        self.assertEqual(second.entries()[0]['plan'], plan)
        second.invalidate(plan, 'New source requires another investigation')
        self.assertEqual(cache.entries()[0]['state'], 'needs_revision')
        self.assertTrue(cache.path.is_relative_to(locations(self.library)[1]))
        self.assertEqual(list(self.library.iterdir()), [])

    def test_active_legacy_lock_prevents_migration(self):
        write_json(self.library / 'versions.json', {'rdkit': 4})
        with lease(self.library, 'catalog'):
            with self.assertRaises(OSError):
                migrate(self.library)
        self.assertTrue((self.library / 'versions.json').exists())
        self.assertFalse((locations(self.library)[1] / 'versions.json').exists())

    def test_conflicting_private_cache_is_not_overwritten(self):
        write_json(self.library / 'versions.json', {'rdkit': 4})
        private = locations(self.library)[1]
        write_json(private / 'versions.json', {'rdkit': 5})
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            migrate(self.library)
        self.assertEqual(read_json(self.library / 'versions.json'), {'rdkit': 4})
        self.assertEqual(read_json(private / 'versions.json'), {'rdkit': 5})

    def test_active_private_lock_prevents_legacy_migration(self):
        write_json(self.library / 'versions.json', {'rdkit': 4})
        private = locations(self.library)[1]
        with lease(private, 'versions'):
            with self.assertRaises(OSError):
                migrate(self.library)
        self.assertTrue((self.library / 'versions.json').exists())
        self.assertFalse((private / 'versions.json').exists())

    def test_interrupted_copy_is_reconciled_without_losing_counters(self):
        write_json(self.library / 'versions.json', {'rdkit': 4})
        private = locations(self.library)[1]
        write_json(private / 'versions.json', {'rdkit': 4})
        migrate(self.library)
        self.assertFalse((self.library / 'versions.json').exists())
        self.assertEqual(read_json(private / 'versions.json'), {'rdkit': 4})

    def test_lock_is_shared_between_clients_outside_tool_materials(self):
        with locked(self.library, 'catalog'):
            with self.assertRaises(OSError):
                with locked(self.library, 'catalog'):
                    self.fail('Concurrent writer acquired the same catalog lock')
        with locked(self.library, 'catalog'):
            pass
        self.assertFalse((self.library / 'leases').exists())

    def test_distinct_library_paths_have_distinct_private_state(self):
        other = self.root / 'another-project/tools'
        self.assertNotEqual(locations(self.library)[1], locations(other)[1])

    def test_invalid_control_directory_is_retained(self):
        (self.library / 'versions.json').mkdir()
        with self.assertRaisesRegex(ValueError, 'must be files'):
            migrate(self.library)
        self.assertTrue((self.library / 'versions.json').is_dir())

    def test_host_pull_receipt_is_not_written_into_public_metadata(self):
        context = self.library / 'rdkit/v1/context'
        context.mkdir(parents=True)
        (context / 'Dockerfile').write_text('FROM python:3.11\n', encoding='utf-8')
        receipt = {'command': ['docker', '--config', 'C:/private/run/auth', 'pull', 'example:1'], 'exit_code': 0}
        record = {**env_plan(), 'id': 'rdkit', 'version': 'v1', 'path': 'rdkit/v1', 'files': manifest(context),
                  'fingerprint': 'source-identity', 'image': 'ghcr.io/example/tools:rdkit-v1',
                  'digest': 'sha256:abc', 'anonymous_pull': receipt}
        client = self.client()
        self.assertEqual(client.persist(record)['anonymous_pull'], receipt)
        public = inventory(self.library)[0]
        self.assertNotIn('anonymous_pull', public)
        metadata = read_json(self.library / 'rdkit/v1/environment.json')
        self.assertEqual(metadata['image'], public['image'])
        self.assertNotIn('anonymous_pull', metadata)
        self.assertNotIn('fingerprint', metadata)
        observation = read_json(client.library_state / 'observations/rdkit/v1/anonymous-pull.json')
        self.assertEqual(observation['observation'], receipt)
        self.assertEqual(observation['digest'], record['digest'])
        self.assertNotIn('C:/private', (self.library / 'catalog.json').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
