"""Offline exact-tool protocol regressions. No model or Docker calls."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from creation_pipeline.contracts import fingerprint
from creation_pipeline.records import write_json
from creation_pipeline.runtime import shared_tool as st
from creation_pipeline.runtime.preparation import handoff, bind, prepare
from creation_pipeline.runtime.local import LocalExecutor
from tests.pipeline import test_runtime_build as fixtures
from tests.pipeline.test_runtime_build import plan, HOST


def declaration(p=None):
    p = p or plan()
    return {'closure': 'all-package-and-sources-except-skill-document', 'requirements': {'imports': {}, 'executables': []},
            'interface': {'entrypoint': p['entrypoint'], 'workdir': '/opt/skill', 'resources': [], 'runtime_network': False},
            'platform': 'linux/amd64', 'policy': st.POLICY}


class SharedToolTests(unittest.TestCase):
    def test_cli_preflight_rejects_external_executable_before_generation(self):
        from creation_pipeline.cli import main
        config = {'sources': [{'id': 'source', 'path': str(self.package)}],
                  'prompt': 'Convert with the original Open Babel entry',
                  'runtime_defaults': {'shared_tool': declaration()}}
        config['runtime_defaults']['shared_tool']['requirements']['executables'] = ['obabel']
        path = self.root / 'unsupported.json'
        write_json(path, config)
        with patch('creation_pipeline.cli.build', side_effect=AssertionError('must not generate')):
            self.assertNotEqual(main(['build', str(path), '--preflight']), 0)

    setUp = fixtures.RuntimeBuildTests.setUp
    tearDown = fixtures.RuntimeBuildTests.tearDown
    prepared = fixtures.RuntimeBuildTests.prepared

    def request(self):
        source = self.root / 'handoff'
        handoff(self.package, self.sources, source)
        return st.describe(source, bind(self.package, self.sources), declaration())

    def artifact(self, request):
        p = st.environment_plan(plan())
        pin = {'repo_digest': 'python@sha256:' + '1' * 64}
        record = {'abi': st.ABI, 'request': request, 'request_key': fingerprint(request), 'plan': p,
                  'base_image': pin, 'recipe_key': fingerprint({'plan': p, 'base_image': pin}),
                  'environment': {'status': 'not_applicable'}, 'image_id': 'sha256:' + 'a' * 64, 'daemon_id': 'daemon'}
        record['artifact_id'] = fingerprint(record)
        return record

    def test_resource_citation_must_survive_skill_document_changes(self):
        (self.package/'SKILL.md').write_text('A: no extra weights', encoding='utf-8')
        request = self.request()
        proposed = plan()
        proposed['resource_assessment'].update(source_path='package/SKILL.md', source_quote='A: no extra weights')
        with self.assertRaises(ValueError) as caught:
            st.check_plan(request, proposed)
        message = str(caught.exception)
        for value in ('shared_tool.resource_assessment.source_path', 'expected', 'actual',
                      'package/SKILL.md', 'sources/tool/main.py', 'implementation closure'):
            self.assertIn(value, message)

    def test_original_resource_citation_keeps_old_tool_available_after_prose_change(self):
        (self.package/'SKILL.md').write_text('A: operator guide', encoding='utf-8')
        request = self.request()
        artifact = self.artifact(request)
        root = self.publish(artifact)
        (self.package/'SKILL.md').write_text('B: curation guide', encoding='utf-8')
        other_source = self.root/'other-handoff'
        handoff(self.package, self.sources, other_source)
        current = st.describe(other_source, bind(self.package, self.sources), declaration())
        self.assertEqual(current, request)
        resolved, observation = st.resolve(current, {'engine_id':'daemon'}, self.probe(artifact), root)
        self.assertEqual(observation['status'], 'hit')
        self.assertEqual(resolved['artifact_id'], artifact['artifact_id'])

    def probe(self, artifact):
        image = {'Id': artifact['image_id'], 'Os': 'linux', 'Architecture': 'amd64',
                 'Config': {'Entrypoint': artifact['plan']['entrypoint'], 'User': '10001:10001', 'WorkingDir': '/opt/skill',
                            'Labels': {'chem.tool.request': artifact['request_key'], 'chem.tool.recipe': artifact['recipe_key']}}}
        return lambda *args: {'exit_code': 0, 'stdout': json.dumps([image])}

    def publish(self, artifact):
        root = self.root / 'registry'
        write_json(root / (artifact['request_key'] + '-' + artifact['artifact_id'] + '.json'), artifact)
        return root

    def test_prose_changes_do_not_change_request_but_support_bytes_do(self):
        request = self.request()
        (self.root / 'handoff/package/SKILL.md').write_text('Different independent skill')
        actual = st.describe(self.root / 'handoff', bind(self.package, self.sources), declaration())
        self.assertEqual(request, actual)
        (self.root / 'handoff/package/data.json').write_text('{}')
        self.assertNotEqual(request, st.describe(self.root / 'handoff', bind(self.package, self.sources), declaration()))

    def test_every_compatibility_input_misses(self):
        request = self.request(); artifact = self.artifact(request); root = self.publish(artifact)
        for field in ('files', 'requirements', 'constraints', 'declaration', 'entry_sha256'):
            changed = copy.deepcopy(request)
            if field == 'declaration':
                changed[field]['requirements'] = {'rdkit': 'different'}
            else:
                changed[field] = 'changed'
            resolved, observation = st.resolve(changed, {'engine_id': 'daemon'}, self.probe(artifact), root)
            self.assertIsNone(resolved, field)
            self.assertEqual(observation['status'], 'miss')

    def test_current_daemon_image_and_record_are_required(self):
        request = self.request(); artifact = self.artifact(request); root = self.publish(artifact)
        self.assertEqual(st.resolve(request, {'engine_id': 'daemon'}, self.probe(artifact), root)[1]['status'], 'hit')
        self.assertEqual(st.resolve(request, {'engine_id': 'other'}, self.probe(artifact), root)[1]['candidates'][0]['reason'], 'different_daemon')
        self.assertIsNone(st.resolve(request, {'engine_id': 'daemon'}, lambda *a: {'exit_code': 1, 'stdout': ''}, root)[0])
        path = next(root.glob('*.json')); path.write_text('{')
        self.assertEqual(st.resolve(request, {'engine_id': 'daemon'}, self.probe(artifact), root)[1]['candidates'][0]['reason'], 'invalid_record')

    def test_inspect_offline_never_creates_missing_root(self):
        path = self.root / 'missing'
        self.assertEqual(st.inspect(path)['artifacts'], [])
        self.assertFalse(path.exists())

    def test_timeout_does_not_remove_other_lock_and_exception_releases_owned_lock(self):
        root = self.root / 'locks'; root.mkdir(); path = root / 'key.lock'; path.write_text('another owner')
        with self.assertRaisesRegex(ValueError, 'deadline'):
            with st.locked(root, 'key', time.monotonic() + .01):
                self.fail('acquired foreign lock')
        self.assertEqual(path.read_text(), 'another owner')
        with self.assertRaises(KeyboardInterrupt):
            with st.locked(root, 'owned', time.monotonic() + 1):
                raise KeyboardInterrupt()
        self.assertFalse((root / 'owned.lock').exists())

    def test_no_acceptance_or_passed_state_in_published_version(self):
        artifact = self.artifact(self.request())
        self.assertFalse(set(artifact['plan']) & st.ACCEPTANCE)
        for value in (None, {}, {'tests': []}):
            with self.assertRaisesRegex(ValueError, 'current_acceptance_required'):
                st.combine(artifact, value)
        current = {k: copy.deepcopy(plan()[k]) for k in st.ACCEPTANCE}
        current['tests'][1]['name'] = 'independent-current-case'
        combined = st.combine(artifact, current)
        self.assertEqual(combined['tests'][1]['name'], 'independent-current-case')
        self.assertNotIn('tests', artifact['plan'])

    def test_hit_prepares_without_planner_or_base_resolution(self):
        artifact = self.artifact(self.request())
        root = self.publish(artifact)
        with patch.dict('os.environ', {'CHEM_AGENT_SHARED_TOOLS': str(root)}), \
             patch.object(LocalExecutor, 'host', return_value=dict(HOST, engine_id='daemon')), \
             patch('creation_pipeline.runtime.local.process', self.probe(artifact)), \
             patch('creation_pipeline.runtime.planner.plan', side_effect=AssertionError('No environment planner')), \
             patch.object(LocalExecutor, 'resolve_base_image', side_effect=AssertionError('No base pull')):
            prepare(self.record, self.package, self.sources, self.root / 'prepare',
                    {'shared_tool': declaration(), 'acceptance_plan': {k: plan()[k] for k in st.ACCEPTANCE}}, LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['status'], 'prepared', self.record['runtime_preparation'])
        self.assertEqual(self.record['runtime_preparation']['model_calls'], 0)
        self.assertEqual(self.record['delivery']['inputs']['environment']['payload']['shared_tool']['artifact'], artifact)
        self.assertFalse(self.record['delivery']['qualification']['accepted'])

    def test_uncertain_closure_named_rejection(self):
        request = self.request()
        for text in ('exec("print(1)")', 'import importlib', 'print("SKILL.md")', 'print(__file__)'):
            (self.root / 'handoff/package/main.py').write_text(text)
            with self.assertRaisesRegex(ValueError, 'shared_tool.closure'):
                st.describe(self.root / 'handoff', bind(self.package, self.sources), declaration())

    def test_record_tampering_and_embedded_binding_rejected(self):
        artifact = self.artifact(self.request())
        for field in ('image_id', 'daemon_id', 'recipe_key', 'request_key', 'artifact_id'):
            changed = copy.deepcopy(artifact); changed[field] = 'bad'
            with self.assertRaises(ValueError):
                st.validate_record(changed)

    def test_unknown_dependency_and_executable_requirements_fail_closed(self):
        self.request()
        for text in ('import absent_dependency', 'import subprocess', 'import os; os.system("external")'):
            (self.root / 'handoff/package/main.py').write_text(text)
            with self.assertRaisesRegex(ValueError, 'shared_tool.(requirements|closure)'):
                st.describe(self.root / 'handoff', bind(self.package, self.sources), declaration())

    def test_dependency_recipe_must_satisfy_explicit_request(self):
        request = self.request()
        request['declaration']['requirements']['imports'] = {'rdkit': '2025.9.1'}
        with self.assertRaisesRegex(ValueError, 'dependencies.rdkit: expected 2025.9.1, actual None'):
            st.check_plan(request, plan())

    def test_policy_invalidated_even_when_record_hash_recomputed(self):
        artifact = self.artifact(self.request())
        artifact['request']['declaration']['policy'] = 'obsolete'
        artifact['request_key'] = fingerprint(artifact['request'])
        artifact['artifact_id'] = fingerprint({k: v for k, v in artifact.items() if k != 'artifact_id'})
        with self.assertRaisesRegex(ValueError, 'policy'):
            st.validate_record(artifact)

    def test_hit_without_current_acceptance_does_not_inherit_tests(self):
        artifact = self.artifact(self.request()); root = self.publish(artifact)
        answer = {'action': 'plan', 'reason': 'current fixture', 'requested_files': [],
                  'plan': {k: copy.deepcopy(plan()[k]) for k in st.ACCEPTANCE}}
        answer['plan']['tests'][1]['name'] = 'new-skill-current-case'
        with patch.dict('os.environ', {'CHEM_AGENT_SHARED_TOOLS': str(root)}), \
             patch.object(LocalExecutor, 'host', return_value=dict(HOST, engine_id='daemon')), \
             patch('creation_pipeline.runtime.local.process', self.probe(artifact)), \
             patch('creation_pipeline.runtime.model_call.call', return_value=(answer, {'status': 'completed'})) as model:
            prepare(self.record, self.package, self.sources, self.root / 'prepare', {'shared_tool': declaration()}, LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['status'], 'prepared', self.record['runtime_preparation'])
        self.assertEqual(model.call_count, 1)
        self.assertEqual(self.record['runtime_preparation']['environment_planning_calls'], 0)
        self.assertEqual(self.record['runtime_preparation']['acceptance_planning_calls'], 1)
        self.assertEqual(self.record['delivery']['inputs']['acceptance']['payload']['cases'][1]['name'], 'new-skill-current-case')
        self.assertFalse(self.record['delivery']['qualification']['accepted'])

    def failed_build(self, cancel=False):
        pin = {'reference': 'python:3.11-slim', 'repo_digest': 'python@sha256:' + '1' * 64}
        root = self.root / 'registry'
        def command(args, timeout):
            if args[:2] == ['docker', 'build']:
                if cancel:
                    raise KeyboardInterrupt('caller cancelled')
                return {'exit_code': 1, 'stdout': '', 'stderr': 'deliberate failure'}
            return {'exit_code': 0, 'stdout': '', 'stderr': ''}
        with patch.dict('os.environ', {'CHEM_AGENT_SHARED_TOOLS': str(root)}), \
             patch.object(LocalExecutor, 'resolve_base_image', return_value=pin), \
             patch('creation_pipeline.runtime.local.process', side_effect=command), \
             patch.object(LocalExecutor, 'host', return_value=dict(HOST, engine_id='daemon')):
            request = self.prepared(spec={'plan': plan(), 'shared_tool': declaration(), 'options': {'pin_base_image': True}})
            # prepared() has its own legacy host fixture without engine_id; build
            # checks this independently using the current host above.
            if cancel:
                with self.assertRaises(KeyboardInterrupt):
                    LocalExecutor().build(request)
            else:
                receipt = LocalExecutor().build(request)
                self.assertEqual(receipt['status'], 'build_failed', receipt)
            self.assertEqual(list(root.glob('*.json')), [])
            self.assertEqual(list(root.glob('*.lock')), [])

    def test_failed_build_never_publishes(self):
        self.failed_build()

    def test_temporary_publication_file_is_not_a_candidate(self):
        artifact = self.artifact(self.request())
        root = self.root/'atomic'; root.mkdir()
        path = root/(artifact['request_key']+'-'+artifact['artifact_id']+'.json.tmp')
        path.write_text('{', encoding='utf-8')
        found, observation = st.resolve(artifact['request'], {'engine_id':'daemon'}, self.probe(artifact), root)
        self.assertIsNone(found)
        self.assertEqual(observation['candidates'], [])
        self.assertEqual(st.inspect(root)['artifacts'], [])
        self.assertEqual(path.read_text(), '{')

    def test_cancelled_waiter_preserves_foreign_lock(self):
        root = self.root/'waiter'; root.mkdir()
        lock = root/'key.lock'; lock.write_text('foreign')
        with patch.object(st.time, 'sleep', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            with st.locked(root, 'key', time.monotonic()+2):
                self.fail('foreign lock acquired')
        self.assertEqual(lock.read_text(), 'foreign')

    def test_tool_build_timeout_cannot_publish_or_qualify(self):
        root = self.root/'timeout-registry'
        pin = {'reference':'python:3.11-slim', 'repo_digest':'python@sha256:'+'1'*64}
        def timed_out(args, timeout):
            if args[:2] == ['docker','build']:
                return {'exit_code':None, 'stdout':'', 'stderr':'timed out', 'error':'TimeoutExpired'}
            return {'exit_code':0,'stdout':'','stderr':''}
        with patch.dict('os.environ', {'CHEM_AGENT_SHARED_TOOLS':str(root)}), \
             patch.object(LocalExecutor,'resolve_base_image',return_value=pin), \
             patch.object(LocalExecutor,'host',return_value=dict(HOST,engine_id='daemon')), \
             patch('creation_pipeline.runtime.local.process',side_effect=timed_out):
            request = self.prepared(spec={'plan':plan(),'shared_tool':declaration(),'options':{'pin_base_image':True}})
            result = LocalExecutor().build(request)
        self.assertEqual(result['status'],'build_failed')
        self.assertEqual(list(root.glob('*.json')),[])
        self.assertEqual(list(root.glob('*.lock')),[])
        from creation_pipeline.contracts import qualify
        self.assertFalse(qualify(self.record['delivery'])[0])

    def test_cancelled_builder_never_publishes_and_releases_only_owned_lock(self):
        self.failed_build(cancel=True)

    def test_replacement_lock_is_not_removed_by_original_owner(self):
        root = self.root/'locks'
        with st.locked(root, 'key', time.monotonic()+1):
            (root/'key.lock').write_text('replacement-owner')
        self.assertEqual((root/'key.lock').read_text(), 'replacement-owner')

    def test_runtime_resource_limits_are_part_of_exact_request(self):
        request = self.request()
        from creation_pipeline.runtime.planner import DEFAULTS
        changed = st.describe(self.root/'handoff', bind(self.package, self.sources), declaration(),
                              runtime_limits=dict(DEFAULTS, memory='2g'))
        self.assertNotEqual(fingerprint(request), fingerprint(changed))

    def test_supplied_changed_environment_does_not_get_silently_ignored(self):
        artifact = self.artifact(self.request()); root = self.publish(artifact)
        p = plan(); p['environment'] = [{'name': 'EXPLICIT_REQUIREMENT', 'value': 'changed'}]
        with patch.dict('os.environ', {'CHEM_AGENT_SHARED_TOOLS': str(root)}), \
             patch.object(LocalExecutor, 'host', return_value=dict(HOST, engine_id='daemon')), \
             patch('creation_pipeline.runtime.local.process', self.probe(artifact)), \
             patch.object(LocalExecutor, 'resolve_base_image', return_value=artifact['base_image']):
            prepare(self.record, self.package, self.sources, self.root/'prepare',
                    {'shared_tool': declaration(), 'plan': p, 'options': {'pin_base_image': True}}, LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['shared_tool']['reason'], 'supplied_environment_plan_mismatch')
        self.assertIsNone(self.record['delivery']['inputs']['environment']['payload']['shared_tool']['artifact'])

    def test_malformed_record_shapes_are_named_errors(self):
        for value in ([], None, {'abi': st.ABI}):
            with self.assertRaisesRegex(ValueError, 'schema'):
                st.validate_record(value)

    def test_explicit_reference_selects_only_named_version(self):
        request = self.request(); artifact = self.artifact(request); root = self.publish(artifact)
        other = copy.deepcopy(artifact); other['image_id'] = 'sha256:' + 'b'*64
        other['artifact_id'] = fingerprint({k:v for k,v in other.items() if k!='artifact_id'})
        self.publish(other)
        reference = {k:artifact[k] for k in ('request_key','artifact_id')}
        with patch.object(st,'resolve',side_effect=AssertionError('Do not select another candidate')):
            resolved, obs = st.select(request,reference,{'engine_id':'daemon'},self.probe(artifact),root)
        self.assertEqual(resolved,artifact); self.assertEqual(obs['selection'],'explicit')
        reference['artifact_id']='0'*64
        resolved,obs=st.select(request,reference,{'engine_id':'daemon'},lambda *a:self.fail('No image to inspect'),root)
        self.assertIsNone(resolved);self.assertEqual(obs['reason'],'selected_artifact_not_found')

    def test_explicit_reference_cannot_trust_renamed_other_record(self):
        request=self.request();artifact=self.artifact(request);root=self.publish(artifact)
        reference={'request_key':artifact['request_key'],'artifact_id':'0'*64}
        write_json(root/(reference['request_key']+'-'+reference['artifact_id']+'.json'),artifact)
        self.assertEqual(st.select(request,reference,{'engine_id':'daemon'},self.probe(artifact),root)[1]['reason'],
                         'invalid_selected_record')

    def test_explicit_reference_reports_changed_file_and_current_daemon(self):
        request=self.request();artifact=self.artifact(request);root=self.publish(artifact)
        reference={k:artifact[k] for k in ('request_key','artifact_id')}
        changed=copy.deepcopy(request);changed['files'][0]['sha256']='0'*64
        _,obs=st.select(changed,reference,{'engine_id':'daemon'},self.probe(artifact),root)
        self.assertEqual(obs['reason'],'selected_request_mismatch')
        self.assertEqual(obs['mismatches'][0]['field'],'files.'+request['files'][0]['path'])
        self.assertNotEqual(obs['mismatches'][0]['expected'],obs['mismatches'][0]['actual'])
        self.assertEqual(st.select(request,reference,{'engine_id':'other'},self.probe(artifact),root)[1]['reason'],'different_daemon')
        self.assertEqual(st.select(request,reference,{'engine_id':'daemon'},lambda *a:{'exit_code':1,'stdout':''},root)[1]['reason'],
                         'image_unavailable_or_changed')

    def test_selected_missing_version_blocks_before_any_planning_or_base_resolution(self):
        artifact=self.artifact(self.request());root=self.publish(artifact)
        with patch.dict('os.environ',{'CHEM_AGENT_SHARED_TOOLS':str(root)}), \
             patch.object(LocalExecutor,'host',return_value=dict(HOST,engine_id='daemon')), \
             patch('creation_pipeline.runtime.planner.plan',side_effect=AssertionError('No planning fallback')), \
             patch.object(LocalExecutor,'resolve_base_image',side_effect=AssertionError('No build fallback')):
            prepare(self.record,self.package,self.sources,self.root/'prepare',
                    {'shared_tool':declaration(),'tool_artifact':{'request_key':artifact['request_key'],'artifact_id':'0'*64}},LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['status'],'runtime_blocked')
        self.assertEqual(self.record['runtime_preparation']['model_calls'],0)
        self.assertEqual(self.record['runtime_preparation']['gaps'][0]['code'],'selected_tool_unavailable')

    def test_selected_version_still_generates_current_acceptance_and_freezes_selection(self):
        artifact=self.artifact(self.request());root=self.publish(artifact)
        reference={k:artifact[k] for k in ('request_key','artifact_id')}
        answer={'action':'plan','reason':'current checks','requested_files':[],
                'plan':{k:copy.deepcopy(plan()[k]) for k in st.ACCEPTANCE}}
        with patch.dict('os.environ',{'CHEM_AGENT_SHARED_TOOLS':str(root)}), \
             patch.object(LocalExecutor,'host',return_value=dict(HOST,engine_id='daemon')), \
             patch('creation_pipeline.runtime.local.process',self.probe(artifact)), \
             patch('creation_pipeline.runtime.model_call.call',return_value=(answer,{})) as model, \
             patch.object(LocalExecutor,'resolve_base_image',side_effect=AssertionError('No environment plan')):
            materials=prepare(self.record,self.package,self.sources,self.root/'prepare',
                {'shared_tool':declaration(),'tool_artifact':reference},LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['status'],'prepared',self.record['runtime_preparation'])
        self.assertEqual(model.call_count,1)
        self.assertEqual(self.record['runtime_preparation']['environment_planning_calls'],0)
        env=self.record['delivery']['inputs']['environment']['payload']
        self.assertEqual(env['shared_tool']['selection'],reference)
        self.assertFalse(self.record['delivery']['qualification']['accepted'])
        changed=copy.deepcopy(env);changed['shared_tool']['selection']['artifact_id']='0'*64
        with self.assertRaisesRegex(ValueError,'explicitly selected version'):
            st.verify_binding(changed,materials)

    def test_reference_requires_independent_declaration_and_disallows_paths(self):
        from creation_pipeline.runtime.preparation import validate_spec
        reference={'request_key':'a'*64,'artifact_id':'b'*64}
        with self.assertRaisesRegex(ValueError,'independent shared_tool'):
            validate_spec({'tool_artifact':reference})
        for value in ({'path':'/tmp/record.json'},dict(reference,artifact_id='../x'),dict(reference,artifact_id='A'*64)):
            with self.assertRaisesRegex(ValueError,'shared_tool.reference'):
                st.validate_reference(value)
        validate_spec({'tool_artifact':reference,'shared_tool':declaration()})

    def test_selected_plan_mismatch_blocks_instead_of_building_replacement(self):
        artifact=self.artifact(self.request());root=self.publish(artifact)
        p=plan();p['environment']=[{'name':'DIFFERENT','value':'required'}]
        with patch.dict('os.environ',{'CHEM_AGENT_SHARED_TOOLS':str(root)}), \
             patch.object(LocalExecutor,'host',return_value=dict(HOST,engine_id='daemon')), \
             patch('creation_pipeline.runtime.local.process',self.probe(artifact)), \
             patch('creation_pipeline.runtime.planner.plan',side_effect=AssertionError('No alternate plan')), \
             patch.object(LocalExecutor,'resolve_base_image',side_effect=AssertionError('No rebuild')):
            prepare(self.record,self.package,self.sources,self.root/'prepare',
                {'shared_tool':declaration(),'tool_artifact':{k:artifact[k] for k in ('request_key','artifact_id')},'plan':p},LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['gaps'][0]['code'],'selected_tool_plan_mismatch')
        self.assertFalse(self.record['delivery']['qualification']['accepted'])

    def test_candidate_selection_can_use_independent_declaration_from_defaults(self):
        from creation_pipeline.models import load_config
        from creation_pipeline.pipeline import runtime_spec_for
        reference={'request_key':'a'*64,'artifact_id':'b'*64}
        path=self.root/'config.json'
        write_json(path,{'sources':[{'id':'tool','path':self.sources[0]['path']}],
                         'runtime_defaults':{'shared_tool':declaration()},'runtime':{'probe':{'tool_artifact':reference}}})
        config=load_config(path);spec=runtime_spec_for(config,'probe')
        self.assertEqual(spec['tool_artifact'],reference)
        self.assertEqual(spec['shared_tool'],declaration())


if __name__ == '__main__':
    unittest.main()
