"""Management DTO boundary and delegation, no live model/Docker calls."""
import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from creation_pipeline import management as api
from creation_pipeline.cli import main
from creation_pipeline.records import write_json, file_digest
from creation_pipeline.runtime.preparation import handoff, RuntimeBlocked
from creation_pipeline.runtime import service
from tests.pipeline import test_runtime_build as fixture, test_shared_tool as shared


def envelope(operation,params):
    return {'api_version':api.API_VERSION,'request_id':'contract-1','operation':operation,'params':params}


class ManagementTests(unittest.TestCase):
    setUp=fixture.RuntimeBuildTests.setUp
    tearDown=fixture.RuntimeBuildTests.tearDown

    def descriptor(self):
        root=self.root/'context';handoff(self.package,self.sources,root)
        return {'context':str(root),'entry':'main.py','declaration':shared.declaration()}

    def published(self):
        descriptor=self.descriptor();described=api.dispatch(envelope('tool.describe',descriptor))
        self.assertTrue(described['ok'],described)
        artifact=shared.SharedToolTests.artifact(self,described['data']['request'])
        registry=shared.SharedToolTests.publish(self,artifact)
        return descriptor,described['data']['request_key'],artifact,registry

    def skill_params(self):
        library=self.root/'library';library.mkdir(exist_ok=True)
        entry={'name':'sample','revision_id':'rev-'+'a'*64,'freeze_sha256':'b'*64,'evidence':'evidence/frozen',
               'current_qualification':{'accepted':False,'reason':'current evidence is unverified'}}
        write_json(library/'catalog.json',{'version':2,'transaction':None,'skills':[entry]})
        return {'library':str(library),'name':'sample'},entry

    def test_descriptor_derives_source_identity_and_does_not_bind_or_execute(self):
        descriptor=self.descriptor()
        with patch('creation_pipeline.management.process',side_effect=AssertionError('No Docker')), \
             patch('creation_pipeline.management.resume_build',side_effect=AssertionError('No execution')):
            result=api.dispatch(envelope('tool.describe',descriptor))
        self.assertTrue(result['ok'],result);self.assertFalse(result['data']['binding_persisted'])
        self.assertEqual(result['data']['binding_observation']['association'],'identical')
        self.assertTrue(all(r['sha256']==file_digest(r['path']) for r in result['evidence']))
        self.assertFalse(result['side_effects']['docker_observation'])

    def test_published_contract_inventory_matches_versioned_facade(self):
        from creation_pipeline.records import read_json
        from creation_pipeline.paths import ROOT
        self.assertEqual(read_json(ROOT/'validation/local-management/contract-v1.json'),api.contract())

    def test_caller_cannot_assert_an_unverified_binding(self):
        descriptor=self.descriptor();descriptor['binding']={'association':'identical'}
        result=api.dispatch(envelope('tool.describe',descriptor))
        self.assertFalse(result['ok']);self.assertEqual(result['error']['code'],'request_invalid')
        descriptor.pop('binding');(self.root/'context/package/main.py').write_text('print("modified")')
        result=api.dispatch(envelope('tool.describe',descriptor))
        self.assertEqual(result['error']['code'],'binding_unresolved')
        self.assertIn('source',result['error']['reason'])

    def test_bad_envelopes_and_options_never_dispatch(self):
        values=[None,[],{},envelope([],{}),dict(envelope('tool.describe',{}),api_version='future'),
                envelope('skill.execute',{'library':'unused','name':'x','allow_diagnosis':True}),
                envelope('tool.availability',{'reference':{},'offline':1})]
        with patch('creation_pipeline.management._perform',side_effect=AssertionError('No action')):
            for value in values:
                result=api.dispatch(value);self.assertFalse(result['ok']);self.assertEqual(result['error']['code'],'request_invalid')
                self.assertEqual(set(result),{'api_version','request_id','operation','ok','observed_at','data','error','evidence','side_effects'})

    def test_request_drift_blocks_before_docker(self):
        descriptor=self.descriptor();key=api.dispatch(envelope('tool.describe',descriptor))['data']['request_key']
        for p in (self.root/'context/package/main.py',self.root/'context/sources/tool/main.py'):p.write_text('print("new version")')
        with patch('creation_pipeline.management._host',side_effect=AssertionError('No host probe')):
            result=api.dispatch(envelope('tool.resolve',{'descriptor':descriptor,'request_key':key}))
        self.assertEqual(result['error']['code'],'request_changed');self.assertEqual(result['error']['expected'],key)
        self.assertNotEqual(result['error']['actual'],key)

    def test_resolve_miss_is_successful_observation_and_never_creates_registry(self):
        descriptor=self.descriptor();key=api.dispatch(envelope('tool.describe',descriptor))['data']['request_key'];missing=self.root/'absent'
        with patch('creation_pipeline.management._host',return_value={'status':'available','engine_id':'daemon'}), \
             patch('creation_pipeline.management.process',side_effect=AssertionError('No images to inspect')):
            result=api.dispatch(envelope('tool.resolve',{'descriptor':descriptor,'request_key':key,'registry':str(missing)}))
        self.assertTrue(result['ok']);self.assertEqual(result['data']['observation']['status'],'miss')
        self.assertIsNone(result['data']['accepted']);self.assertFalse(missing.exists())

    def test_exact_select_returns_same_artifact_but_no_skill_binding_or_qualification(self):
        descriptor,key,artifact,root=self.published()
        reference={k:artifact[k] for k in ('request_key','artifact_id')}
        with patch('creation_pipeline.management._host',return_value={'status':'available','engine_id':'daemon'}), \
             patch('creation_pipeline.management.process',shared.SharedToolTests.probe(self,artifact)):
            result=api.dispatch(envelope('tool.select',{'descriptor':descriptor,'request_key':key,'registry':str(root),'reference':reference}))
        self.assertTrue(result['ok'],result);self.assertEqual(result['data']['artifact'],artifact)
        self.assertFalse(result['data']['binding_persisted']);self.assertIsNone(result['data']['accepted'])
        self.assertTrue(result['data']['observations'])

    def test_selected_mismatch_keeps_original_reason_field_and_evidence(self):
        descriptor,key,artifact,root=self.published();descriptor['constraints']=['new requirement']
        key=api.dispatch(envelope('tool.describe',descriptor))['data']['request_key']
        with patch('creation_pipeline.management._host',return_value={'status':'available','engine_id':'daemon'}):
            result=api.dispatch(envelope('tool.select',{'descriptor':descriptor,'request_key':key,'registry':str(root),
                'reference':{k:artifact[k] for k in ('request_key','artifact_id')}}))
        self.assertEqual(result['error']['code'],'selection_failed');self.assertEqual(result['error']['field'],'constraints')
        self.assertEqual(result['error']['raw']['observation']['reason'],'selected_request_mismatch')
        self.assertTrue(result['evidence']);self.assertEqual(result['error']['source_refs'],result['evidence'])

    def test_offline_availability_is_unknown_and_corrupt_record_is_not_trusted(self):
        _,_,artifact,root=self.published();params={'registry':str(root),'reference':{k:artifact[k] for k in ('request_key','artifact_id')},'offline':True}
        with patch('creation_pipeline.management._host',side_effect=AssertionError('No Docker')):
            result=api.dispatch(envelope('tool.availability',params))
        self.assertTrue(result['ok']);self.assertIsNone(result['data']['available']);self.assertIsNone(result['data']['accepted'])
        next(root.glob('*.json')).write_text('{}')
        result=api.dispatch(envelope('tool.availability',params));self.assertEqual(result['error']['code'],'artifact_invalid')
        self.assertTrue(result['error']['raw']['reason']);self.assertTrue(result['evidence'][0]['sha256'])

    def test_unavailable_image_is_a_negative_observation_not_a_pass(self):
        _,_,artifact,root=self.published()
        with patch('creation_pipeline.management._host',return_value={'status':'available','engine_id':'other'}):
            result=api.dispatch(envelope('tool.availability',{'registry':str(root),'reference':{k:artifact[k] for k in ('request_key','artifact_id')}}))
        self.assertTrue(result['ok']);self.assertFalse(result['data']['available'])
        self.assertEqual(result['data']['availability'],'different_daemon');self.assertIsNone(result['data']['passed'])

    def test_offline_qualification_never_recovers_or_reconciles_catalog(self):
        params,entry=self.skill_params();entry['current_qualification']['accepted']=True
        write_json(self.root/'library/catalog.json',{'version':2,'skills':[entry]})
        with patch('creation_pipeline.management.store.check'), \
             patch('creation_pipeline.management.store.get',side_effect=AssertionError('No catalog recovery')):
            result=api.dispatch(envelope('skill.qualification',dict(params,offline=True)))
        self.assertTrue(result['ok']);self.assertIsNone(result['data']['qualification']['accepted'])
        self.assertTrue(result['data']['historical']['current_qualification']['accepted'])
        self.assertFalse(result['side_effects']['catalog_lock_recovery_or_reconciliation_possible'])

    def test_online_qualification_preserves_false_and_declares_query_mutations(self):
        params,entry=self.skill_params()
        with patch('creation_pipeline.management.store.get',return_value=entry) as get:
            result=api.dispatch(envelope('skill.qualification',params))
        get.assert_called_once();self.assertTrue(result['ok']);self.assertFalse(result['data']['qualification']['accepted'])
        self.assertTrue(result['side_effects']['catalog_lock_recovery_or_reconciliation_possible'])

    def test_execute_delegates_validation_only_and_passed_does_not_imply_accepted(self):
        params,entry=self.skill_params();params.update(expected_revision=entry['revision_id'],expected_freeze_sha256=entry['freeze_sha256'])
        with patch('creation_pipeline.management.resume_build',return_value={'status':'execution_passed','accepted':False}) as resume:
            result=api.dispatch(envelope('skill.execute',params))
        self.assertTrue(result['ok']);self.assertTrue(result['data']['passed']);self.assertFalse(result['data']['accepted'])
        self.assertEqual(resume.call_args.kwargs,{'reuse_image':True,'allow_diagnosis':False,'expected_revision':entry['revision_id'],'expected_freeze':entry['freeze_sha256'],'include_evidence':True})

    def test_response_evidence_uses_own_attempt_even_when_catalog_has_a_later_one(self):
        params,entry=self.skill_params();root=self.root/'library'
        own=dict(entry,runtime={'path':'runtime/own-attempt'})
        later=dict(entry,runtime={'path':'runtime/later-attempt'})
        for attempt in ('own-attempt','later-attempt'):
            write_json(root/'runtime'/attempt/'receipt.json',{'identity':attempt})
        write_json(root/'catalog.json',{'version':2,'skills':[later]})
        params.update(expected_revision=entry['revision_id'],expected_freeze_sha256=entry['freeze_sha256'])
        with patch('creation_pipeline.management.resume_build',return_value={'status':'execution_passed','accepted':True,'evidence_snapshot':own}):
            result=api.dispatch(envelope('skill.execute',params))
        self.assertTrue(result['ok'])
        receipts=[r['path'] for r in result['evidence'] if r['path'].endswith('receipt.json')]
        self.assertEqual(receipts,[str(root/'runtime/own-attempt/receipt.json')])

    def test_execution_failure_and_cancellation_retain_raw_and_evidence(self):
        params,entry=self.skill_params();params.update(expected_revision=entry['revision_id'],expected_freeze_sha256=entry['freeze_sha256'])
        with patch('creation_pipeline.management.resume_build',return_value={'status':'runtime_blocked','gaps':[{'code':'image_missing','detail':'original'}]}):
            result=api.dispatch(envelope('skill.execute',params))
        self.assertEqual(result['error']['code'],'execution_blocked');self.assertEqual(result['error']['raw']['gaps'][0]['detail'],'original')
        self.assertTrue(result['evidence'])
        with patch('creation_pipeline.management.resume_build',side_effect=KeyboardInterrupt()):
            result=api.dispatch(envelope('skill.execute',params))
        self.assertEqual(result['error']['code'],'cancelled');self.assertTrue(result['evidence'])

    def test_missing_library_query_does_not_create_a_catalog(self):
        absent=self.root/'absent'
        result=api.dispatch(envelope('skill.qualification',{'library':str(absent),'name':'sample'}))
        self.assertEqual(result['error']['code'],'not_found');self.assertFalse(absent.exists())

    def test_corrupt_catalog_keeps_original_error_and_catalog_byte_reference(self):
        params,_=self.skill_params();path=self.root/'library/catalog.json';path.write_text('{broken')
        result=api.dispatch(envelope('skill.qualification',dict(params,offline=True)))
        self.assertFalse(result['ok']);self.assertEqual(result['error']['raw']['exception'],'JSONDecodeError')
        self.assertEqual(result['evidence'][0]['sha256'],file_digest(path))

    def test_cli_manage_uses_envelope_and_keeps_old_preflight_output(self):
        path=self.root/'request.json';write_json(path,envelope('tool.describe',self.descriptor()))
        output=io.StringIO()
        with redirect_stdout(output):self.assertEqual(main(['manage',str(path)]),0)
        self.assertTrue(json.loads(output.getvalue())['ok'])
        path.write_text('{bad JSON');result=api.from_file(path)
        self.assertEqual(api.exit_code(result),2);self.assertEqual(result['error']['object'],str(path))

    def test_validation_only_never_starts_automatic_diagnosis(self):
        selected={'runtime':{'repair_lane':'contract'},'revision_id':'rev-'+'a'*64,'freeze_sha256':'b'*64,'evidence':'frozen'}
        with patch('creation_pipeline.artifacts.store.get',return_value=selected), \
             patch.object(service,'automatic_revision',side_effect=AssertionError('No models')):
            with self.assertRaisesRegex(RuntimeBlocked,'cannot invoke models'):
                service.resume_build(self.root,'sample',reuse_image=True,allow_diagnosis=False)
        with patch('creation_pipeline.artifacts.store.get',return_value=selected), \
             patch.object(service,'verify',return_value={'delivery':{'inputs':{'environment':{'payload':{}}}}}), \
             patch.object(service,'automatic_revision',return_value={'legacy':'unchanged'}) as diagnosis:
            self.assertEqual(service.resume_build(self.root,'sample'),{'legacy':'unchanged'});diagnosis.assert_called_once()

    def test_revision_is_rechecked_inside_existing_writer_lock(self):
        params,selected=self.skill_params();changed=copy.deepcopy(selected);changed['revision_id']='rev-'+'c'*64
        with patch('creation_pipeline.artifacts.store.get',return_value=selected), \
             patch('creation_pipeline.artifacts.store.reconcile',return_value={'skills':[changed]}), \
             patch.object(service,'execute_prepared',side_effect=AssertionError('No stale execution')):
            with self.assertRaises(RuntimeBlocked) as error:
                service.resume_build(params['library'],'sample',reuse_image=True,allow_diagnosis=False,
                    expected_revision=selected['revision_id'],expected_freeze=selected['freeze_sha256'])
        self.assertEqual(error.exception.code,'revision_changed');self.assertEqual(error.exception.field,'revision_id')
