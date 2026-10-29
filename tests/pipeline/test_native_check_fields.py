"""Unsupported assertion fields must not disappear while a weak marker passes."""
import unittest

from creation_pipeline.validation.runtime import validate_test,NATIVE_CHECK_FIELDS
from creation_pipeline.runtime.checks import mapped_checks
from creation_pipeline.generation.author import CHECK_EXECUTION_POLICY


class NativeCheckFieldTests(unittest.TestCase):
    def setUp(self):
        self.test={'name':'exact-oracle','argv':['{python}','-c','print(123)'],
                   'stdout_contains':['123'],'expected_exit':0}

    def test_unknown_exact_assertion_cannot_be_silently_dropped_by_mapping(self):
        self.test['stdout_equals']='DIFFERENT'
        for validate in (validate_test,lambda t:mapped_checks({'generated':[t]},
                {'entrypoint':['python','/opt/skill/package/main.py'],'language':'python'},[])):
            with self.subTest(validate=validate),self.assertRaises(ValueError) as caught:
                validate(self.test)
            self.assertIn('exact-oracle',str(caught.exception))
            self.assertIn('stdout_equals',str(caught.exception))
            self.assertIn('cannot be silently ignored',str(caught.exception))

    def test_unknown_fixture_or_typo_is_rejected_even_with_another_valid_assertion(self):
        for key,value in [('input_files',{'x.txt':'x'}),('json_equal',{'ok':False}),
                          ('timeout_seconds',123),('stderr_contains',['ERROR'])]:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,key):
                validate_test(dict(self.test,**{key:value}))

    def test_documented_checks_and_both_stage_contexts_share_the_supported_field_set(self):
        validate_test(dict(self.test,cwd='{run}',json_equals={'ok':True},artifacts=[],
                           evidence='e1',purpose='source-backed result',kind='positive',
                           candidate='current-skill'))
        self.assertEqual(CHECK_EXECUTION_POLICY['native_check_fields'],sorted(NATIVE_CHECK_FIELDS))


if __name__=='__main__':
    unittest.main()
