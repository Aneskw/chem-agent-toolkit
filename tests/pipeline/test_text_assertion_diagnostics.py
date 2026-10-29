"""Retained-file failures identify their channel without changing comparisons."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from creation_pipeline.runtime import runner


class TextAssertionDiagnosticTests(unittest.TestCase):
    def execute(self,pattern,*,file_output=True):
        text='ethanol\n  3  2 V2000\nM  END\n$$$$\n'
        case={'name':'retained-ethanol','origin':'model_proposed','basis':'source fixture',
              'args':[],'expected_exit':0,
              'acceptance':{'assertion':{'kind':'text_regex','pattern':pattern,
                                        'source_path':'observed/ethanol.sdf'}}}
        if file_output:
            case['output_file']='ethanol.sdf'
        def invoke(tool,image,args,input_dir,output_dir,entrypoint,timeout):
            if output_dir:
                (output_dir/'ethanol.sdf').write_text(text,encoding='utf-8',newline='')
            return {'exit_code':0,'stdout':'{"ok": true}' if file_output else text,'stderr':''}
        with tempfile.TemporaryDirectory() as tmp,patch.object(runner,'run',side_effect=invoke):
            return runner.run_case(Path(tmp),{'behavior':{'file_io':True}},'image',case)

    def test_terminal_newline_mismatch_is_named_and_still_fails(self):
        pattern=r'(?s).+\$\$\$\$\Z'
        result=self.execute(pattern)
        self.assertEqual(result['status'],'failed')
        problem=result['assertion_failure']
        self.assertEqual(problem['case'],'retained-ethanol')
        self.assertEqual(problem['channel'],'output_file')
        self.assertEqual(problem['output_file'],'ethanol.sdf')
        self.assertEqual(problem['pattern'],pattern)
        self.assertTrue(problem['actual_tail'].endswith('$$$$\n'))
        self.assertTrue(result['persisted_output'].endswith('$$$$\n'))

    def test_matching_file_has_no_failure_and_stdout_is_separate(self):
        pattern=r'(?s).+\$\$\$\$\n\Z'
        result=self.execute(pattern)
        self.assertEqual(result['status'],'passed')
        self.assertNotIn('assertion_failure',result)
        failed=self.execute(r'other',file_output=False)
        self.assertEqual(failed['assertion_failure']['channel'],'stdout')
        self.assertIsNone(failed['assertion_failure']['output_file'])

    def test_python_family_misasserted_as_exact_literal_is_named_without_relaxing_it(self):
        actual='{"pass": true, "python": "3.11.18"}\n'
        missing='"python": "3.11"'
        case={'name':'version-baseline','origin':'model_proposed','basis':'runtime version',
              'args':[],'expected_exit':0,'stdout_contains':['"pass": true',missing]}
        with tempfile.TemporaryDirectory() as tmp,patch.object(runner,'run',return_value={
                'exit_code':0,'stdout':actual,'stderr':''}):
            result=runner.run_case(Path(tmp),{'behavior':{'file_io':False}},'image',case)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['stdout'],actual)
        self.assertEqual(result['assertion_failures'][0]['case'],'version-baseline')
        self.assertEqual(result['assertion_failures'][0]['missing_literals'],[missing])
        self.assertEqual(result['assertion_failures'][0]['channel'],'stdout')


if __name__=='__main__':
    unittest.main()
