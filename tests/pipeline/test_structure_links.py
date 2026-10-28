"""The structure check must not read chemistry as Markdown.

Run 21 delivered a reference page listing RECAP SMARTS inside inline code spans. Those
patterns contain ``](`` (for example `` `[C:1](=!@[O:2])!@[#7:3]` ``), so the link
scanner reported a broken package link and the candidate failed although the delivery
was valid. Fenced blocks were already ignored; inline code spans are literal too.
"""
import tempfile
import unittest
from pathlib import Path

from creation_pipeline.artifacts.package import manifest
from creation_pipeline.validation.checks import static_checks

SKILL = ('---\nname: demo\ndescription: demo skill\n---\n\n'
         'Use `scripts/run.py`; see [the notes](references/notes.md).\n')


class StructureLinkTests(unittest.TestCase):
    def build(self, references):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / 'bundle'
        package = root / 'skills/demo'
        (package / 'references').mkdir(parents=True)
        (package / 'scripts').mkdir(parents=True)
        (package / 'SKILL.md').write_text(SKILL, encoding='utf-8')
        (package / 'scripts/run.py').write_text('print(1)\n', encoding='utf-8')
        (package / 'references/notes.md').write_text('# notes\n', encoding='utf-8')
        (package / 'references/reactions.md').write_text(references, encoding='utf-8')
        return root, package, manifest(package)

    def problems(self, references):
        root, package, files = self.build(references)
        report = static_checks(package, 'demo', bundle=root)
        return next(c for c in report if c['name'] == 'structure')['findings']

    def test_smarts_inside_inline_code_are_not_links(self):
        findings = self.problems('- 1 amide: `[C;!$(C([#7])[#7]):1](=!@[O:2])!@[#7;+0;!D1:3]>>*[C:1]=[O:2].*[#7:3]`\n'
                                 '- 2 ester: `[C:1](=!@[O:2])!@[O;+0:3]>>*[C:1]=[O:2].[O:3]*`\n')
        self.assertEqual(findings, [])

    def test_a_real_broken_link_is_still_reported(self):
        findings = self.problems('See [the missing page](references/missing.md).\n')
        self.assertTrue(any('Broken or external package link' in item for item in findings), findings)

    def test_a_link_whose_label_is_code_is_still_checked(self):
        findings = self.problems('See [`the page`](references/missing.md).\n')
        self.assertTrue(any('Broken or external package link' in item for item in findings), findings)


if __name__ == '__main__':
    unittest.main()
