"""A literal ending in LF cannot equal an actual string whose edges are stripped."""
import copy
from pathlib import Path
import tempfile
import unittest

from creation_pipeline.runtime.acceptance import _case_contract
from creation_pipeline.runtime.planner import check_case,PlanningError
from creation_pipeline.runtime.runner import output_matches


class StrippedEqualityContractTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        quote='A completed conversion prints its source-backed report.'
        (self.root/'spec.txt').write_text(quote,encoding='utf-8')
        self.index={'files':{'spec.txt':{}},'read_files':['spec.txt']}
        cite={'source_path':'spec.txt','source_quote':quote}
        self.case={'name':'conversion-report','args':['x'],'expected_exit':0,
                   'acceptance':dict(cite,purpose='operation',assertion=dict(cite,
                       role='result',kind='stdout_equals',value='{"ok": true}\n'))}

    def validate(self,case):
        _case_contract(case,{},self.index,self.root,['python','/opt/skill/package/main.py'])

    def test_run73_style_literal_is_rejected_before_locking_and_comparison_stays_false(self):
        with self.assertRaises(ValueError) as caught:
            self.validate(self.case)
        message=str(caught.exception)
        self.assertIn('conversion-report',message)
        self.assertIn('stdout_equals.value',message)
        self.assertIn('strips actual text only',message)
        actual='{"ok": true}\n'
        self.assertFalse(output_matches(self.case,{'stdout':actual,'stderr':''},actual))
        fixed=copy.deepcopy(self.case)
        fixed['acceptance']['assertion']['value']='{"ok": true}'
        self.validate(fixed)
        self.assertTrue(output_matches(fixed,{'stdout':actual,'stderr':''},actual))
        self.assertFalse(output_matches(fixed,{'stdout':'{"ok": false}','stderr':''},'{"ok": false}'))

    def test_legacy_case_literal_has_the_same_satisfiability_gate(self):
        for expected in ('value\n',' value','value\t'):
            with self.subTest(expected=expected),self.assertRaisesRegex(PlanningError,'strips actual stdout only'):
                check_case({'args':[],'stdout_equals':expected})
        check_case({'args':[],'stdout_equals':'value'})

    def test_raw_whitespace_protocol_can_still_be_asserted_without_trimming(self):
        case=copy.deepcopy(self.case)
        case['acceptance']['assertion'].update(kind='text_regex',pattern=r'\{"ok": true\}\n')
        self.validate(case)
        self.assertTrue(output_matches(case,{'stdout':'{"ok": true}\n'},'{"ok": true}\n'))
        self.assertFalse(output_matches(case,{'stdout':'{"ok": true}'},'{"ok": true}'))


if __name__=='__main__':
    unittest.main()
