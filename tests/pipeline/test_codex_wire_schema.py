"""Offline Codex strict-schema compatibility; logical business contracts stay intact."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import jsonschema
from creation_pipeline.runtime import model_call as m, planner as p


class CodexWireSchemaTests(unittest.TestCase):
    def test_real_plan_patch_and_acceptance_schemas_are_closed_without_source_mutation(self):
        def check(node):
            if isinstance(node,dict):
                if node.get('type')=='object':
                    self.assertIs(node['additionalProperties'],False)
                    self.assertEqual(set(node['required']),set(node['properties']))
                self.assertNotEqual(node.get('type'),['string','object'])
                for value in node.values():check(value)
            elif isinstance(node,list):
                for value in node:check(value)
        for schema in (p.PLAN_SCHEMA,p.PATCH_SCHEMA,p.ACCEPTANCE_ONLY_SCHEMA):
            before=copy.deepcopy(schema);wire=m.codex_schema(schema)
            check(wire);jsonschema.Draft202012Validator.check_schema(wire)
            self.assertEqual(schema,before)

    def test_json_text_encoding_keeps_logical_object_compatibility_and_payload(self):
        payload={'operations':[{'id':'direct'}],'checks':[{'id':'nonblank'}]}
        node=p.PLAN_SCHEMA['properties']['plan']['properties']['acceptance_json']
        before=copy.deepcopy(node);wire=m.codex_schema(node)
        jsonschema.validate(payload,node)
        encoded=json.dumps(payload);jsonschema.validate(encoded,wire)
        self.assertEqual(json.loads(encoded),payload);self.assertEqual(node,before)
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(payload,wire)
        case=p.PLAN_SCHEMA['properties']['plan']['properties']['tests']['items']['properties']['case_json']
        self.assertEqual(m.codex_schema(case)['type'],'string')

    def test_remove_patch_can_supply_unused_value_without_changing_logical_optional_field(self):
        answer={'action':'patch','requested_files':[],'reason':'remove a generated item',
                'operations':[{'op':'remove','path':'/generated_files/0'}]}
        jsonschema.validate(answer,p.PATCH_SCHEMA)
        wire=m.codex_schema(p.PATCH_SCHEMA)
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(answer,wire)
        answer['operations'][0]['value_json']='null'
        jsonschema.validate(answer,wire);jsonschema.validate(answer,p.PATCH_SCHEMA)
        self.assertEqual(p.PATCH_SCHEMA['properties']['operations']['items']['required'],['op','path'])

    def test_undetermined_open_object_is_rejected_before_process_or_model(self):
        with patch.object(m,'run',side_effect=AssertionError('No model process')), \
             self.assertRaisesRegex(m.ModelConfigError,'open object'):
            m.call('input',p.obj({'unknown':{'type':'object'}}),'fixed')

    def test_receipt_separates_source_schema_and_exact_wire_file_hashes(self):
        schema=p.obj({'payload':{'type':['string','object']}})
        answer={'payload':'{"ok":true}'}
        events='\n'.join(json.dumps(e) for e in [
            {'type':'item.completed','item':{'type':'agent_message','text':json.dumps(answer)}},
            {'type':'turn.completed','usage':{}}])
        with tempfile.TemporaryDirectory() as tmp, patch.object(m,'codex_command',return_value=['codex']), \
             patch.object(m,'isolated_options',return_value=([],{})), \
             patch.object(m,'run',return_value=subprocess.CompletedProcess([],0,events,'')) as run:
            actual,receipt=m.call('input',schema,'fixed',audit_dir=Path(tmp))
            raw=(Path(tmp)/'schema.json').read_bytes()
            self.assertEqual(json.loads(raw),m.codex_schema(schema))
            self.assertEqual(receipt['wire_schema_sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(receipt['schema_sha256'],hashlib.sha256(json.dumps(schema,ensure_ascii=False,sort_keys=True).encode()).hexdigest())
            self.assertEqual(receipt['schema_projection'],'codex-json-text-v1')
            self.assertEqual(actual,answer);self.assertEqual(run.call_args.args[-1]['schema_sha256'],receipt['wire_schema_sha256'])

    def test_schema_rejection_reports_actual_server_field_and_redacts_diagnostics(self):
        message=json.dumps({'error':{'code':'invalid_json_schema','param':'text.format.schema',
            'message':'additionalProperties missing at acceptance_json; password=privatevalue'}})
        events=json.dumps({'type':'error','message':message})
        with patch.object(m,'codex_command',return_value=['codex']), \
             patch.object(m,'isolated_options',return_value=([],{})), \
             patch.object(m,'run',return_value=subprocess.CompletedProcess([],1,events,'')), \
             self.assertRaises(m.ModelConfigError) as error:
            m.call('input',{},'fixed')
        self.assertIn('acceptance_json',str(error.exception));self.assertIn('invalid_json_schema',str(error.exception))
        self.assertNotIn('privatevalue',str(error.exception))

    def test_deepseek_schema_and_dispatch_are_unchanged(self):
        schema=copy.deepcopy(p.PLAN_SCHEMA)
        with patch.object(m,'codex_schema',side_effect=AssertionError('No Codex projection')), \
             patch.object(m,'_deepseek_call',return_value=({'ok':True},{'backend':'deepseek_api'})) as send:
            m.call('input',schema,'provider-model',backend='deepseek_api')
        self.assertIs(send.call_args.args[1],schema)
        self.assertEqual(schema,p.PLAN_SCHEMA)
