"""A citation may name the upstream path; the snapshot path is what gets verified.

The supplied source files are snapshots (``document.py``), while the honest provenance
also records the upstream path (``rdkit/Chem/Recap.py``). Run 10 failed because the
association proposal used the upstream path and the exact-substring check found no
candidate. The alias is accepted only when exactly one supplied file maps to it, and
the quote is still checked against that file's bytes.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.artifacts.package import manifest
from creation_pipeline.records import write_json
from creation_pipeline.runtime import entry

TEXT = 'def RecapDecompose(mol, allNodes=None, minFragmentSize=0, onlyUseReactions=None):\n    mSmi = 1\n'
OPTIONS = {'model': 'test-model', 'model_timeout': 60, 'total_seconds': 60,
           'transport': 'default', 'progress_watch': 'observe', 'reasoning_effort': None,
           'service_tier': None, 'backend': 'codex_cli'}


class AliasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / 'package'
        self.source = self.root / 'source'
        for path in (self.package / 'SKILL.md', self.package / 'scripts/wrapper.py',
                     self.source / 'document.py'):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(TEXT if path.name == 'document.py' else '---\nname: demo\n---\n',
                            encoding='utf-8')
        self.sources = [{'id': 'recap', 'path': str(self.source), 'inventory': manifest(self.source),
                         'upstream': {'repo': 'https://github.com/rdkit/rdkit', 'path': 'rdkit/Chem/Recap.py',
                                      'commit': '237a1d9027c800784afed8788540f38a3aa595f8'}}]
        self.entry = {'kind': 'script', 'entry': 'scripts/wrapper.py',
                      'runtime_entry': 'package/scripts/wrapper.py'}

    def associate(self, proposal):
        review = {'review': {'status': 'pass', 'binding_verified': True,
                             'requirement_assessment': 'confirmed'},
                  'receipts': [], 'files': []}
        with patch('creation_pipeline.runtime.model_call.call', return_value=(proposal, {})), \
                patch('creation_pipeline.runtime.review.review_snapshot', return_value=review):
            return entry.associate({'name': 'probe'}, self.package, self.sources,
                                   self.root / 'audit', OPTIONS, entry=self.entry)

    def proposal(self, source_path):
        return {'source_id': 'recap', 'source_path': source_path,
                'quote': 'def RecapDecompose(mol, allNodes=None, minFragmentSize=0, onlyUseReactions=None):',
                'reason': 'The wrapper calls Recap.RecapDecompose exactly as documented.',
                'invocation': "python scripts/wrapper.py 'CCO'", 'supported': True}

    def test_the_snapshot_path_binds_directly(self):
        binding = self.associate(self.proposal('document.py'))
        self.assertEqual(binding['source_path'], 'document.py')
        self.assertNotIn('source_path_alias', binding)

    def test_the_unique_upstream_alias_resolves_to_the_snapshot(self):
        binding = self.associate(self.proposal('rdkit/Chem/Recap.py'))
        self.assertEqual(binding['source_path'], 'document.py')
        self.assertEqual(binding['source_path_alias'], 'rdkit/Chem/Recap.py')
        self.assertEqual(binding['source_sha256'], self.sources[0]['inventory'][0]['sha256'])

    def test_an_unrelated_path_is_still_refused(self):
        with self.assertRaises(entry.EntryError) as caught:
            self.associate(self.proposal('rdkit/Chem/Nonexistent.py'))
        self.assertEqual(caught.exception.code, 'binding_unresolved')

    def test_a_quote_that_does_not_match_the_snapshot_is_refused(self):
        proposal = dict(self.proposal('rdkit/Chem/Recap.py'),
                        quote='def RecapDecompose(mol, allNodes=None):')
        with self.assertRaises(entry.EntryError) as caught:
            self.associate(proposal)
        self.assertEqual(caught.exception.code, 'binding_unresolved')

    def test_an_ambiguous_alias_is_refused(self):
        second = self.source / 'extra.py'
        second.write_text(TEXT, encoding='utf-8')
        self.sources[0]['inventory'] = manifest(self.source)
        with self.assertRaises(entry.EntryError) as caught:
            self.associate(self.proposal('rdkit/Chem/Recap.py'))
        self.assertEqual(caught.exception.code, 'binding_unresolved')

    def test_the_prompt_lists_the_allowed_citation_paths(self):
        captured = {}

        def fake_call(prompt, schema, model, **kwargs):
            captured['prompt'] = prompt
            return self.proposal('document.py'), {}

        review = {'review': {'status': 'pass', 'binding_verified': True,
                             'requirement_assessment': 'confirmed'}, 'receipts': [], 'files': []}
        with patch('creation_pipeline.runtime.model_call.call', side_effect=fake_call), \
                patch('creation_pipeline.runtime.review.review_snapshot', return_value=review):
            entry.associate({'name': 'probe'}, self.package, self.sources,
                            self.root / 'audit2', OPTIONS, entry=self.entry)
        self.assertIn('citation_paths', captured['prompt'])
        self.assertIn('document.py', captured['prompt'])
        self.assertIn('belongs in reason', captured['prompt'])

    def test_the_independent_review_uses_the_batch_native_provider(self):
        """The association review is a model stage: it must not silently use the CLI."""
        captured = {}

        def fake_review(*args, **kwargs):
            captured.update(kwargs)
            return {'review': {'status': 'pass', 'binding_verified': True,
                               'requirement_assessment': 'confirmed'}, 'receipts': [], 'files': []}

        options = dict(OPTIONS, native_model={'backend': 'deepseek_api', 'api_model': 'deepseek-v4-pro'})
        with patch('creation_pipeline.runtime.model_call.call', return_value=(self.proposal('document.py'), {})), \
                patch('creation_pipeline.runtime.review.review_snapshot', side_effect=fake_review):
            entry.associate({'name': 'probe'}, self.package, self.sources,
                            self.root / 'audit-provider', options, entry=self.entry)
        self.assertEqual(captured['backend'], 'deepseek_api')
        self.assertEqual(captured['api_model'], 'deepseek-v4-pro')


if __name__ == '__main__':
    unittest.main()
