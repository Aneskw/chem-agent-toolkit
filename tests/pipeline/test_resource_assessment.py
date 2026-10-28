"""The resource assessment must be expressible honestly, and unknown must stay blocked.

``status=unknown`` used to require a quotation from a read source, which meant an
undetermined requirement could only be expressed by inventing evidence. It now needs
no quotation but must name the open question in ``unresolved``; execution remains
blocked by the runtime gap ``resources_unknown`` either way.
"""
import copy
import tempfile
import unittest
from pathlib import Path

from creation_pipeline.runtime import planner
from tests.pipeline.test_runtime_build import TEXT, plan


class ResourceAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for path in ('package/main.py', 'sources/tool/main.py'):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(TEXT, encoding='utf-8')

    def base(self, status, unresolved, quote=None):
        p = copy.deepcopy(plan())
        p['resource_assessment'] = {'status': status, 'source_path': '', 'source_quote': '',
                                    'memory_bytes': 0, 'cpus': 0}
        if quote is not None:
            p['resource_assessment'].update(source_path='sources/tool/main.py', source_quote=quote)
        p['unresolved'] = unresolved
        return p

    def validate(self, p):
        return planner.validate_plan(p, planner.inventory(self.root, planner.options({})), self.root)

    def test_unknown_needs_no_quotation_when_the_open_question_is_stated(self):
        p = self.base('unknown', ['Peak memory is not documented in the read source'])
        # The assessment gate accepts it; any later rejection must be about something
        # else, never about a missing citation.
        try:
            self.validate(p)
        except (planner.PlanningError, ValueError) as exc:
            self.assertNotIn('status=', str(exc))

    def test_unknown_without_a_stated_question_is_rejected(self):
        for unresolved in ([], ['   ']):
            with self.assertRaises(planner.PlanningError) as caught:
                self.validate(self.base('unknown', unresolved))
            self.assertIn('status=unknown must state the undetermined resource requirement',
                          str(caught.exception))

    def test_complete_still_needs_an_exact_quotation(self):
        with self.assertRaises(planner.PlanningError) as caught:
            self.validate(self.base('complete', []))
        self.assertIn('status=complete needs an exact quotation', str(caught.exception))

    def test_complete_with_a_real_quotation_still_passes_the_gate(self):
        p = self.base('complete', [], quote=TEXT.splitlines()[0])
        try:
            self.validate(p)
        except (planner.PlanningError, ValueError) as exc:
            self.assertNotIn('status=', str(exc))

    def test_unknown_is_still_a_runtime_blocker(self):
        # The gate change does not touch the execution policy: local.py gap remains.
        source = (Path(__file__).resolve().parents[2] / 'creation_pipeline/runtime/local.py').read_text(encoding='utf-8')
        self.assertIn('resources_unknown', source)
        self.assertIn("!= \"complete\"", source)


if __name__ == '__main__':
    unittest.main()
