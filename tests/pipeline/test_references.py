"""Read-only reverse references; fixtures are not real Docker acceptance evidence."""
import copy
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from creation_pipeline import management, references
from creation_pipeline.artifacts.evidence import seal
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import fingerprint, versioned, runtime_request
from creation_pipeline.records import write_json, read_json, file_digest
from creation_pipeline.runtime.local import binding_identity
from tests.pipeline import test_runtime_build as fixture, test_shared_tool as shared


class ReferenceTests(unittest.TestCase):
    setUp = fixture.RuntimeBuildTests.setUp
    tearDown = fixture.RuntimeBuildTests.tearDown
    request = shared.SharedToolTests.request

    def seed(self, *, concrete=True, attempt=True):
        self.library = self.root/'library';self.library.mkdir()
        self.tools = self.root/'tools';self.tools.mkdir()
        self.environments = self.root/'environments';self.environments.mkdir()
        recipe = {'abi':1,'base':'python@sha256:'+'1'*64,'platform':'linux/amd64','prefix_text':'FROM pinned\n','files':[]}
        self.env = {'recipe_key':fingerprint(recipe),'image_id':'sha256:'+'e'*64,'daemon_id':'daemon'}
        write_json(self.environments/(self.env['recipe_key']+'.json'),dict(recipe=recipe,image_id=self.env['image_id'],daemon_id='daemon',complete_rebuild_lock=False))
        self.artifact = shared.SharedToolTests.artifact(self,self.request())
        self.artifact['environment'] = dict(self.env,status='built')
        self.artifact['artifact_id'] = fingerprint({k:v for k,v in self.artifact.items() if k!='artifact_id'})
        self.publish(self.artifact)
        self.entry = self.revision('alpha',concrete=concrete)
        self.save_catalog([self.entry])
        if attempt:self.add_attempt(self.entry)
        return self.params()

    def publish(self, artifact, filename=None):
        path=self.tools/(filename or artifact['request_key']+'-'+artifact['artifact_id']+'.json')
        write_json(path,artifact);return path

    def revision(self,name,*,concrete=True,version='one'):
        materials=self.root/'handoff'
        material_root=self.root/('materials-'+name+'-'+version)
        shutil.copytree(materials,material_root/'context')
        record=copy.deepcopy(self.record);delivery=record['delivery'];record['name']=name
        inputs=delivery['inputs'];inputs['candidate']=dict(inputs['candidate'],name=name,version=version)
        env={'plan':fixture.plan(),'limits':self.artifact['request']['runtime_limits'],'base_image':self.artifact['base_image'],
             'materials':manifest(material_root),'shared_tool':{'abi':self.artifact['abi'],'request':self.artifact['request'],
             'request_key':self.artifact['request_key'],'artifact':self.artifact if concrete else None}}
        inputs['environment']=versioned(env,2)
        inputs['bindings']=versioned(inputs['bindings']['payload'],2)
        delivery['candidate_id']='candidate-'+fingerprint({'name':name})
        delivery['revision_id']='rev-'+fingerprint(inputs)
        delivery['fingerprints']={k:fingerprint(inputs[k]) for k in delivery['fingerprints']}
        path='evidence/'+delivery['candidate_id']+'/'+version
        digest=seal(self.library/path,self.package,record,self.sources,material_root)
        return {'name':name,'revision_id':delivery['revision_id'],'freeze_sha256':digest,'evidence':path,
                'delivery':delivery,'history':[],'current_qualification':{'accepted':True,'reason':'historical fixture'}}

    def save_catalog(self,entries):write_json(self.library/'catalog.json',{'version':2,'skills':entries,'transaction':None})

    def add_attempt(self,entry,*,token='first',recorded_status='execution_failed'):
        relative='runtime/'+entry['delivery']['candidate_id']+'/'+token
        path=self.library/relative
        request=runtime_request(entry['delivery'],self.library/entry['evidence'],entry['freeze_sha256'],path)
        write_json(path/'build-log.json',[])
        receipt={'version':2,'status':'built','request':binding_identity(request),'image_id':self.artifact['image_id'],
                 'tag':'fixture','tool_artifact':self.artifact,'log_sha256':file_digest(path/'build-log.json')}
        write_json(path/'receipt.json',receipt)
        write_json(path/'execution/report.json',{'status':recorded_status,'request':receipt['request'],'image_id':receipt['image_id'],'tag':receipt['tag']})
        entry['runtime']={'path':relative,'files':manifest(path)}
        self.save_catalog([self.entry])
        return path

    def params(self,kind='tool'):
        target=dict(kind='tool',**{k:self.artifact[k] for k in ('request_key','artifact_id')}) if kind=='tool' else dict(kind='environment',**self.env)
        return {'libraries':[str(self.library)],'tool_registries':[str(self.tools)],'environment_registries':[str(self.environments)],'target':target}

    def query(self,params=None):return references.query(params or self.params())[0]

    def test_real_frozen_and_attempt_identity_join_never_infers_qualification(self):
        self.seed();result=self.query()
        self.assertTrue(result['scope']['complete_within_declared_layouts'],result['issues'])
        self.assertEqual(len(result['matches']['bindings']),1);self.assertEqual(len(result['matches']['attempts']),1)
        self.assertEqual(result['matches']['attempts'][0]['recorded_execution_status'],'execution_failed')
        self.assertIsNone(result['qualification']);self.assertIsNone(result['availability'])
        self.assertNotIn('accepted',str(result['matches']))

    def test_native_content_revision_counters_are_not_schema_versions(self):
        self.seed();result=self.query()
        self.assertEqual(self.entry['delivery']['inputs']['bindings']['version'],2)
        self.assertEqual(self.entry['delivery']['inputs']['environment']['version'],2)
        self.assertTrue(result['scope']['complete_within_declared_layouts'],result['issues'])

    def test_first_build_request_without_frozen_concrete_version_joins_receipt(self):
        self.seed(concrete=False);result=self.query()
        self.assertEqual(len(result['matches']['bindings']),1);self.assertEqual(result['unresolved_bindings'],[])
        self.assertEqual(result['matches']['bindings'][0]['origins'],['attempt_concrete_tool'])

    def test_environment_finds_tools_and_independent_skill_revisions(self):
        self.seed();second=self.revision('beta');self.save_catalog([self.entry,second])
        result=self.query(self.params('environment'))
        self.assertEqual(len(result['matches']['tools']),1)
        self.assertEqual({b['name'] for b in result['matches']['bindings']},{'alpha','beta'})

    def test_history_and_unlisted_freeze_are_scanned_without_latest_catalog_bias(self):
        self.seed();new=self.revision('alpha',version='two');new['history']=[self.entry]
        self.revision('orphan');self.save_catalog([new])
        result=self.query();rows=result['matches']['bindings']
        self.assertEqual(len(rows),3)
        self.assertTrue(any('.history[' in role for b in rows for role in b['catalog_roles']))
        self.assertTrue(any(b['name']=='orphan' and not b['catalog_roles'] for b in rows))

    def test_same_recipe_different_actual_environment_version_does_not_match(self):
        self.seed();params=self.params('environment');params['target']['image_id']='sha256:'+'0'*64
        result=self.query(params);self.assertEqual(result['matches'],{'tools':[],'bindings':[],'attempts':[]})
        self.assertEqual(result['target_registration']['status'],'not_found_in_scanned_roots')

    def test_same_tool_request_different_artifact_does_not_match(self):
        self.seed();params=self.params();params['target']['artifact_id']='0'*64
        self.assertEqual(self.query(params)['matches']['bindings'],[])

    def test_only_explicit_roots_no_environment_defaults_or_external_catalog_paths(self):
        self.seed();other=self.root/'unscanned';other.mkdir();(other/'catalog.json').write_text('{broken')
        with patch('creation_pipeline.runtime.shared_tool.registry_root',side_effect=AssertionError('No default root')), \
             patch('creation_pipeline.runtime.shared_environment.registry_root',side_effect=AssertionError('No default root')):
            params=self.params();params['tool_registries']=[];params['environment_registries']=[]
            result=self.query(params)
        self.assertEqual(result['target_registration']['status'],'not_scanned')
        self.assertEqual(set(result['scope']['unscanned_categories']),{'tool_registries','environment_registries'})
        self.assertFalse(result['scope']['global_complete']);self.assertFalse(any('unscanned' in i['path'] for i in result['issues']))

    def test_missing_library_does_not_become_no_references_or_create_directory(self):
        self.seed();missing=self.root/'missing';params=self.params();params['libraries'].append(str(missing))
        result=self.query(params)
        self.assertEqual(len(result['matches']['bindings']),1);self.assertFalse(result['scope']['complete_within_declared_layouts'])
        self.assertFalse(missing.exists());self.assertTrue(any(i['path']==str(missing) for i in result['issues']))

    def test_missing_tool_record_retains_embedded_reference_and_reports_scope(self):
        self.seed();next(self.tools.glob('*.json')).unlink()
        result=self.query();self.assertEqual(len(result['matches']['bindings']),1)
        self.assertEqual(result['target_registration']['status'],'not_found_in_scanned_roots')
        self.assertTrue(any(i['code']=='tool_record_not_found_in_scope' for i in result['issues']))

    def test_corrupt_catalog_still_scans_frozen_evidence_and_reports_raw_reason(self):
        self.seed();(self.library/'catalog.json').write_text('{broken')
        result=self.query();self.assertEqual(len(result['matches']['bindings']),1)
        self.assertTrue(any('JSONDecodeError' in i['reason'] for i in result['issues']))
        self.assertFalse(result['scope']['complete_within_declared_layouts'])

    def test_corrupt_tool_registration_cannot_add_a_verified_registry_location(self):
        self.seed();path=next(self.tools.glob('*.json'));record=read_json(path);record['image_id']='sha256:'+'b'*64;write_json(path,record)
        result=self.query();self.assertEqual(result['target_registration']['status'],'not_found_in_scanned_roots')
        self.assertTrue(any('artifact_id' in i['reason'] for i in result['issues']))

    def test_misnamed_tool_record_is_not_indexed_as_verified_version(self):
        self.seed(attempt=False,concrete=False);path=next(self.tools.glob('*.json'));path.rename(self.tools/'wrong.json')
        result=self.query();self.assertEqual(result['index']['tool_versions'],0)
        self.assertTrue(any(i['field']=='tool.filename' for i in result['issues']))

    def test_changed_frozen_source_not_a_verified_binding(self):
        self.seed();(self.library/self.entry['evidence']/'runtime/context/package/main.py').write_text('changed')
        result=self.query();self.assertEqual(result['matches']['bindings'],[])
        self.assertFalse(result['scope']['complete_within_declared_layouts'])
        self.assertTrue(any(i['field']=='freeze.files' for i in result['issues']))

    def test_corrupt_attempt_cannot_supply_first_concrete_version(self):
        self.seed(concrete=False);path=self.library/self.entry['runtime']['path']/'receipt.json';receipt=read_json(path)
        receipt['request']['freeze_sha256']='0'*64;write_json(path,receipt)
        result=self.query();self.assertEqual(result['matches']['bindings'],[]);self.assertTrue(result['unresolved_bindings'])

    def test_catalog_binding_drift_and_missing_attempt_are_named(self):
        self.seed();self.entry['freeze_sha256']='0'*64
        shutil.rmtree(self.library/self.entry['runtime']['path']);self.save_catalog([self.entry])
        result=self.query();self.assertTrue(any(i['code']=='catalog_reference_mismatch' for i in result['issues']))
        self.assertTrue(any('runtime' in i['path'] for i in result['issues']))

    def test_unresolved_request_is_not_promoted_to_concrete_tool_binding(self):
        self.seed(concrete=False,attempt=False);result=self.query()
        self.assertFalse(result['matches']['bindings']);self.assertTrue(result['unresolved_bindings'])
        self.assertFalse(result['scope']['complete_within_declared_layouts'])

    def test_foreign_locks_journals_and_temporary_publications_are_never_modified(self):
        self.seed();(self.library/'.catalog.lock').write_text('other-owner')
        (self.library/'.transaction.json').write_text('{pending');(self.tools/'request.lock').write_text('other-owner')
        (self.tools/'request.json.tmp').write_text('{partial');before=manifest(self.root)
        with patch('creation_pipeline.artifacts.store.recover',side_effect=AssertionError('No recovery')), \
             patch('creation_pipeline.artifacts.store.locked',side_effect=AssertionError('No lock')), \
             patch('creation_pipeline.contracts.qualify',side_effect=AssertionError('No qualification')), \
             patch('creation_pipeline.runtime.local.process',side_effect=AssertionError('No Docker/models')):
            result=self.query()
        self.assertEqual(before,manifest(self.root));self.assertFalse(result['scope']['complete_within_declared_layouts'])
        self.assertTrue(any(i['code']=='publication_pending' for i in result['issues']))

    def test_rebuilt_index_is_deterministic_and_does_not_persist(self):
        self.seed();before=manifest(self.root);first=self.query();second=self.query()
        first.pop('observed_at');second.pop('observed_at');self.assertEqual(first,second)
        self.assertEqual(before,manifest(self.root));self.assertEqual(first['index']['storage'],'ephemeral_rebuilt_each_query')

    def test_changed_during_scan_is_partial_and_never_silently_complete(self):
        self.seed();original=references._Scan.library
        def changed(scan,root):
            original(scan,root);(root/'catalog.json').write_text('{}')
        with patch.object(references._Scan,'library',changed):result=self.query()
        self.assertTrue(any(i['code']=='scan_changed' for i in result['issues']))
        self.assertFalse(result['scope']['complete_within_declared_layouts'])

    def test_full_scope_and_identity_validation_before_record_reads(self):
        self.seed();bad=[]
        for field,value in [('libraries','auto'),('tool_registries',['relative']),('environment_registries',[str(self.environments)]*2),('target',{'kind':'environment','recipe_key':self.env['recipe_key']})]:
            params=self.params();params[field]=value;bad.append(params)
        params=self.params();params.pop('libraries');bad.append(params)
        with patch.object(references._Scan,'run',side_effect=AssertionError('No scan')):
            for params in bad:
                with self.assertRaises(references.ReferenceError) as error:references.query(params)
                self.assertEqual(error.exception.code,'request_invalid')

    def test_symlink_record_is_not_followed(self):
        self.seed();path=self.tools/'linked.json';path.write_text('{not-read')
        original=references.has_link
        # Model the Windows reparse observation without requiring symlink privileges.
        with patch('creation_pipeline.references.has_link',side_effect=lambda p: Path(p)==path or original(p)):
            result=self.query()
        self.assertTrue(any(i['code']=='linked_path' for i in result['issues']))
        self.assertFalse(any('not-read' in i['reason'] for i in result['issues']))

    def test_management_envelope_has_no_query_mutation_effects(self):
        self.seed();result=management.dispatch({'api_version':management.API_VERSION,'request_id':'reverse-1','operation':'references.query','params':self.params()})
        self.assertTrue(result['ok'],result);self.assertEqual(result['data']['protocol'],references.PROTOCOL)
        for key,value in result['side_effects'].items():
            if key!='filesystem_reads':self.assertFalse(value,key)
        self.assertTrue(result['evidence']);self.assertEqual(set(result['evidence'][0]),{'path','kind','sha256'})

    def test_distinct_tool_versions_using_one_environment_are_both_reported(self):
        self.seed();other=copy.deepcopy(self.artifact);other['image_id']='sha256:'+'b'*64
        other['artifact_id']=fingerprint({k:v for k,v in other.items() if k!='artifact_id'});self.publish(other)
        result=self.query(self.params('environment'))
        self.assertEqual(len(result['matches']['tools']),2)
        self.assertEqual(len(result['matches']['bindings']),1)

    def test_missing_environment_record_keeps_dependency_edges_without_claiming_runtime_failure(self):
        self.seed();next(self.environments.glob('*.json')).unlink()
        result=self.query(self.params('environment'))
        self.assertEqual(len(result['matches']['tools']),1);self.assertEqual(len(result['matches']['bindings']),1)
        self.assertTrue(any(i['code']=='environment_record_not_found_in_scope' for i in result['issues']))
        self.assertIsNone(result['availability']);self.assertIsNone(result['qualification'])

    def test_self_contained_environment_receipt_does_not_invent_tool_artifact(self):
        self.seed(attempt=False)
        path=self.library/self.entry['evidence'];record=read_json(path/'record.json')
        inputs=record['delivery']['inputs'];env=inputs['environment']['payload'];env.pop('shared_tool')
        inputs['environment']=versioned(env);delivery=record['delivery'];delivery['revision_id']='rev-'+fingerprint(inputs)
        delivery['fingerprints']={k:fingerprint(inputs[k]) for k in delivery['fingerprints']}
        shutil.rmtree(path)
        digest=seal(path,self.package,record,self.sources,self.root/'materials-alpha-one')
        self.entry.update(freeze_sha256=digest,revision_id=delivery['revision_id'],delivery=delivery)
        attempt=self.add_attempt(self.entry);receipt=read_json(attempt/'receipt.json');receipt.pop('tool_artifact')
        receipt['shared_environment']=dict(self.env,status='hit');write_json(attempt/'receipt.json',receipt)
        self.entry['runtime']['files']=manifest(attempt);self.save_catalog([self.entry])
        result=self.query(self.params('environment'))
        bindings=result['matches']['bindings'];self.assertEqual(len(bindings),1)
        self.assertIsNone(bindings[0]['tool_reference'])
        self.assertEqual(bindings[0]['origins'],['self_contained_attempt_environment'])

    def test_external_catalog_locator_is_reported_without_following_or_reading(self):
        self.seed();outside=self.root/'secret-area';outside.mkdir();(outside/'freeze.json').write_text('{not-read')
        self.entry['evidence']=str(outside);self.save_catalog([self.entry]);result=self.query()
        self.assertTrue(any(i['field']=='skills[0].evidence' for i in result['issues']))
        self.assertFalse(any(i['path'].startswith(str(outside)) for i in result['issues']))

    def test_unknown_delivery_version_is_named_and_cannot_be_a_verified_binding(self):
        self.seed(attempt=False);path=self.library/self.entry['evidence'];record=read_json(path/'record.json')
        record['delivery']['protocol']=999;write_json(path/'record.json',record)
        freeze=read_json(path/'freeze.json');freeze['files']=[f for f in manifest(path) if f['path']!='freeze.json'];write_json(path/'freeze.json',freeze)
        result=self.query();self.assertEqual(result['matches']['bindings'],[])
        self.assertTrue(any(i['field']=='delivery.protocol' and i['actual']==999 for i in result['issues']))

    def test_malformed_delivery_shape_is_reported_without_crashing_query(self):
        self.seed(attempt=False);path=self.library/self.entry['evidence'];record=read_json(path/'record.json')
        record['delivery']=[];write_json(path/'record.json',record)
        freeze=read_json(path/'freeze.json');freeze['files']=[f for f in manifest(path) if f['path']!='freeze.json'];write_json(path/'freeze.json',freeze)
        result=self.query();self.assertTrue(any(i['field']=='delivery' for i in result['issues']))
        self.assertTrue(result['unresolved_bindings'][0]['catalog_claim_only'])

    def test_malformed_receipt_request_shape_is_reported_without_crashing_query(self):
        self.seed();self.entry['runtime'].pop('files');self.save_catalog([self.entry])
        path=self.library/self.entry['runtime']['path']/'receipt.json';receipt=read_json(path);receipt['request']=[];write_json(path,receipt)
        result=self.query();self.assertTrue(any(i['field']=='attempt.request' for i in result['issues']))
        self.assertEqual(result['matches']['attempts'],[])

    def test_report_drift_cannot_relabel_an_attempt_as_execution_passed(self):
        self.seed();path=self.library/self.entry['runtime']['path']/'execution/report.json'
        report=read_json(path);report['status']='execution_passed';write_json(path,report)
        result=self.query();self.assertTrue(any(i['field']=='catalog.attempt.files' for i in result['issues']))
        self.assertEqual(result['matches']['attempts'],[]);self.assertIsNone(result['qualification'])


if __name__=='__main__':unittest.main()
