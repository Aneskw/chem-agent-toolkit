"""Delivery packages remain independent of local catalog and transaction state."""
import copy
import errno
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.artifacts.package import manifest
from creation_pipeline.cli import main
from creation_pipeline.records import lease, read_json, write_json
from creation_pipeline.shared.delivery import adopt, entries, promote
from creation_pipeline.shared.environment import fingerprint
from creation_pipeline.shared.library import catalog_path, is_library, locations, migrate


IMAGE = 'ghcr.io/example/chem-tools:example-v1'
DIGEST = 'sha256:' + 'a' * 64


class SharedLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        state = patch('creation_pipeline.shared.library.STATE_ROOT', self.root / '.pipeline/skill-libraries')
        state.start()
        self.addCleanup(state.stop)
        self.library = self.root / 'skills' / 'paper-a'
        self.package = self.root / 'package'
        for name, content in {
            'SKILL.md': '---\nname: example\ndescription: Process an input with the documented tool.\n---\nUse runtime.json.\n',
            'runtime.json': json.dumps({'image': IMAGE, 'platform': 'linux/amd64'}),
            'scripts/process.py': 'print("result")\n',
            'references/guide.md': 'Input and output descriptions.\n',
            'resources/example.json': '{"value": 1}\n',
        }.items():
            path = self.package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        self.files = manifest(self.package)
        self.record = {
            'name': 'example', 'group': 'paper-a', 'status': 'verified', 'final_files': self.files,
            'record': str(self.root / 'records/record.json'),
            'environment': {'image': IMAGE, 'digest': DIGEST,
                'anonymous_access': {'status': 'verified', 'image': IMAGE, 'digest': DIGEST}},
        }

    def seed_legacy(self):
        entry = adopt(self.package, self.record, self.library)
        private = catalog_path(self.library)
        original = read_json(private)
        original.pop('library_root')
        write_json(self.library / 'catalog.json', original)
        private.unlink()
        with lease(self.library, 'shared-catalog'):
            pass
        partial = self.library / '.staging/interrupted/partial.txt'
        partial.parent.mkdir(parents=True)
        partial.write_text('Recoverable incomplete copy', encoding='utf-8')
        return entry, original

    def test_export_preserves_required_files_and_keeps_all_work_state_outside_library(self):
        entry = adopt(self.package, self.record, self.library)
        self.assertEqual(manifest(self.library / entry['path']), self.files)
        self.assertEqual({p.name for p in self.library.iterdir()}, {'verified'})
        library, state = locations(self.library)
        self.assertFalse(state.is_relative_to(library))
        self.assertTrue((state / 'catalog.json').is_file())
        self.assertTrue((state / 'leases/shared-catalog.lock').is_file())
        self.assertTrue((state / 'staging').is_dir())
        self.assertEqual(read_json(state / 'catalog.json')['library_root'], str(self.library.resolve()))
        self.assertEqual(adopt(self.package, self.record, self.library), entry)

    def test_cli_query_and_install_find_the_external_index(self):
        adopt(self.package, self.record, self.library)
        self.assertTrue(is_library(self.library))
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(['library', str(self.library)])
        self.assertEqual(code, 0, output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['skills'][0]['name'], 'example')
        installed = self.root / 'installed'
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(['install', str(self.library), '--name', 'example', '--destination', str(installed)]), 0)
        self.assertEqual(manifest(installed / 'example'), self.files)
        self.assertEqual({p.name for p in self.library.iterdir()}, {'verified'})

    def test_distinct_group_libraries_have_distinct_private_catalogs(self):
        adopt(self.package, self.record, self.library)
        other = self.root / 'skills/paper-b'
        adopt(self.package, self.record, other)
        self.assertNotEqual(catalog_path(self.library), catalog_path(other))
        self.assertEqual(catalog_path(self.library), catalog_path(self.library / '..' / 'paper-a'))
        self.assertEqual(len(entries(self.library)), 1)
        self.assertEqual(len(entries(other)), 1)

    def test_migration_preserves_package_identity_and_interrupted_staging(self):
        entry, original = self.seed_legacy()
        self.assertTrue(is_library(self.library))
        result = migrate(self.library)
        state = locations(self.library)[1]
        self.assertEqual(result['skills'], 1)
        self.assertEqual(entries(self.library)[0], entry)
        self.assertEqual(manifest(self.library / entry['path']), self.files)
        self.assertEqual({p.name for p in self.library.iterdir()}, {'verified'})
        self.assertEqual(read_json(state / 'migration.json')['catalog'], original)
        self.assertEqual((state / 'staging/recovered/interrupted/partial.txt').read_text(), 'Recoverable incomplete copy')
        self.assertEqual(migrate(self.library), result)

    def test_migration_refuses_modified_delivery_without_removing_old_catalog(self):
        entry, _ = self.seed_legacy()
        changed = self.library / entry['path'] / 'SKILL.md'
        changed.write_text('Changed externally', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'migration refused'):
            migrate(self.library)
        self.assertTrue((self.library / 'catalog.json').is_file())
        self.assertTrue((self.library / '.staging/interrupted/partial.txt').is_file())
        self.assertFalse(locations(self.library)[1].joinpath('catalog.json').exists())

    def test_active_legacy_lock_prevents_migration(self):
        self.seed_legacy()
        with lease(self.library, 'shared-catalog'):
            with self.assertRaises(OSError):
                migrate(self.library)
        self.assertTrue((self.library / 'catalog.json').exists())
        self.assertEqual(migrate(self.library)['skills'], 1)

    def test_promotion_keeps_reports_and_staging_outside_delivered_packages(self):
        record = copy.deepcopy(self.record)
        record.update(status='pending-validation', verification={'deferred': [{'item_id': 'sample'}]})
        entry = adopt(self.package, record, self.library)
        report = {'image': IMAGE, 'package_sha256': fingerprint(entry['files']),
                  'items': [{'item_id': 'sample', 'status': 'passed', 'evidence': 'Manual execution receipt'}]}
        result = promote(self.library, 'example', report)
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(manifest(self.library / result['path']), self.files)
        self.assertTrue((locations(self.library)[1] / 'promotion.json').is_file())
        self.assertEqual({p.name for p in self.library.iterdir()}, {'verified', 'pending-validation'})

    def test_process_sidecars_cannot_be_exported_as_an_approved_package(self):
        (self.package / 'build.log').write_text('Internal build output', encoding='utf-8')
        record = {**self.record, 'final_files': manifest(self.package)}
        with self.assertRaisesRegex(ValueError, 'Unsupported file role'):
            adopt(self.package, record, self.library)
        self.assertFalse(self.library.exists())

    def test_copy_failure_leaves_no_partial_delivery_and_retry_is_safe(self):
        def partial_copy(source, target):
            target = Path(target)
            target.mkdir()
            (target / 'SKILL.md').write_text('Incomplete', encoding='utf-8')
            raise OSError('Interrupted copy')
        with patch('creation_pipeline.shared.delivery.shutil.copytree', side_effect=partial_copy):
            with self.assertRaisesRegex(OSError, 'Interrupted copy'):
                adopt(self.package, self.record, self.library)
        self.assertFalse(self.library.exists())
        self.assertFalse(locations(self.library)[1].joinpath('catalog.json').exists())
        entry = adopt(self.package, self.record, self.library)
        self.assertEqual(manifest(self.library / entry['path']), self.files)

    def test_cross_device_commit_does_not_publish_a_partial_package(self):
        with patch.object(Path, 'rename', side_effect=OSError(errno.EXDEV, 'Cross-device rename')):
            with self.assertRaises(OSError):
                adopt(self.package, self.record, self.library)
        self.assertFalse((self.library / 'verified/example').exists())
        self.assertFalse(locations(self.library)[1].joinpath('catalog.json').exists())


if __name__ == '__main__':
    unittest.main()
