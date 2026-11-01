"""Documented interface drift and executable minimal examples; offline only."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from creation_pipeline.cli import main
from creation_pipeline.contracts import versioned, fingerprint
from creation_pipeline.records import write_json

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('skillnet_contract',ROOT/'validation/deepseek-api/verify_skillnet_contract.py')
verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)


class SkillnetContractTests(unittest.TestCase):
    def setUp(self):
        self.value=json.loads((ROOT/'validation/deepseek-api/skillnet-contract.json').read_text(encoding='utf-8'))

    def test_documented_local_contract_matches_code(self):
        self.assertEqual(verifier.check(self.value),[])

    def test_version_field_and_unimplemented_endpoint_drift_are_detected(self):
        for field in ('runtime_request_fields','tool_record_v1_fields'):
            wrong=copy.deepcopy(self.value);wrong[field].append('platform_invented_id')
            self.assertTrue(any(x['field']==field for x in verifier.check(wrong)))
        wrong=copy.deepcopy(self.value);wrong['existing_entrypoints']['creation_pipeline.runtime.shared_tool'].append('remote_resolve')
        self.assertTrue(any('remote_resolve' in x['field'] for x in verifier.check(wrong)))

    def test_minimal_cli_examples_never_start_model_or_docker(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);config=root/'config.json'
            write_json(config,{'prompt':'Inspect the source capability','sources':[{'id':'example','path':str(root/'source')}]})
            with patch('creation_pipeline.cli.build',side_effect=AssertionError('No pipeline execution')), \
                 patch('creation_pipeline.runtime.local.process',side_effect=AssertionError('No Docker')):
                for argv in (['build',str(config),'--preflight'],['runtime-tools-inspect','--root',str(root/'empty'),'--offline']):
                    output=io.StringIO()
                    with redirect_stdout(output):self.assertEqual(main(argv),0)
                    data=json.loads(output.getvalue())
                    if argv[0]=='build':
                        self.assertEqual(data,{'status':'configuration_valid','source_count':1,'source_availability':'not_checked','model_calls':0})
                    else:
                        self.assertEqual(data['artifacts'],[]);self.assertEqual(data['business_acceptance'],'not_run')
            self.assertFalse((root/'empty').exists())
        payload=self.value['examples']['identity_payload']
        self.assertEqual(versioned(payload)['sha256'],fingerprint(payload))
