"""Explicit scopes, conservative unknowns, legacy identities and freeze gates."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from creation_pipeline.artifacts.evidence import seal
from creation_pipeline.contracts import fingerprint, versioned, runtime_request, qualify
from creation_pipeline.records import file_digest
from creation_pipeline.runtime import request_contracts as rc, shared_tool as st, planner
from creation_pipeline.runtime.local import LocalExecutor
from creation_pipeline.runtime.preparation import prepare, handoff, bind, validate_spec
from tests.pipeline import test_runtime_build as fixtures, test_shared_tool as legacy


def scoped_spec():
    p=fixtures.plan()
    return {'shared_tool':legacy.declaration(),
        'tool_compatibility':{'version':1,'source_policy':rc.SOURCE_POLICY,
            'requirements':{k:p[k] for k in ('base_image','language','language_version')},
            'constraints':{'dependency_files':[],'install_commands':[],'environment':[]}},
        'skill_contract':{'version':1,'requirements':['Print the current business report.'],'constraints':['Write for operators.']}}


class RequestContractsTests(unittest.TestCase):
    setUp=fixtures.RuntimeBuildTests.setUp
    tearDown=fixtures.RuntimeBuildTests.tearDown

    def request(self,spec=None):
        spec=spec or scoped_spec();source=self.root/('handoff-'+str(len(list(self.root.glob('handoff-*')))))
        handoff(self.package,self.sources,source)
        return st.describe(source,bind(self.package,self.sources),spec['shared_tool'],spec.get('requirements',[]),
                           spec.get('constraints',[]),tool_compatibility=rc.tool_payload(spec))

    def artifact(self,request):
        value=legacy.SharedToolTests.artifact(self,request);value['abi']=request['abi']
        value['artifact_id']=fingerprint({k:v for k,v in value.items() if k!='artifact_id'})
        return st.validate_record(value)

    def test_business_text_and_current_cases_leave_tool_identity_equal(self):
        first=scoped_spec();a=self.request(first)
        second=copy.deepcopy(first);second['skill_contract']['requirements']=['Current Skill uses a differently named report check.']
        second['skill_contract']['constraints']=['Write for a batch curator.']
        (self.package/'SKILL.md').write_text('Current independent instructions')
        self.assertEqual(a,self.request(second))
        current=rc.skill_payload(first,rc.caller_context({'prompt':'A','checks':[{'name':'a'}]}))
        other=rc.skill_payload(second,rc.caller_context({'prompt':'B','checks':[{'name':'b'}]}))
        self.assertNotEqual(fingerprint(current),fingerprint(other))
        self.assertEqual(a['abi'],rc.ABI);self.assertEqual(a['request_protocol'],2)
        self.assertFalse({'requirements','constraints','skill_contract'}&a.keys())

    def test_unclassified_legacy_text_is_retained_and_changes_miss(self):
        a=scoped_spec();a.update(requirements=['An unknown future requirement'],constraints=['Opaque provisioning instruction'])
        request=self.request(a);self.assertEqual(request['tool_compatibility']['unclassified']['requirements'],a['requirements'])
        b=copy.deepcopy(a);b['requirements'][0]+=' changed'
        self.assertNotEqual(fingerprint(request),fingerprint(self.request(b)))
        payload=rc.tool_payload(a)
        with self.assertRaisesRegex(ValueError,'no silent removal'):
            st.describe(self.root/'handoff-0',bind(self.package,self.sources),a['shared_tool'],tool_compatibility=payload)

    def test_unknown_caller_constraint_values_are_not_reduced_to_keys(self):
        a=rc.tool_payload(scoped_spec(),rc.caller_context({'constraints':{'future_runtime':{'version':'1'}}}))
        b=rc.tool_payload(scoped_spec(),rc.caller_context({'constraints':{'future_runtime':{'version':'2'}}}))
        self.assertNotEqual(fingerprint(a),fingerprint(b))
        self.assertEqual(a['unclassified']['caller_constraints']['future_runtime']['version'],'1')

    def test_every_compatibility_change_rejects_selected_version(self):
        request=self.request();artifact=self.artifact(request);root=legacy.SharedToolTests.publish(self,artifact)
        probe=legacy.SharedToolTests.probe(self,artifact);reference={k:artifact[k] for k in ('request_key','artifact_id')}
        changed=[]
        for field,value in [('platform','linux/arm64'),('requirements',{'imports':{'numpy':'2.0.0'},'executables':[]}),
                            ('interface',dict(request['declaration']['interface'],entrypoint=['python3','/opt/skill/package/main.py']))]:
            r=copy.deepcopy(request);r['declaration'][field]=value;changed.append(r)
        for field,value in [('memory','2g'),('cpus','1'),('pids',64)]:
            r=copy.deepcopy(request);r['runtime_limits'][field]=value;changed.append(r)
        r=copy.deepcopy(request);r['tool_compatibility']['requirements']['base_image']='python:3.12-slim';changed.append(r)
        for r in changed:
            found,obs=st.select(r,reference,{'engine_id':'daemon'},probe,root)
            self.assertIsNone(found);self.assertEqual(obs['reason'],'selected_request_mismatch');self.assertTrue(obs['mismatches'])
        self.assertEqual(st.select(request,reference,{'engine_id':'daemon'},probe,root)[1]['status'],'hit')

    def test_source_data_and_unclassified_docs_are_never_auto_excluded(self):
        before=self.request();(self.source/'README.md').write_text('Changed business-looking documentation with unknown runtime role')
        self.sources[0]['inventory'].append({'path':'README.md','sha256':file_digest(self.source/'README.md'),'bytes':(self.source/'README.md').stat().st_size})
        self.assertNotEqual(before,self.request())
        (self.package/'rules.json').write_text('{"value":1}')
        self.assertIn('package/rules.json',[f['path'] for f in self.request()['files']])

    def test_unknown_scope_fields_and_versions_reject_without_inference(self):
        for field,value in [('version',2),('source_policy','ignore-markdown'),('unknown_requirement',True)]:
            s=scoped_spec();s['tool_compatibility'][field]=value
            with self.assertRaisesRegex(ValueError,'tool_compatibility'):validate_spec(s)
        s=scoped_spec();s['skill_contract']['platform']='linux/amd64'
        with self.assertRaisesRegex(ValueError,'skill_contract'):validate_spec(s)
        s=scoped_spec();del s['skill_contract']
        with self.assertRaisesRegex(ValueError,'scoped_contracts_required'):validate_spec(s)

    def test_plan_constraints_have_concrete_expected_actual(self):
        request=self.request()
        for mode in ('base_image','language_version','environment','install_commands'):
            p=fixtures.plan()
            if mode=='install_commands':p['steps']=[{'command':'pip install unknown','purpose':'x','evidence':'x'}]
            elif mode=='environment':p['environment']=[{'name':'CHANGED','value':'1'}]
            else:p[mode]='changed'
            with self.assertRaisesRegex(ValueError,'tool_compatibility.*expected=.*actual='):st.check_plan(request,p)

    def test_legacy_record_and_request_are_unchanged_and_cannot_be_mislabeled(self):
        source=self.root/'legacy';handoff(self.package,self.sources,source)
        request=st.describe(source,bind(self.package,self.sources),legacy.declaration(),['legacy requirement'],['legacy constraint'])
        self.assertEqual(request['abi'],st.ABI);self.assertNotIn('request_protocol',request)
        self.assertEqual(request['requirements'],['legacy requirement'])
        old=legacy.SharedToolTests.artifact(self,request);st.validate_record(old)
        new=self.artifact(self.request());new['abi']=st.ABI
        with self.assertRaisesRegex(ValueError,'request_protocol'):st.validate_record(new)

    def prepared_scope(self):
        s=scoped_spec();s['plan']=fixtures.plan();s['options']={'pin_base_image':True}
        with patch.object(LocalExecutor,'host',return_value=dict(fixtures.HOST,engine_id='daemon')), \
             patch.object(LocalExecutor,'resolve_base_image',return_value={'repo_digest':'python@sha256:'+'1'*64}), \
             patch.object(st,'resolve',return_value=(None,{'status':'miss','reason':'unit fresh registry'})), \
             patch.object(planner,'plan',side_effect=AssertionError('Model forbidden')):
            materials=prepare(self.record,self.package,self.sources,self.root/'prepare',s,LocalExecutor(),
                              caller_context=rc.caller_context({'prompt':'Current instructions'}))
        self.assertEqual(self.record['runtime_preparation']['status'],'prepared',self.record['runtime_preparation'])
        return materials

    def test_freeze_and_recovery_keep_scopes_separate_without_qualification(self):
        materials=self.prepared_scope();inputs=self.record['delivery']['inputs'];rc.verify_inputs(inputs)
        self.assertEqual(inputs['environment']['payload']['tool_compatibility']['version'],1)
        self.assertEqual(inputs['acceptance']['payload']['skill_contract']['version'],1)
        spec={};context=rc.inherit(spec,inputs)
        self.assertEqual(context['prompt'],'Current instructions');self.assertIn('tool_compatibility',spec)
        frozen=self.root/'frozen';sha=seal(frozen,self.package,self.record,self.sources,materials)
        runtime_request(self.record['delivery'],frozen,sha,self.root/'attempt')
        self.assertFalse(qualify(self.record['delivery'])[0])
        bad=copy.deepcopy(inputs);bad['acceptance']['payload']['skill_contract']['payload']['requirements'].append('drift')
        with self.assertRaisesRegex(ValueError,'skill_contract'):rc.verify_inputs(bad)

    def test_business_required_paths_still_block_even_though_not_in_tool_key(self):
        self.prepared_scope();inputs=copy.deepcopy(self.record['delivery']['inputs'])
        payload=inputs['acceptance']['payload']['skill_contract']['payload']
        payload['requirements']=['Required delivered files: missing.json.']
        inputs['acceptance']['payload']['skill_contract']=versioned(payload)
        with self.assertRaisesRegex(ValueError,'missing.json'):rc.verify_inputs(inputs)

    def test_runtime_only_repair_cannot_bypass_review_or_promote_legacy_scope(self):
        with self.assertRaisesRegex(ValueError,'scope_migration_requires_new_skill'):
            rc.inherit(scoped_spec(),self.record['delivery']['inputs'])
        self.prepared_scope();changed=scoped_spec();changed['skill_contract']['requirements']=['Different business obligation']
        with self.assertRaisesRegex(ValueError,'skill_contract_change_requires_review'):
            rc.inherit(changed,self.record['delivery']['inputs'])

    def test_failed_preparation_preserves_both_scopes_and_never_qualifies(self):
        with patch.object(LocalExecutor,'host',return_value={'status':'unavailable','gaps':[{'code':'offline','detail':'Offline fixture'}]}), \
             patch.object(st,'resolve',return_value=(None,{'status':'miss'})), \
             patch.object(planner,'plan',side_effect=AssertionError('No paid model')):
            prepare(self.record,self.package,self.sources,self.root/'failed',scoped_spec(),LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['status'],'runtime_blocked')
        inputs=self.record['delivery']['inputs'];rc.verify_inputs(inputs)
        restored={};rc.inherit(restored,inputs);self.assertIn('tool_compatibility',restored)
        self.assertFalse(qualify(self.record['delivery'])[0])
