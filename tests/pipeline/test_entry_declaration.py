"""Delivered-entry resolution: caller binding, then author declaration, then conservatism.

The declaration only selects an entry. It never earns trust by existing: the package,
the source association, the independent review and the frozen execution contract all
still decide whether the delivery is acceptable.
"""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.artifacts.delivery import finish
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import finalize
from creation_pipeline.runtime import entry, planner, preparation

SKILL = '---\nname: demo\ndescription: demo\n---\n\nText.\n'
SKILL_BLOCK_ONE = ('---\nname: demo\ndescription: demo\n---\n\n```python\n'
                   'print("first")\n```\n')
BLOCK_ONE = 'print("first")\n'
BLOCK_TWO = 'print("second")\n'
WRAPPER = 'import runpy\nrunpy.run_path("main.py")\n'
SOURCE_TEXT = 'def main():\n    return 1\n'


def write(path, text):
    """Write exact LF bytes so extraction hashes are platform independent."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


class DeclarationSelectionTests(unittest.TestCase):
    def setUp(self):
        self.roots = []

    def tearDown(self):
        for root in self.roots:
            shutil.rmtree(root, ignore_errors=True)

    def package(self, files):
        root = Path(tempfile.mkdtemp(prefix='entry-declaration-'))
        self.roots.append(root)
        for name, text in files.items():
            write(root / name, text)
        return root

    def test_declaration_selects_the_script_beside_a_documentation_block(self):
        package = self.package({'SKILL.md': SKILL_BLOCK_ONE, 'scripts/run.py': 'print(1)\n'})
        binding = entry.preflight(package, {'kind': 'script', 'path': 'scripts/run.py'})
        self.assertEqual(binding['kind'], 'script')
        self.assertEqual(binding['entry'], 'scripts/run.py')
        self.assertEqual(binding['runtime_entry'], 'package/scripts/run.py')
        self.assertEqual(binding['declaration'],
                         {'kind': 'script', 'path': 'scripts/run.py'})

    def test_declaration_resolves_ambiguity_that_conservative_rules_refuse(self):
        package = self.package({'SKILL.md': SKILL_BLOCK_ONE, 'scripts/run.py': 'print(2)\n'})
        with self.assertRaises(entry.EntryError) as caught:
            entry.preflight(package)
        self.assertEqual(caught.exception.code, 'entry_ambiguous')
        binding = entry.preflight(package, {'kind': 'script', 'path': 'scripts/run.py'})
        self.assertEqual(binding['entry'], 'scripts/run.py')

    def test_declaration_picks_one_markdown_block_by_index(self):
        skill = ('---\nname: d\ndescription: d\n---\n\n'
                 'Example only:\n\n```python\n' + BLOCK_ONE + '```\n\n'
                 'Runnable entry:\n\n```python\n' + BLOCK_TWO + '```\n')
        package = self.package({'SKILL.md': skill})
        with self.assertRaises(entry.EntryError):
            entry.preflight(package)  # two fences, no declaration
        binding = entry.preflight(package, {'kind': 'markdown_python', 'path': 'SKILL.md',
                                            'block_index': 1})
        self.assertEqual(binding['kind'], 'markdown_python')
        self.assertEqual(binding['extraction']['block_index'], 1)
        self.assertEqual(binding['extraction']['code_sha256'],
                         hashlib.sha256(BLOCK_TWO.encode()).hexdigest())

    def test_declared_code_identifier_must_match_the_extracted_block(self):
        package = self.package({'SKILL.md':
                                '---\nname: d\ndescription: d\n---\n\n```python\n'
                                + BLOCK_TWO + '```\n'})
        digest = hashlib.sha256(BLOCK_TWO.encode()).hexdigest()
        binding = entry.preflight(package, {'kind': 'markdown_python', 'path': 'SKILL.md',
                                            'code_sha256': digest})
        self.assertEqual(binding['extraction']['block_index'], 0)
        with self.assertRaises(entry.EntryError) as caught:
            entry.preflight(package, {'kind': 'markdown_python', 'path': 'SKILL.md',
                                      'code_sha256': '0' * 64})
        self.assertEqual(caught.exception.code, 'entry_declaration_mismatch')

    def test_missing_or_unsafe_or_unsupported_declarations_are_refused(self):
        package = self.package({'SKILL.md': SKILL, 'scripts/run.py': 'print(1)\n'})
        cases = [
            ({'kind': 'script', 'path': 'absent.py'}, 'entry_declaration_missing'),
            ({'kind': 'script', 'path': '../run.py'}, 'entry_declaration_invalid'),
            ({'kind': 'script', 'path': 'C:/run.py'}, 'entry_declaration_invalid'),
            ({'kind': 'script', 'path': 'SKILL.md'}, 'entry_declaration_invalid'),
            ({'kind': 'markdown_python', 'path': 'scripts/run.py'}, 'entry_unsupported'),
            ({'kind': 'markdown_python', 'path': 'SKILL.md', 'block_index': 3},
             'entry_unsupported'),
            ({'kind': 'binary', 'path': 'scripts/run.py'}, 'entry_declaration_invalid'),
            ({'kind': 'script', 'path': 'scripts/run.py', 'block_index': 0},
             'entry_declaration_invalid'),
            ({'kind': 'script', 'path': 'scripts/run.py', 'extra': 1},
             'entry_declaration_invalid'),
            ('scripts/run.py', 'entry_declaration_invalid'),
        ]
        for declared, code in cases:
            with self.assertRaises(entry.EntryError, msg=repr(declared)) as caught:
                entry.preflight(package, declared)
            self.assertEqual(caught.exception.code, code, repr(declared))

    def test_a_declaration_is_validated_not_trusted(self):
        # Declaring a Markdown block does not skip the static checks.
        package = self.package({'SKILL.md':
                                '---\nname: d\ndescription: d\n---\n\n```python\n'
                                'print(undefined_name)\n```\n'})
        with self.assertRaises(entry.EntryError) as caught:
            entry.preflight(package, {'kind': 'markdown_python', 'path': 'SKILL.md',
                                      'block_index': 0})
        self.assertEqual(caught.exception.code, 'entry_context_missing')

    def test_declared_markdown_entry_materializes_the_selected_block(self):
        skill = ('---\nname: d\ndescription: d\n---\n\n```python\n' + BLOCK_ONE + '```\n\n'
                 '```python\n' + BLOCK_TWO + '```\n')
        package = self.package({'SKILL.md': skill})
        binding = entry.preflight(package, {'kind': 'markdown_python', 'path': 'SKILL.md',
                                            'block_index': 1})
        target = self.package({'SKILL.md': SKILL})  # separate, empty target tree
        entry.materialize(package, binding, target)
        self.assertEqual((target / 'entry/skill.py').read_text(encoding='utf-8'), BLOCK_TWO)
        entry.verify_material(package, binding, target)

    def test_a_changed_document_no_longer_matches_the_frozen_locator(self):
        skill = ('---\nname: d\ndescription: d\n---\n\n```python\n' + BLOCK_ONE + '```\n\n'
                 '```python\n' + BLOCK_TWO + '```\n')
        package = self.package({'SKILL.md': skill})
        binding = entry.preflight(package, {'kind': 'markdown_python', 'path': 'SKILL.md',
                                            'block_index': 1})
        target = self.package({'SKILL.md': SKILL})
        entry.materialize(package, binding, target)
        write(package / 'SKILL.md',
              '---\nname: d\ndescription: d\n---\n\n```python\n' + BLOCK_TWO + '```\n\n'
              '```python\n' + BLOCK_ONE + '```\n')
        with self.assertRaises(ValueError):
            entry.verify_material(package, binding, target)


class ByteIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.package = self.root / 'package'
        self.source = self.root / 'source'
        for base in (self.package, self.source):
            write(base / 'main.py', SOURCE_TEXT)
        write(self.package / 'SKILL.md', SKILL)
        write(self.package / 'scripts/wrapper.py', WRAPPER)
        self.sources = [{'id': 'tool', 'path': str(self.source),
                         'inventory': manifest(self.source)}]

    def tearDown(self):
        self.temp.cleanup()

    def test_declaring_the_adapted_entry_does_not_use_the_identical_file(self):
        with self.assertRaises(preparation.RuntimeBlocked):
            preparation.bind(self.package, self.sources, entry='scripts/wrapper.py')
        binding = preparation.bind(self.package, self.sources, entry='main.py')
        self.assertEqual(binding['entry'], 'main.py')
        self.assertEqual(binding['association'], 'identical')

    def test_byte_identity_without_a_declared_entry_is_unchanged(self):
        binding = preparation.bind(self.package, self.sources)
        self.assertEqual(binding['entry'], 'main.py')


class DeliveryReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.package = self.root / 'package'
        write(self.package / 'SKILL.md', SKILL)
        write(self.package / 'scripts/run.py', 'print(1)\n')
        write(self.root / 'resource-state.json',
              json.dumps({'config': {'limits': {'package_bytes': None}}}))
        write(self.root / 'active-phase.json', json.dumps({'phase': 'author'}))

    def tearDown(self):
        self.temp.cleanup()

    def metadata(self, entry_declaration=None):
        data = {'tests': [], 'issues': [], 'notes': []}
        if entry_declaration is not None:
            data['entry'] = entry_declaration
        path = self.root / 'meta.json'
        write(path, json.dumps(data))
        return path

    def test_declaration_is_persisted_in_the_delivery_receipt(self):
        declared = {'kind': 'script', 'path': 'scripts/run.py'}
        finish(self.root, self.package, 'token-1', self.metadata(declared))
        receipt = json.loads((self.root / 'deliveries/package.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['entry'], declared)

    def test_malformed_declarations_are_refused_at_the_receipt(self):
        for bad in ({'kind': 'shell', 'path': 'scripts/run.py'},
                    {'kind': 'script'},
                    {'kind': 'script', 'path': ''},
                    {'kind': 'script', 'path': 'scripts/run.py', 'block_index': -1},
                    {'kind': 'script', 'path': 'scripts/run.py', 'block_index': True},
                    {'kind': 'markdown_python', 'path': 'SKILL.md',
                     'code_sha256': 'not-a-digest'},
                    {'kind': 'script', 'path': 'scripts/run.py', 'unexpected': 1}):
            with self.assertRaises(ValueError, msg=repr(bad)):
                finish(self.root, self.package, 'token-1', self.metadata(bad))

    def test_absent_declaration_keeps_the_old_receipt_shape(self):
        finish(self.root, self.package, 'token-2', self.metadata())
        receipt = json.loads((self.root / 'deliveries/package.json').read_text(encoding='utf-8'))
        self.assertNotIn('entry', receipt)


class PriorityTests(unittest.TestCase):
    """The three entry-selection sources, in order, through ``prepare``."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def build(self, delivered, name='run'):
        package = self.root / name / 'package'
        source = self.root / name / 'source'
        write(source / 'main.py', SOURCE_TEXT)
        for relative, text in delivered.items():
            write(package / relative, text)
        sources = [{'id': 'tool', 'path': str(source), 'inventory': manifest(source),
                    'resolved_ref': 'fixture'}]
        record = {'name': 'probe', 'status': 'ready', 'files': manifest(package),
                  'plan': {'name': 'probe'},
                  'checks': [{'name': 'content_review', 'status': 'pass',
                              'requirement_assessment': 'confirmed'}]}
        finalize(record, sources, {'status': 'required', 'reason': 'Executable',
                                    'citations': [{'source_id': 'tool', 'path': 'main.py',
                                                   'quote': 'def main'}]})
        return package, sources, record

    def run_prepare(self, package, sources, record, spec=None, name='work'):
        from creation_pipeline.runtime.local import LocalExecutor
        host = {'status': 'available', 'observed_at': 'test', 'gaps': [],
                'memory_bytes': 10 ** 10, 'cpus': 4}
        sentinel = planner.ModelUnavailable('sentinel: association was reached')
        with patch.object(LocalExecutor, 'host', return_value=host), \
                patch.object(entry, 'associate', side_effect=sentinel) as associate, \
                patch.object(planner, 'plan', side_effect=planner.PlanningError('sentinel plan')):
            preparation.prepare(record, package, sources, self.root / name,
                                spec or {}, LocalExecutor())
        return associate, record['runtime_preparation']['gaps']

    def test_declaration_is_used_before_automatic_recognition(self):
        package, sources, record = self.build(
            {'SKILL.md': SKILL_BLOCK_ONE, 'main.py': SOURCE_TEXT,
             'scripts/wrapper.py': WRAPPER})
        record['entry_declaration'] = {'kind': 'script', 'path': 'scripts/wrapper.py'}
        associate, gaps = self.run_prepare(package, sources, record)
        self.assertTrue(associate.called, gaps)
        self.assertEqual(associate.call_args.kwargs['entry']['entry'], 'scripts/wrapper.py')

    def test_without_a_declaration_the_package_is_still_ambiguous(self):
        package, sources, record = self.build(
            {'SKILL.md': SKILL_BLOCK_ONE, 'scripts/wrapper.py': WRAPPER})
        associate, gaps = self.run_prepare(package, sources, record)
        self.assertFalse(associate.called)
        self.assertEqual(gaps[0]['code'], 'entry_ambiguous')

    def test_an_explicit_caller_binding_still_wins(self):
        package, sources, record = self.build(
            {'SKILL.md': SKILL, 'main.py': SOURCE_TEXT, 'scripts/wrapper.py': WRAPPER})
        record['entry_declaration'] = {'kind': 'script', 'path': 'scripts/wrapper.py'}
        spec = {'binding': {'entry': 'main.py', 'source_id': 'tool',
                            'source_path': 'main.py', 'association': 'identical'}}
        associate, gaps = self.run_prepare(package, sources, record, spec=spec,
                                           name='work-binding')
        self.assertFalse(associate.called, gaps)
        binding = json.loads((self.root / 'work-binding/materials/binding.json')
                             .read_text(encoding='utf-8'))
        self.assertEqual(binding['entry'], 'main.py')
        self.assertEqual(binding['declaration_source'], 'user_binding')

    def test_a_rejected_declaration_blocks_instead_of_falling_back(self):
        package, sources, record = self.build({'SKILL.md': SKILL, 'main.py': SOURCE_TEXT})
        record['entry_declaration'] = {'kind': 'script', 'path': 'scripts/absent.py'}
        associate, gaps = self.run_prepare(package, sources, record)
        self.assertFalse(associate.called)
        self.assertEqual(gaps[0]['code'], 'entry_declaration_missing')


if __name__ == '__main__':
    unittest.main()
