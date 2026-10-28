"""Malformed policy field types are clean rejections, never a crash.

Run 34 died with ``TypeError: cannot use 'dict' as a set element`` because the model
returned ``invalid_input`` as an object and a set membership test hashed it. Model
output is data: every such field must be type-checked before it reaches a set/graph
operation, and a bad shape must be a repairable plan rejection.
"""
import json
import tempfile
import unittest
from pathlib import Path

from creation_pipeline.runtime.acceptance import contracts

BASE = {'scope': 'one nonempty SMILES argument', 'purposes': ['computation'],
        'source_path': 'doc.py', 'source_quote': 'from rdkit import Chem'}


class PolicyTypeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'doc.py').write_text('from rdkit import Chem\n', encoding='utf-8')
        self.index = {'files': {'doc.py': {'sha256': 'x'}}, 'read_files': ['doc.py']}

    def rejects(self, policy, fragment):
        with self.assertRaises(ValueError) as caught:
            contracts({'acceptance_json': json.dumps(policy)}, [], self.index, self.root)
        self.assertNotIsInstance(caught.exception, TypeError)
        self.assertIn(fragment, str(caught.exception))

    def test_an_object_invalid_input_is_rejected(self):
        self.rejects(dict(BASE, invalid_input={'status': 'required', 'constraint': 'x'}), 'Input policy')

    def test_object_purposes_are_rejected(self):
        self.rejects(dict(BASE, invalid_input='not_applicable', purposes=[{'a': 1}]), 'purposes as strings')

    def test_object_checks_are_rejected(self):
        self.rejects(dict(BASE, invalid_input='required', checks=[{'id': 'c'}]), 'checks')

    def check(self, ident='c'):
        return {'id': ident, 'channel': 'args', 'key': 0, 'pattern': r'.+',
                'source_path': 'doc.py', 'source_quote': 'from rdkit import Chem'}

    def operation(self, **overrides):
        base = {'id': 'op', 'selector': {'args': [{'index': 0, 'equals': 'from'}]},
                'checks': ['c'], 'purposes': ['computation'], 'require_persistence': False,
                'source_path': 'doc.py', 'source_quote': 'from rdkit import Chem'}
        base.update(overrides)
        return base

    def test_object_operations_and_check_ids_are_rejected(self):
        policy = dict(BASE, invalid_input='required', checks=[self.check()],
                      operations=[self.operation(checks=[{'id': 'c'}])])
        self.rejects(policy, 'check ids')
        policy = dict(BASE, invalid_input='required', checks=[self.check()],
                      operations=[{'id': 'op'}])
        self.rejects(policy, 'Operation')

    def test_object_operation_purposes_are_rejected(self):
        policy = dict(BASE, invalid_input='required', checks=[self.check()],
                      operations=[self.operation(purposes=[{'a': 1}])])
        self.rejects(policy, 'purposes')


if __name__ == '__main__':
    unittest.main()
