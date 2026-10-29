"""run73 repeated the wrong object shape after an ambiguous aggregate message."""
import json
from pathlib import Path
import tempfile
import unittest

from creation_pipeline.runtime.acceptance import contracts


class AggregateStatusDiagnosticTests(unittest.TestCase):
    def test_wrong_aggregate_object_is_distinguished_from_the_required_contract_object(self):
        contract={'status':'required','constraint':'known output format'}
        base={'scope':'format conversion','purposes':['operation'],
              'invalid_input':{'status':'required','detail':'mistaken aggregate object'}}
        policies=[dict(base,operations=[{'id':'convert-molecule','input_contract':contract}]),
                  dict(base,input_contract=contract)]
        with tempfile.TemporaryDirectory() as tmp:
            for policy in policies:
                with self.subTest(policy=policy),self.assertRaises(ValueError) as caught:
                    contracts({'acceptance_json':json.dumps(policy)},[],{'files':{}},Path(tmp))
                message=str(caught.exception)
                self.assertIn('acceptance_json.invalid_input',message)
                self.assertIn('received=',message)
                self.assertIn('JSON string "required"',message)
                self.assertIn('separate',message)
                if 'operations' in policy:
                    self.assertIn('convert-molecule',message)
                    self.assertIn('operations[].input_contract',message)


if __name__=='__main__':
    unittest.main()
