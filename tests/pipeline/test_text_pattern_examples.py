"""Historical examples catch predicate contradictions, never grant execution passes."""
import copy
from pathlib import Path
import tempfile
import unittest

from creation_pipeline.runtime.acceptance import _case_contract
from creation_pipeline.runtime.runner import output_matches


class TextPatternExampleTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        quote='Output has three atoms and two bonds with a terminated record.'
        (self.root/'spec.txt').write_text(quote,encoding='utf-8')
        self.text='ethanol\n  3  2 V2000\nM  END\n$$$$\n'
        (self.root/'sample.sdf').write_text(self.text,encoding='utf-8',newline='')
        self.index={'files':{'spec.txt':{},'sample.sdf':{}},
                    'read_files':['spec.txt','sample.sdf']}
        cite={'source_path':'spec.txt','source_quote':quote}
        self.case={'name':'convert-ethanol','args':['x'],'expected_exit':0,'output_file':'ethanol.sdf',
                   'acceptance':dict(cite,purpose='operation',assertion=dict(cite,role='result',
                      kind='text_regex',pattern=r'(?s).+  3  2 V2000\nM  END\n\$\$\$\$\n\Z',
                      example_source_path='sample.sdf'))}

    def validate(self,case=None):
        _case_contract(case or self.case,{},self.index,self.root,['python','/opt/skill/package/main.py'])

    def test_terminal_newline_contradiction_is_named_before_execution(self):
        self.case['acceptance']['assertion']['pattern']=r'(?s).+\$\$\$\$\Z'
        with self.assertRaises(ValueError) as caught:
            self.validate()
        message=str(caught.exception)
        self.assertIn('convert-ethanol',message)
        self.assertIn('does not full-match',message)
        self.assertIn('sample.sdf',message)
        self.assertIn('actual_tail=',message)

    def test_valid_example_does_not_replace_actual_output_comparison(self):
        self.validate()
        self.assertTrue(output_matches(self.case,{'stdout':'','stderr':''},self.text))
        self.assertFalse(output_matches(self.case,{'stdout':'','stderr':''},self.text.replace('  3  2','  2  1')))
        self.assertFalse(output_matches(self.case,{'stdout':'','stderr':''},''))

    def test_example_must_be_an_actual_read_source_file(self):
        for value in ('unread.sdf',None,{'path':'sample.sdf'}):
            case=copy.deepcopy(self.case)
            case['acceptance']['assertion']['example_source_path']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'not read material'):
                self.validate(case)
        self.index['read_files'].append('../outside.sdf')
        self.case['acceptance']['assertion']['example_source_path']='../outside.sdf'
        with self.assertRaisesRegex(ValueError,'source tree'):
            self.validate()

    def test_examples_follow_the_same_newline_reading_as_output(self):
        (self.root/'sample.sdf').write_bytes(self.text.replace('\n','\r\n').encode('utf-8'))
        self.validate()


if __name__=='__main__':
    unittest.main()
