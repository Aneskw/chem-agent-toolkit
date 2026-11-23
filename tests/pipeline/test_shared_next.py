"""Behavioral regressions for publishing, explicit coverage and recoverable delivery."""
import copy
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
import subprocess

from creation_pipeline.records import write_json, read_json
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.shared.registry import Registry, RegistryError, PublicRedirect
from creation_pipeline.shared.environment import EnvironmentLibrary, PublicationPending, compatible, run_checked, OperationError
from creation_pipeline.shared.contracts import runtime
from creation_pipeline.shared.verification import code_units, validate_decisions, bind_items, validate_plan, requires_audit, execute, execution_key, ReviewPlanError, TestPlanError
from creation_pipeline.shared.delivery import adopt
from creation_pipeline.shared.investigation import Investigations
from creation_pipeline.shared.pipeline import build
from tests.pipeline.test_shared_creation import env_plan, Session, Library, IMAGE, DIGEST
from creation_pipeline.models import load_config


class Response(io.BytesIO):
    def __init__(self, value):
        super().__init__(json.dumps(value).encode())


class SharedNextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        tool_state = patch('creation_pipeline.shared.environment_state.STATE_ROOT', self.root / '.pipeline/tool-libraries')
        tool_state.start()
        self.addCleanup(tool_state.stop)
        library_state = patch('creation_pipeline.shared.library.STATE_ROOT', self.root / '.pipeline/skill-libraries')
        library_state.start()
        self.addCleanup(library_state.stop)

    def environment_library(self):
        (self.root / 'source.txt').write_text('Source', encoding='utf-8')
        config_path = self.root / 'input.json'
        write_json(config_path, {'sources': [{'path': 'source.txt'}], 'environments': {
            'root': 'tools', 'repository': 'ghcr.io/example/project'}})
        class Remote:
            tags = {}
            public_access = False
            def resolve(self, image, authenticated=False): return self.tags.get(image)
            def public(self, image, digest, platform):
                if not self.public_access: raise RegistryError('Private package', 401)
                return {'status': 'verified', 'image': image, 'digest': digest, 'platform': platform}
        remote, calls = Remote(), []
        def docker(command, timeout):
            calls.append(command)
            stdout = ''
            if command[:2] == ['docker', '--config']:
                config = read_json(Path(command[2]) / 'config.json')
                self.assertEqual(config, {'auths': {'ghcr.io': {}}, 'credsStore': '', 'credHelpers': {}})
                self.assertIn('pull', command)
            if command[:2] == ['docker', 'push']: remote.tags[command[-1]] = DIGEST
            if command[:3] == ['docker', 'image', 'inspect']:
                stdout = json.dumps([{'Id': 'sha256:' + 'c'*64, 'Os': 'linux', 'Architecture': 'amd64',
                    'RepoDigests': ['ghcr.io/example/project@' + DIGEST] if command[-1].startswith('ghcr.io') else ['python@sha256:' + 'b'*64]}])
            if command[:3] == ['docker', 'run', '--rm']: stdout = '{"version":"3.11"}'
            return {'exit_code': 0, 'stdout': stdout, 'stderr': ''}
        return EnvironmentLibrary(load_config(config_path), self.root / 'state', docker, remote), remote, calls

    def test_docker_operation_deadline_is_opt_in(self):
        (self.root / 'source.txt').write_text('Source', encoding='utf-8')
        path = self.root / 'input.json'
        write_json(path, {'sources': [{'path': 'source.txt'}]})
        config = load_config(path)
        self.assertIsNone(config['environments']['operation_timeout'])
        calls = []
        def runner(command, timeout):
            calls.append((command, timeout))
            return {'exit_code': 0, 'stdout': 'Build completed', 'stderr': ''}
        library = EnvironmentLibrary(config, self.root / 'state', runner)
        self.assertEqual(library.registry.timeout, 30)
        library.command(['docker', 'build', 'context'])
        self.assertIsNone(calls[0][1])
        for value in (None, 1200):
            write_json(path, {'sources': [{'path': 'source.txt'}], 'environments': {'operation_timeout': value}})
            self.assertEqual(load_config(path)['environments']['operation_timeout'], value)
        for value in (0, -1, True, '600'):
            write_json(path, {'sources': [{'path': 'source.txt'}], 'environments': {'operation_timeout': value}})
            with self.assertRaises(ValueError):
                load_config(path)

    def test_preflight_honors_configured_model_deadlines(self):
        from creation_pipeline.shared.preflight import startup
        observed = []
        class SmokeSession:
            def __init__(self, config, sources, limits, work):
                observed.append(copy.deepcopy(limits))
                self.work, self.receipts = Path(work), []
                self.work.mkdir(parents=True)
            def stage(self, instructions, context, schema=None):
                for key in ('local_probe', 'cache_probe', 'resume_probe'):
                    target = Path(context[key])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(context['token'], encoding='utf-8')
                self.receipts.append({'phase': 'preflight'})
                return {'ready': True}
        source = self.root / 'source.txt'
        source.write_text('Source', encoding='utf-8')
        path = self.root / 'input.json'
        for label, deadline, total in [('unlimited', None, None), ('explicit', 240, 900)]:
            write_json(path, {'sources': [{'path': 'source.txt'}],
                'limits': {'model_timeout': deadline, 'total_seconds': total}})
            config = load_config(path)
            with patch('creation_pipeline.shared.preflight.observe', return_value=[]), \
                 patch('creation_pipeline.agent.backend.NativeSession', SmokeSession):
                receipts = startup(config, self.root / 'state', self.root / label, lambda _: None)
            self.assertEqual(len(receipts), 2)
            self.assertEqual(observed[-1]['model_timeout'], deadline)
            self.assertEqual(observed[-1]['total_seconds'], total)
            self.assertIsNone(observed[-1]['model_calls'])

    def test_explicit_docker_timeout_retains_build_output(self):
        def runner(command, timeout):
            error = subprocess.TimeoutExpired(command, timeout, output=b'Compiling graph library: 36%', stderr=b'Compiler still active')
            error.cleanup = [{'phase': 'terminate_process_tree'}]
            raise error
        with self.assertRaises(OperationError) as failure:
            run_checked(['docker', 'build', 'context'], 600, runner)
        observation = failure.exception.observation
        self.assertIn('36%', observation['stdout'])
        self.assertIn('Compiler still active', observation['stderr'])
        self.assertEqual(observation['cleanup'][0]['phase'], 'terminate_process_tree')

    def test_selective_execution_without_deadline_keeps_cleanup_bounded(self):
        package = self.root / 'package'
        package.mkdir()
        (package / 'SKILL.md').write_text('```python\nprint(2)\n```\n', encoding='utf-8')
        items = bind_items(package, [{'id': 'sample', 'file': 'SKILL.md', 'start_line': 2,
            'end_line': 2, 'necessary': True, 'reason': 'Original code', 'expected_check': 'Print 2'}])
        plan = {'cases': [{'item_id': 'sample', 'files': [], 'command': ['python', '/code/sample.py'],
            'expected_exit': 0, 'stdout_contains': ['2'], 'output_files': [], 'check_command': [],
            'basis': 'Print literal two'}], 'deferred': [], 'audit_risks': []}
        calls = []
        def runner(command, timeout):
            calls.append((command, timeout))
            return {'exit_code': 0, 'stdout': '2\n', 'stderr': ''}
        result = execute(package, 'test:1', 'linux/amd64', items, plan, self.root / 'work', None, runner)
        self.assertEqual(result['status'], 'verified')
        self.assertIsNone(calls[0][1])
        self.assertEqual(calls[-1][0][:3], ['docker', 'rm', '--force'])
        self.assertEqual(calls[-1][1], 30)

    def test_uploaded_private_record_resumes_only_public_check(self):
        library, remote, calls = self.environment_library()
        built = library.ensure(env_plan(), self.root / 'work')
        self.assertEqual((built['state'], built['image']), ('built', None))
        self.assertTrue(library.ensure(env_plan(), self.root / 'local-reuse')['reuse'])
        with self.assertRaises(PublicationPending) as failure: library.publish(built)
        uploaded = failure.exception.record
        self.assertEqual(uploaded['state'], 'published')
        self.assertEqual(uploaded['anonymous_access']['status'], 'unavailable')
        self.assertEqual(uploaded['image'], IMAGE)
        remote.public_access = True
        qualified = library.publish(built)  # Interrupted caller can still hold the pre-upload record.
        self.assertEqual(qualified['anonymous_access']['status'], 'verified')
        self.assertEqual(qualified['anonymous_pull']['exit_code'], 0)
        self.assertEqual(sum(c[:2] == ['docker', 'push'] for c in calls), 1)
        self.assertEqual(sum(c[:2] == ['docker', 'build'] for c in calls), 1)
        reused = library.publish(library.ensure(env_plan(), self.root / 'reuse'))
        self.assertTrue(reused['reuse'])
        remote.public_access = False
        with self.assertRaises(RegistryError): library.verify_public(reused)
        self.assertEqual(library.records()[0]['anonymous_access']['status'], 'unavailable')

    def test_pruned_local_image_is_rebuilt_instead_of_claimed_reusable(self):
        library, remote, calls = self.environment_library()
        built = library.ensure(env_plan(), self.root / 'work')
        original = library.run
        def pruned(command, timeout):
            if command[:3] == ['docker', 'image', 'inspect'] and command[-1] == built['content_id']:
                return {'exit_code': 1, 'stdout': '', 'stderr': 'Error: No such image: ' + built['content_id']}
            return original(command, timeout)
        library.run = pruned
        restored = library.ensure(env_plan(), self.root / 'rebuild')
        self.assertFalse(restored['reuse'])
        self.assertEqual(restored['version'], 'v2')

    def test_versions_skip_remote_collisions_and_never_overwrite_changed_tags(self):
        library, remote, calls = self.environment_library()
        remote.tags[IMAGE] = 'sha256:' + 'f'*64
        remote.public_access = True
        built = library.ensure(env_plan(), self.root / 'work')
        self.assertEqual(built['version'], 'v2')
        qualified = library.publish(built)
        remote.tags[qualified['image']] = 'sha256:' + 'e'*64
        with self.assertRaisesRegex(PublicationPending, 'refusing overwrite'): library.publish(qualified)
        self.assertEqual(sum(c[:2] == ['docker', 'push'] for c in calls), 1)
        self.assertEqual(library.reserve('env-python'), 'v3')

    def test_prepared_sources_rebind_ids_despite_unrelated_extra_documents(self):
        class Sources:
            evidence = [{'id': 'e1', 'kind': 'source_locator', 'sha256': 'sourcehash', 'path': 'api.py'}]
        sources = Sources()
        cache = Investigations(self.root / 'tools')
        cache.remember(env_plan(), sources)
        sources.evidence = [{'id': 'e7', 'kind': 'source_locator', 'sha256': 'extra', 'path': 'other.md'},
                            {**sources.evidence[0], 'id': 'e8'}]
        entity = {'tool_requirements': env_plan()['tools'], 'resources': [], 'environment_gaps': []}
        self.assertEqual(cache.resolve(entity, sources)['evidence'], ['e8'])
        cache.invalidate(env_plan(), 'Build disproved the recipe')
        self.assertIsNone(cache.resolve(entity, sources))

    def test_legacy_resume_strips_absent_shared_only_option(self):
        from creation_pipeline.pipeline import build as dispatch
        write_json(self.root / 'runs/old/checkpoint.json', {'workflow': 'legacy-script-images'})
        with patch('creation_pipeline.pipeline.build_legacy', return_value={}) as legacy:
            dispatch(state_root=self.root, resume_id='old', image_repository=None)
        self.assertNotIn('image_repository', legacy.call_args.kwargs)
        with self.assertRaisesRegex(ValueError, 'only supported'):
            dispatch(state_root=self.root, resume_id='old', image_repository='ghcr.io/example/project')

    def test_anonymous_registry_never_loads_publisher_credentials(self):
        requests = []
        def open_url(req, timeout):
            requests.append(req)
            if '/token?' in req.full_url:
                self.assertIsNone(req.get_header('Authorization'))
                return Response({'token': 'anonymous-scope-token'})
            raise urllib.error.HTTPError(req.full_url, 401, 'Private', {}, None)
        with patch('creation_pipeline.shared.registry.credentials', side_effect=AssertionError('must not access system credentials')):
            with self.assertRaises(RegistryError):
                Registry(opener=open_url).public(IMAGE, DIGEST, 'linux/amd64')
        self.assertEqual(len(requests), 2)

    def test_layer_redirect_does_not_send_registry_token_to_blob_host(self):
        import urllib.request
        original = urllib.request.Request('https://ghcr.io/v2/repo/blobs/sha256:x', headers={'Authorization': 'Bearer private'})
        request = PublicRedirect().redirect_request(original, None, 302, '', {}, 'https://blob.example/layer')
        self.assertIsNone(request.get_header('Authorization'))

    def test_startup_reports_registry_login_failure_before_inference(self):
        from creation_pipeline.shared.preflight import observe
        config = {'environments': {'repository': 'ghcr.io/example/project', 'publish': True}}
        def run(command, timeout):
            stdout = json.dumps({'OSType': 'linux'}) if command[:2] == ['docker', 'info'] else '--add-dir --output-schema --config'
            return {'exit_code': 0, 'stdout': stdout, 'stderr': ''}
        with patch('creation_pipeline.shared.preflight.codex_command', return_value=['codex']), \
             patch('creation_pipeline.shared.preflight.Registry.session', side_effect=RegistryError('Log in first')):
            checks = observe(config, run=run)
        self.assertEqual(next(c for c in checks if c['object'] == 'publication')['status'], 'blocked')

    def test_public_registry_verifies_index_platform_and_layers(self):
        import hashlib
        child = {'config': {'digest': 'sha256:config'}, 'layers': [{'digest': 'sha256:layer'}]}
        child_digest = 'sha256:' + hashlib.sha256(json.dumps(child).encode()).hexdigest()
        index = {'manifests': [{'digest': child_digest, 'platform': {'os': 'linux', 'architecture': 'amd64'}}]}
        expected = 'sha256:' + hashlib.sha256(json.dumps(index).encode()).hexdigest()
        def open_url(req, timeout):
            if '/token?' in req.full_url: return Response({'token': 'anonymous'})
            if req.full_url.endswith('/env-python-v1'): return Response(index)
            if req.full_url.endswith(child_digest): return Response(child)
            if req.full_url.endswith('/sha256:layer'): return io.BytesIO(b'x')
            raise AssertionError(req.full_url)
        registry = Registry(opener=open_url)
        self.assertEqual(registry.public(IMAGE, expected, 'linux/amd64')['status'], 'verified')
        with self.assertRaises(RegistryError): registry.public(IMAGE, DIGEST, 'linux/amd64')
        with self.assertRaises(RegistryError): registry.public(IMAGE, expected, 'linux/arm64')

    def test_consumer_projection_omits_defaults_but_retains_real_conditions(self):
        plan = env_plan()
        value = runtime(plan, IMAGE)
        self.assertEqual(set(value), {'image', 'platform', 'environment'})
        self.assertNotIn('conditions', value['environment'])
        plan['conditions'].update(network_required=True, minimum_memory_gib=8)
        self.assertEqual(runtime(plan)['environment']['conditions'], {'minimum_memory_gib': 8, 'network_required': True})
        self.assertTrue(compatible(env_plan(), plan))

    def test_probe_uses_the_same_numeric_version_equivalence_as_catalog_matching(self):
        library, _, _ = self.environment_library()
        plan = env_plan()
        plan['tools'][0]['version'] = '2024.9.6'
        library.run = lambda *args: {'exit_code': 0, 'stdout': '{"version":"2024.09.6"}', 'stderr': ''}
        library.probe('local', plan, self.root / 'probe')

    def test_resume_publication_does_not_reauthor(self):
        (self.root / 'source.txt').write_text('print(2)', encoding='utf-8')
        config = self.root / 'input.json'
        write_json(config, {'sources': [{'path': 'source.txt'}]})
        Session.calls, Session.mode = [], 'exempt'
        def pending(self, env):
            raise PublicationPending('Make the uploaded package Public', {**env, 'state': 'published', 'image': IMAGE, 'digest': DIGEST})
        with patch('creation_pipeline.shared.pipeline.EnvironmentLibrary', Library), patch.object(Library, 'publish', pending):
            first = build(config, self.root / 'state', library_root=self.root / 'skills', _session_factory=Session)
        self.assertEqual(first['counts'], {'blocked': 1})
        self.assertFalse((self.root / 'skills').exists())
        authors = sum(p == 'author' for _, p in Session.calls)
        with patch('creation_pipeline.shared.pipeline.EnvironmentLibrary', Library):
            second = build(state_root=self.root / 'state', resume_id=first['build_id'], image_repository='ghcr.io/example/replacement',
                           library_root=self.root / 'skills', _session_factory=Session)
        self.assertEqual(second['counts'], {'verified': 1}, second)
        self.assertEqual(sum(p == 'author' for _, p in Session.calls), authors)
        state = read_json(Path(second['workspace']) / 'checkpoint.json')
        self.assertEqual(state['config']['environments']['repository'], 'ghcr.io/example/replacement')

    def test_export_rejects_changed_final_payload(self):
        package = self.root / 'package'; package.mkdir()
        (package / 'SKILL.md').write_text('Approved', encoding='utf-8')
        record = {'status': 'verified', 'final_files': manifest(package), 'environment': {
            'image': IMAGE, 'digest': DIGEST, 'anonymous_access': {'status': 'verified', 'image': IMAGE, 'digest': DIGEST}}}
        (package / 'SKILL.md').write_text('Changed after review', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'differs'):
            adopt(package, record, self.root / 'library')

    def test_every_code_unit_needs_a_decision_even_if_exempt(self):
        package = self.root / 'package'; package.mkdir()
        (package / 'SKILL.md').write_text('```python\nprint(2)\n```\n```bash\ndocker pull {{image}}\n```\n', encoding='utf-8')
        units = code_units(package)
        with self.assertRaises(ReviewPlanError): validate_decisions(package, [], [])
        decisions = [{'unit_id': u['unit_id'], 'decision': 'exempt', 'reason': 'Documented example', 'execution_ids': []} for u in units]
        validate_decisions(package, decisions, [])
        decisions[0]['decision'] = 'runtime_example'
        with self.assertRaises(ReviewPlanError): validate_decisions(package, decisions, [])

    def test_fake_path_argument_needs_audit_and_is_not_a_direct_call(self):
        package = self.root / 'package'; package.mkdir()
        (package / 'task.py').write_text('raise RuntimeError("actual source")\n', encoding='utf-8')
        items = bind_items(package, [{'id': 'sample', 'file': 'task.py', 'start_line': 1, 'end_line': 1,
                                      'necessary': True, 'reason': 'Custom code', 'expected_check': 'Actual exception'}])
        case = {'item_id': 'sample', 'files': [], 'command': ['python', '-c', 'print(2)', '/code/sample.py'],
                'expected_exit': 0, 'stdout_contains': ['2'], 'output_files': [], 'check_command': [], 'basis': 'Source'}
        plan = {'cases': [case], 'deferred': [], 'audit_risks': []}
        self.assertTrue(requires_audit(items, plan))
        with self.assertRaises(TestPlanError):
            execute(package, IMAGE, 'linux/amd64', items, plan, self.root / 'work', 10,
                    run=lambda *args: self.fail('must not execute unaudited wrapper'))

    def test_file_existence_alone_cannot_claim_a_business_result(self):
        case = {'item_id': 'sample', 'files': [], 'command': ['python', '/code/sample.py'], 'basis': 'Source',
                'stdout_contains': [], 'output_files': ['result.csv'], 'check_command': []}
        with self.assertRaisesRegex(TestPlanError, 'existence alone'):
            validate_plan([{'id': 'sample', 'necessary': True}], {'cases': [case], 'deferred': []})

    def test_execution_cache_changes_with_helper_and_fixture(self):
        p = self.root / 'package'; p.mkdir()
        (p / 'task.py').write_text('import helper\n', encoding='utf-8')
        (p / 'helper.py').write_text('VALUE=1\n', encoding='utf-8')
        item = bind_items(p, [{'id': 'sample', 'file': 'task.py', 'start_line': 1, 'end_line': 1,
                              'necessary': True, 'reason': 'Glue', 'expected_check': 'Result'}])[0]
        env = {'content_id': 'fixed', 'platform': 'linux/amd64'}
        case = {'input': 'one'}
        key = execution_key(p, env, item, case)
        (p / 'helper.py').write_text('VALUE=2\n', encoding='utf-8')
        self.assertNotEqual(key, execution_key(p, env, item, case))
        self.assertNotEqual(execution_key(p, env, item, case), execution_key(p, env, item, {'input': 'two'}))

    def test_selective_execution_preserves_code_and_checks_outputs_under_long_windows_paths(self):
        import shutil
        from creation_pipeline.records import long_path
        package = self.root / 'package'
        package.mkdir()
        code = 'print("checked")\n'
        (package / 'sample.py').write_text(code, encoding='utf-8')
        item = bind_items(package, [{'id': 'simulate-and-summarize-campaigns', 'file': 'sample.py',
            'start_line': 1, 'end_line': 1, 'necessary': True, 'reason': 'Original code',
            'expected_check': 'Source-backed output'}])[0]
        work = self.root / ('deep-' + 'a'*75) / ('nested-' + 'b'*75)
        fixture = 'inputs/' + 'c'*65 + '/input.txt'
        artifact = 'results/' + 'd'*65 + '/result.json'
        plan = {'cases': [{'item_id': item['id'], 'files': [{'path': fixture, 'content': 'input'}],
            'command': ['python', '/code/' + item['id'] + '.py'], 'expected_exit': 0,
            'stdout_contains': ['checked'], 'output_files': [artifact], 'check_command': [],
            'basis': 'Known fixture and original code'}], 'deferred': []}
        seen = []
        def runner(command, timeout):
            if command[:2] == ['docker', 'run']:
                mounts = {value.split('target=')[1].split(',')[0]:
                    Path(value.split('source=')[1].split(',')[0])
                    for value in command if isinstance(value, str) and value.startswith('type=bind,source=')}
                source = mounts['/code'] / (item['id'] + '.py')
                self.assertGreater(len(str(source)), 260)
                self.assertEqual(long_path(source).read_text(encoding='utf-8'), code)
                self.assertEqual(long_path(mounts['/work'] / fixture).read_text(encoding='utf-8'), 'input')
                output = long_path(mounts['/work'] / artifact)
                output.parent.mkdir(parents=True)
                output.write_text('{"value":2}', encoding='utf-8')
                seen.append(str(source))
            return {'exit_code': 0, 'stdout': 'checked', 'stderr': ''}
        try:
            result = execute(package, IMAGE, 'linux/amd64', [item], plan, work, 30, runner)
            self.assertEqual(result['status'], 'verified')
            self.assertTrue(seen)
            self.assertEqual((package / 'sample.py').read_text(encoding='utf-8'), code)
        finally:
            self.assertTrue(work.resolve().is_relative_to(self.root.resolve()))
            if long_path(work).exists():
                shutil.rmtree(long_path(work))

    def test_author_repair_revision_bypasses_rejected_delivery_cache(self):
        # Exercise the actual author receipt path, not only token construction.
        from creation_pipeline.generation.content_author import author
        from creation_pipeline.resources.intake import Sources
        (self.root / 'source.txt').write_text('print(2)', encoding='utf-8')
        config_path = self.root / 'input.json'; write_json(config_path, {'sources': [{'path': 'source.txt'}]})
        config = load_config(config_path); config.update(_group_id='default', _environment_plan=env_plan(), _author_revision=1)
        session = Session(config, Sources(config, self.root / 'cache'), config['limits'], self.root / 'work')
        candidate = {'name': 'example', 'evidence': [{'id': 'e1', 'claim': 'Source example'}]}
        package = self.root / 'work/package'
        from creation_pipeline.shared.contracts import runtime
        package.mkdir(parents=True); write_json(package / 'runtime.json', runtime(env_plan()))
        Session.calls = []
        author(session, config, candidate, package, [{'problem': 'same feedback'}])
        author(session, config, candidate, package, [{'problem': 'same feedback'}])
        self.assertEqual(sum(p == 'author' for _, p in Session.calls), 1)
        config['_author_revision'] = 2
        author(session, config, candidate, package, [{'problem': 'same feedback'}])
        self.assertEqual(sum(p == 'author' for _, p in Session.calls), 2)
