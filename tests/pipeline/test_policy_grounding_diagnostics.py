"""A rejected policy must identify the source/quote the planner needs to repair."""
import json
from pathlib import Path
import tempfile
import unittest

from creation_pipeline.runtime.acceptance import contracts


class PolicyGroundingDiagnosticTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        (self.root/'SKILL.md').write_text('Use `obabel` for conversion.\n',encoding='utf-8')
        self.index={'files':{'SKILL.md':{}},'read_files':['SKILL.md']}
        self.policy={'purposes':['operation'],'scope':'format conversion',
                     'invalid_input':'required','source_path':'SKILL.md',
                     'source_quote':'Use obabel for conversion.'}

    def rejection(self,policy):
        with self.assertRaises(ValueError) as caught:
            contracts({'acceptance_json':json.dumps(policy)},[],self.index,self.root)
        return str(caught.exception)

    def test_legacy_policy_names_path_and_changed_quote(self):
        message=self.rejection(self.policy)
        self.assertIn('acceptance_json citation',message)
        self.assertIn('does not occur verbatim in SKILL.md',message)
        self.assertIn('Use obabel for conversion.',message)
        # Adding backticks repairs grounding; coverage remains a separate gate.
        fixed=dict(self.policy,source_quote='Use `obabel` for conversion.')
        contracts({'acceptance_json':json.dumps(fixed)},[],self.index,self.root)

    def test_wrong_state_and_unread_path_are_both_named(self):
        message=self.rejection(dict(self.policy,invalid_input=True,source_path='not-read.md'))
        self.assertIn('acceptance_json.invalid_input=true',message)
        self.assertIn('source_path not-read.md is not read material',message)

    def test_declared_required_contract_names_both_failed_citations(self):
        policy=dict(self.policy,input_contract={'status':'required','constraint':'known format',
                    'source_path':'missing.md','source_quote':'format'})
        message=self.rejection(policy)
        self.assertIn('acceptance_json citation',message)
        self.assertIn('does not occur verbatim in SKILL.md',message)
        self.assertIn('acceptance_json.input_contract citation',message)
        self.assertIn('source_path missing.md is not read material',message)


if __name__=='__main__':
    unittest.main()
