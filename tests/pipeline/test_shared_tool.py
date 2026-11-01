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
        with patch.dict('os.environ', {'CHEM_AGENT_SHARED_TOOLS': str(root)}), \
             patch.object(LocalExecutor, 'host', return_value=dict(HOST, engine_id='daemon')), \
             patch('creation_pipeline.runtime.local.process', self.probe(artifact)), \
             patch('creation_pipeline.runtime.planner.plan', side_effect=AssertionError('No model')):
            prepare(self.record, self.package, self.sources, self.root / 'prepare', {'shared_tool': declaration()}, LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['status'], 'runtime_blocked')
        self.assertIn('current_acceptance_required', self.record['runtime_preparation']['gaps'][0]['detail'])
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


if __name__ == '__main__':
    unittest.main()
