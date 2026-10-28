"""Author repair must see every structural problem in one round.

Run 8 died because the delivered package kept a top-level ``LICENSES.txt``: the
validator refused it, but the only repair feedback the model had received was a
check-definition error, so the one allowed repair round fixed the check and the
candidate still failed. Two things are asserted here:

* ``finish`` reports the package layout and the check definitions together;
* the author-visible packaging guidance states the closed role layout, so the model
  is told the rule it is graded on.
"""
import json
import tempfile
import unittest
from pathlib import Path

from creation_pipeline.artifacts.delivery import finish
from creation_pipeline.paths import ROOT

SKILL = '---\nname: demo\ndescription: demo skill\n---\n\nUse it.\n'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


class AuthorFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / 'package'
        write(self.package / 'SKILL.md', SKILL)
        write(self.package / 'scripts/run.py', 'print(1)\n')
        write(self.root / 'resource-state.json',
              json.dumps({'config': {'limits': {'package_bytes': None}}}))
        write(self.root / 'active-phase.json', json.dumps({'phase': 'author'}))

    def metadata(self, tests=None):
        path = self.root / 'meta.json'
        write(path, json.dumps({'tests': tests or [], 'issues': [], 'notes': []}))
        return path

    def test_a_root_level_file_and_a_bad_check_are_reported_together(self):
        write(self.package / 'LICENSES.txt', 'BSD-3-Clause\n')
        bad = {'name': 'usage', 'argv': ['python', '{package}/scripts/run.py'],
               'expected_exit': 0, 'stdout_contains': ['1'],
               'json_equals': 'not-an-object', 'purpose': 'demo', 'evidence': 'source'}
        with self.assertRaises(ValueError) as caught:
            finish(self.root, self.package, 'token', self.metadata([bad]))
        message = str(caught.exception)
        self.assertIn('Unsupported file role: LICENSES.txt', message)
        self.assertIn('json_equals', message)
        # One message, so a single repair round can address both.
        self.assertEqual(len(message.split('; ')), 2, message)

    def test_a_valid_package_still_finalises(self):
        result = finish(self.root, self.package, 'token', self.metadata())
        self.assertEqual(result['status'], 'saved')
        receipt = json.loads((self.root / 'deliveries/package.json').read_text(encoding='utf-8'))
        self.assertEqual(sorted(f['path'] for f in receipt['files']),
                         ['SKILL.md', 'scripts/run.py'])

    def test_the_author_is_told_the_closed_role_layout(self):
        packaging = (ROOT / 'docs/skills/packaging.md').read_text(encoding='utf-8')
        minimum = (ROOT / 'docs/skills/minimum.md').read_text(encoding='utf-8')
        for text, name in ((packaging, 'packaging'), (minimum, 'minimum')):
            self.assertIn('references/', text, name)
            self.assertIn('SKILL.md', text, name)
        for role in ('references/', 'scripts/', 'examples/', 'resources/', 'assets/'):
            self.assertIn(role, packaging, role)
        self.assertIn('only file at the top level', packaging)
        self.assertIn('refused by the delivery', packaging)
        self.assertIn('references/LICENSE.txt', packaging)


if __name__ == '__main__':
    unittest.main()
