import copy
from pathlib import Path
import tempfile
import unittest

from creation_pipeline.runtime.acceptance import _case_contract, consistency
from creation_pipeline.runtime.runner import output_matches


class TextFileOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        quote='Retain the structure with three atoms and two bonds.'
        (self.root/'spec.txt').write_text(quote)
        self.index={'files':{'spec.txt':{}},'read_files':['spec.txt']}
        citation={'source_path':'spec.txt','source_quote':quote}
        self.case={'name':'structure-file','args':['--input','/input/example.smi'],
            'output_file':'structure.sdf','layer':'behavior','expected_exit':0,
            'stdout_contains':['"ok": true'],
            'acceptance':dict(citation,purpose='operation',assertion=dict(citation,role='result',
                kind='text_regex',pattern=r'(?s).*  3  2[^\n]*V2000\n.+M  END\n\$\$\$\$\n'))}
        self.text='title\nvariable time\n\n  3  2 V2000\natom/bond records\nM  END\n$$$$\n'

    def validate(self,case):
        _case_contract(case,{},self.index,self.root,['python','/opt/skill/package/main.py'])

    def test_stdout_metadata_and_retained_non_json_business_text_are_distinct(self):
        self.validate(self.case)
        result={'stdout':'{"ok": true}','stderr':''}
        self.assertTrue(output_matches(self.case,result,self.text))
        self.assertTrue(output_matches(self.case,result,self.text.replace('variable time','new time')))
        self.assertFalse(output_matches(self.case,result,self.text.replace('  3  2','  2  1')))
        self.assertFalse(output_matches(self.case,{'stdout':'{"ok": false}'},self.text))

    def test_old_json_predicate_on_non_json_artifact_still_fails(self):
        case=copy.deepcopy(self.case)
        case['acceptance']['assertion'].update(kind='json',path=['ok'],allowed_values=[True])
        self.assertFalse(output_matches(case,{'stdout':'{"ok": true}'},self.text))

    def test_invalid_or_empty_accepting_pattern_rejected_before_docker(self):
        for pattern in ('', '[', '(?s).*'):
            case=copy.deepcopy(self.case); case['acceptance']['assertion']['pattern']=pattern
            with self.subTest(pattern=pattern), self.assertRaises(ValueError):
                self.validate(case)

    def test_pattern_requires_own_source_evidence(self):
        case=copy.deepcopy(self.case); case['acceptance']['assertion'].pop('source_quote')
        with self.assertRaisesRegex(ValueError,'source evidence'):
            self.validate(case)

    def test_text_file_assertion_does_not_allow_wrapper_entrypoint(self):
        case=copy.deepcopy(self.case); case.update(entrypoint='python',args=['-c','print("fake")'])
        with self.assertRaisesRegex(ValueError,'configured business entrypoint'):
            self.validate(case)

    def test_exact_stdout_and_text_pattern_conflict_remains_named(self):
        case=copy.deepcopy(self.case); case.pop('output_file'); case['stdout_equals']='other'
        conflicts=consistency([case])
        self.assertEqual(conflicts[0]['case'],'structure-file')
        self.assertIn('pattern',conflicts[0]['basis'])
