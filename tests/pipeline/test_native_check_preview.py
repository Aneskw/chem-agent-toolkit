"""A truncated planning preview must never replace a delivered native program."""
import copy
import unittest

from creation_pipeline.runtime.preparation import declared_checks,NATIVE_CHECK_MAPPING_POLICY
from creation_pipeline.runtime.checks import mapped_checks


class NativeCheckPreviewTests(unittest.TestCase):
    def test_preview_is_explicit_and_original_program_is_mapped_in_full(self):
        program='import json\n'+('# source context\n'*20)+'print(json.dumps({"python":"3.11.18","pass":True}))'
        test={'name':'version-baseline','argv':['{python}','-c',program],
              'cwd':'{package}','expected_exit':0,'json_equals':{'pass':True},
              'purpose':'Check the real executable and original input','kind':'positive'}
        payload={'generated':[test]}
        before=copy.deepcopy(payload)
        preview=declared_checks(payload)[0]
        self.assertTrue(preview['preview_only'])
        self.assertTrue(preview['automatically_mapped'])
        self.assertNotIn('argv',preview)
        self.assertLess(len(preview['argv_preview'][2]),len(program))
        mapped=mapped_checks(payload,{'entrypoint':['python3','/opt/skill/package/main.py'],
                                     'language':'python'},[])
        self.assertEqual(len(mapped),1)
        self.assertEqual(mapped[0]['args'],['-c',program])
        self.assertEqual(mapped[0]['json_equals'],{'pass':True})
        self.assertEqual(payload,before)
        self.assertIn('not executable source',NATIVE_CHECK_MAPPING_POLICY)
        self.assertIn('does not waive that coverage',NATIVE_CHECK_MAPPING_POLICY)


if __name__=='__main__':
    unittest.main()
