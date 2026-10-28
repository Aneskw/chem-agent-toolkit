"""Mechanism tests with explicit Docker/model doubles, not real acceptance evidence."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.artifacts.evidence import seal, verify
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.artifacts import store
from creation_pipeline.contracts import finalize, qualify, runtime_request
from creation_pipeline.records import write_json, read_json
from creation_pipeline.runtime import planner
from creation_pipeline.runtime.preparation import prepare, bind, RuntimeBlocked
from creation_pipeline.runtime.local import LocalExecutor
from creation_pipeline.runtime.service import execute_prepared, resume_build, prepare_revision

TEXT = '# CPU only; public Python standard library; no inputs, data, weights or services.\nprint("ok")\n'
PATH = 'sources/tool/main.py'
QUOTE = 'print("ok")'


def plan():
    assertion = {'role': 'report', 'kind': 'stdout_equals', 'value': 'ok', 'source_path': PATH, 'source_quote': QUOTE}
    acceptance = {'purpose': 'report', 'source_path': PATH, 'source_quote': QUOTE, 'assertion': assertion}
    cases = [{'name': 'environment', 'layer': 'environment', 'kind': 'derived', 'source_paths': [PATH],
              'basis': 'Python stdlib source', 'oracle_status': 'supported', 'tolerance': 0, 'limitations': [],
              'case_json': json.dumps({'entrypoint': 'python', 'args': ['--version'], 'expected_exit': 0})},
             {'name': 'entry', 'layer': 'interface', 'kind': 'reference', 'source_paths': [PATH],
              'basis': 'Source prints ok', 'oracle_status': 'supported', 'tolerance': 0, 'limitations': [],
              'case_json': json.dumps({'args': [], 'expected_exit': 0, 'stdout_equals': 'ok', 'acceptance': acceptance})}]
    return {'entrypoint': ['python', '/opt/skill/package/main.py'], 'script': 'package/main.py',
            'base_image': 'python:3.11-slim', 'platform': 'linux/amd64', 'language': 'python', 'language_version': '3.11',
            'source_files': ['package/main.py', PATH], 'dependencies': [], 'steps': [],
            'build_layout': {'dependency_files': [], 'prefix_steps': 0, 'reason': 'No dependencies'},
            'environment': [], 'resources': [], 'file_io': False, 'output_contract': 'ok', 'runtime_network': False,
            'network_reason': '', 'choices': [{'choice': 'Python stdlib', 'evidence': QUOTE, 'certainty': 'declared'}],
            'unresolved': [], 'unverified_behavior': ['No scientific claim'], 'generated_files': [], 'tests': cases,
            'resource_assessment': {'status': 'complete', 'source_path': PATH, 'source_quote': TEXT.splitlines()[0], 'memory_bytes': 0, 'cpus': 1},
            'acceptance_json': json.dumps({'invalid_input': 'not_applicable', 'scope': 'Print fixed report without user input',
                'purposes': ['report'], 'constraint': '', 'source_path': PATH, 'source_quote': TEXT.splitlines()[0]})}


HOST = {'status': 'available', 'observed_at': 'test', 'gaps': [], 'memory_bytes': 10**10, 'cpus': 4}


class RuntimeBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.package = self.root / 'package'; self.package.mkdir()
        self.source = self.root / 'source'; self.source.mkdir()
        for path in (self.package / 'main.py', self.source / 'main.py'):
            path.write_text(TEXT, encoding='utf-8')
        self.sources = [{'id': 'tool', 'path': str(self.source), 'inventory': manifest(self.source), 'resolved_ref': 'fixed-test-fixture'}]
        self.record = {'name': 'probe', 'status': 'ready', 'files': manifest(self.package), 'plan': {'name': 'probe'},
                       'checks': [{'name': 'content_review', 'status': 'pass', 'requirement_assessment': 'confirmed'}]}
        finalize(self.record, self.sources, {'status': 'required', 'reason': 'Executable',
                 'citations': [{'source_id': 'tool', 'path': 'main.py', 'quote': QUOTE}]})

    def tearDown(self):
        self.temp.cleanup()

    def prepared(self, p=None, spec=None):
        spec = spec if spec is not None else {'plan': p or plan()}
        with patch.object(LocalExecutor, 'host', return_value=HOST):
            materials = prepare(self.record, self.package, self.sources, self.root / 'work', spec, LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['status'], 'prepared', self.record['runtime_preparation'])
        frozen = self.root / 'output/evidence/probe'
        freeze = seal(frozen, self.package, self.record, self.sources, materials)
        self.record['durable_evidence'] = {'path': 'evidence/probe', 'freeze_sha256': freeze}
        return runtime_request(self.record['delivery'], frozen, freeze, self.root / 'attempt')

    def test_prepared_is_not_execution_and_freezes_actual_entry(self):
        request = self.prepared()
        self.assertFalse(qualify(self.record['delivery'])[0])
        self.assertEqual(self.record['delivery']['execution']['status'], 'not_run')
        self.assertTrue((Path(request.frozen_directory) / 'runtime/context/package/main.py').exists())
        self.assertTrue((Path(request.frozen_directory) / 'runtime/locked-tests.json').exists())

    def test_script_path_as_unused_argument_cannot_bind_execution(self):
        for number, prefix in enumerate((['python', '-c', 'print(123)'], ['python', '-m', 'unrelated'],
                                        ['echo'], ['bash', '-c', 'echo ok'], ['python', '-W'])):
            with self.subTest(prefix=prefix):
                p = plan()
                p['entrypoint'] = prefix + ['/opt/skill/package/main.py']
                with patch.object(LocalExecutor, 'host', return_value=HOST), \
                     patch.object(planner, 'plan', side_effect=AssertionError('No model call')):
                    prepare(self.record, self.package, self.sources, self.root / ('bad-' + str(number)),
                            {'plan': p}, LocalExecutor())
                result = self.record['runtime_preparation']
                self.assertEqual(result['status'], 'runtime_blocked')
                self.assertEqual(result['gaps'][0]['code'], 'entry_mismatch')
                self.assertIn('/opt/skill/package/main.py', result['gaps'][0]['detail'])

    def test_bound_script_supports_direct_execution_and_safe_python_flags(self):
        from creation_pipeline.runtime.preparation import validate_bound_entrypoint
        for argv in (['/opt/skill/package/main.py'],
                     ['python3.11', '-u', '-B', '/opt/skill/package/main.py', '--input', 'value']):
            p = plan(); p['entrypoint'] = argv
            validate_bound_entrypoint(p, {'entry': 'main.py'})

    def test_unknown_and_ambiguous_block_without_model_or_docker(self):
        for unknown in (False, True):
            record = copy.deepcopy(self.record)
            if unknown:
                record['delivery']['inputs']['requirement']['status'] = 'unknown'
                record['delivery']['inputs']['requirement']['reason'] = 'Unknown scope'
            else:
                (self.package / 'second.py').write_text(TEXT)
            with patch.object(planner, 'plan', side_effect=AssertionError('unexpected model')), patch.object(LocalExecutor, 'host', side_effect=AssertionError('unexpected Docker')):
                prepare(record, self.package, self.sources, self.root / str(unknown), {}, LocalExecutor())
            self.assertEqual(record['delivery']['execution']['status'], 'runtime_blocked')
            self.assertIn(record['runtime_preparation']['gaps'][0]['code'], {'requirements_unknown', 'binding_unresolved', 'entry_ambiguous'})

    def test_docker_unavailable_does_not_call_model(self):
        with patch.object(LocalExecutor, 'host', return_value={'gaps': [{'code': 'docker_unavailable', 'detail': 'missing'}]}), patch.object(planner, 'plan', side_effect=AssertionError('unexpected model')):
            prepare(self.record, self.package, self.sources, self.root / 'work', {}, LocalExecutor())
        self.assertEqual(self.record['delivery']['execution']['status'], 'runtime_blocked')

    def test_model_timeout_records_attempt_and_transport_blocker(self):
        from creation_pipeline.runtime import model_call
        with patch.object(LocalExecutor, 'host', return_value=HOST), \
                patch.object(model_call, 'call', side_effect=model_call.ModelExecutionError('timed out')) as call:
            prepare(self.record, self.package, self.sources, self.root / 'work', {}, LocalExecutor())
        call.assert_called_once()
        result = self.record['runtime_preparation']
        self.assertEqual(result['model_calls'], 1)
        self.assertEqual(result['gaps'][0]['code'], 'model_unavailable')
        self.assertEqual(result['gaps'][0]['blocker_kind'], 'model_transport')
        self.assertEqual(self.record['delivery']['content']['status'], 'passed')

    def test_rejected_call_guard_is_not_counted(self):
        def guard():
            raise RuntimeBlocked('explicit_budget', 'No calls left')
        with patch.object(LocalExecutor, 'host', return_value=HOST), \
                patch.object(planner.model_call, 'call') as call:
            prepare(self.record, self.package, self.sources, self.root / 'work', {}, LocalExecutor(), guard)
        call.assert_not_called()
        self.assertEqual(self.record['runtime_preparation']['model_calls'], 0)

    def test_association_transport_failure_is_not_an_input_defect(self):
        from creation_pipeline.runtime import model_call
        def associate(*args):
            args[5]()
            raise model_call.ModelExecutionError('association transport failed')
        with (patch('creation_pipeline.runtime.preparation.bind', side_effect=RuntimeBlocked('binding_unresolved', 'associate')),
                patch('creation_pipeline.runtime.entry.preflight'),
                patch('creation_pipeline.runtime.entry.associate', side_effect=associate),
                patch.object(LocalExecutor, 'host', return_value=HOST)):
            prepare(self.record, self.package, self.sources, self.root / 'work', {}, LocalExecutor())
        result = self.record['runtime_preparation']
        self.assertEqual(result['model_calls'], 1)
        self.assertEqual(result['gaps'][0]['blocker_kind'], 'model_transport')

    def test_subsecond_remaining_budget_is_not_extended(self):
        with patch.object(planner.time, 'monotonic', return_value=0.75), \
                patch.object(planner.model_call, 'call', return_value=({'action': 'plan', 'plan': {}}, {})) as call:
            planner.plan(self.source, {}, self.root / 'audit', planner.options({}), 1.0)
        self.assertEqual(call.call_args.kwargs['timeout'], 0.25)

    def test_expired_deadline_after_guard_does_not_start_model(self):
        clock = [0.0]
        def guard():
            clock[0] = 2.0
        with patch.object(planner.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(planner.model_call, 'call') as call, \
                self.assertRaises(planner.BudgetExceeded):
            planner.plan(self.source, {}, self.root / 'audit', planner.options({}), 1.0, call_guard=guard)
        call.assert_not_called()

    def test_stalled_transport_is_not_reported_as_an_invalid_plan(self):
        from creation_pipeline.runtime import model_call
        stalled = model_call.ModelExecutionError('Model stream produced no lifecycle event for 240.0s')
        stalled.code = 'model_stalled'
        with patch.object(planner.model_call, 'call', side_effect=stalled), \
                self.assertRaises(planner.ModelUnavailable) as caught:
            planner.plan(self.source, {}, self.root / 'audit', planner.options({}), None)
        self.assertEqual(caught.exception.code, 'model_stalled')
        self.assertEqual(caught.exception.kind, 'model_transport')

    def test_planner_passes_the_progress_watchdog_budget(self):
        with patch.object(planner.model_call, 'call', return_value=({'action': 'plan', 'plan': {}}, {})) as call:
            planner.plan(self.source, {}, self.root / 'audit', planner.options({'progress_timeout': 30}), None)
        self.assertEqual(call.call_args.kwargs['progress_timeout'], 30)

    def test_progress_watchdog_option_is_validated(self):
        self.assertEqual(planner.options({})['progress_timeout'], 240)
        self.assertIsNone(planner.options({'progress_timeout': None})['progress_timeout'])
        for bad in (0, -5, 'x', 1.5):
            with self.assertRaises(planner.PlanningError):
                planner.options({'progress_timeout': bad})

    def test_resources_scope_unknown_and_model_availability_not_trusted(self):
        p = plan()
        p['resources'] = [{'kind': 'weight', 'description': 'weights', 'available': True, 'required_for_execution': True, 'evidence': QUOTE},
                          {'kind': 'gpu', 'description': 'optional training', 'available': False, 'required_for_execution': False, 'evidence': QUOTE}]
        p['unresolved'] = ['Required input size is unknown']
        p['resource_assessment']['status'] = 'unknown'
        request = self.prepared(p)
        with patch.object(LocalExecutor, 'host', return_value=HOST):
            result = LocalExecutor().preflight(request)
        self.assertEqual({g['code'] for g in result['gaps']}, {'resource_missing', 'resource_mount_unresolved', 'resources_unknown'})

    def test_resource_assessment_bad_quote_names_field_path_and_quote_without_model(self):
        p = plan()
        p['resource_assessment']['source_quote'] = 'FROM fabricated@sha256:wrong'
        with patch.object(LocalExecutor, 'host', return_value=HOST), \
             patch.object(planner, 'plan', side_effect=AssertionError('No model call')):
            prepare(self.record, self.package, self.sources, self.root / 'bad-resource-quote',
                    {'plan': p}, LocalExecutor())
        result = self.record['runtime_preparation']
        self.assertEqual(result['status'], 'runtime_blocked')
        detail = result['gaps'][0]['detail']
        for expected in ('resource_assessment', PATH, 'FROM fabricated@sha256:wrong',
                         'does not occur verbatim', 'keeping all required fields'):
            self.assertIn(expected, detail)

    def test_actual_build_failure_is_separate_and_keeps_lock(self):
        request = self.prepared()
        with patch.object(LocalExecutor, 'host', return_value=HOST), patch('creation_pipeline.runtime.local.process', return_value={'exit_code': 1, 'stdout': '', 'stderr': 'build failed'}):
            result = LocalExecutor().build(request)
        self.assertEqual(result['status'], 'build_failed')
        self.assertEqual(result['business_acceptance'], 'not_run')
        self.assertFalse(qualify(self.record['delivery'])[0])
        verify(request.frozen_directory, request.freeze_sha256)

    def test_locked_assertions_cannot_be_changed_for_environment_repair(self):
        request = self.prepared()
        cases = self.record['delivery']['inputs']['acceptance']['payload']['cases']
        changed = plan(); changed['tests'][1]['case_json'] = changed['tests'][1]['case_json'].replace('"stdout_equals": "ok"', '"stdout_equals": "other"')
        record = copy.deepcopy(self.record)
        with patch.object(LocalExecutor, 'host', return_value=HOST):
            prepare(record, self.package, self.sources, self.root / 'repair', {'plan': changed, 'locked_cases': cases}, LocalExecutor())
        self.assertEqual(record['runtime_preparation']['status'], 'runtime_blocked')
        self.assertIn('locked test', str(record['runtime_preparation']))

    def test_plan_change_creates_revision_and_original_files_survive(self):
        request = self.prepared()
        original = self.record['delivery']['revision_id']
        p = plan(); p['base_image'] = 'python:3.12-slim'
        with patch.object(LocalExecutor, 'host', return_value=HOST):
            prepare(self.record, self.package, self.sources, self.root / 'revision', {'plan': p}, LocalExecutor())
        self.assertNotEqual(original, self.record['delivery']['revision_id'])
        self.assertEqual(self.record['delivery']['inputs']['files'], manifest(self.package))
        verify(request.frozen_directory, request.freeze_sha256)

    def test_blocked_evidence_is_durable_in_catalog_and_default_hidden(self):
        self.prepared()
        with patch.object(LocalExecutor, 'host', return_value={'status': 'unavailable', 'gaps': [{'code': 'docker_unavailable', 'detail': 'missing'}]}):
            execute_prepared(self.root / 'output', self.record, LocalExecutor())
        library = self.root / 'library'
        store.adopt(self.root / 'output', [self.record], {'revision_parents': {}, 'batch': {'label': 'test', 'tags': []}}, library)
        self.assertEqual(store.entries(library), [])
        entry = store.get(library, 'probe', include_candidates=True)
        self.assertEqual(entry['current_execution']['status'], 'runtime_blocked')
        self.assertTrue((library / entry['runtime']['path'] / 'receipt.json').is_file())
        import shutil
        shutil.rmtree(self.root / 'output')
        store.get(library, 'probe', include_candidates=True)
        with patch.object(LocalExecutor, 'host', return_value={'status': 'unavailable', 'gaps': [{'code': 'docker_unavailable', 'detail': 'missing'}]}):
            result = resume_build(library, 'probe')
        self.assertEqual(result['status'], 'runtime_blocked')
        entry = store.get(library, 'probe', include_candidates=True)
        self.assertEqual(len(entry['runtime_history']), 1)

    def test_no_hidden_production_quotas(self):
        opts = planner.options({})
        for k in ('max_attempts', 'total_seconds', 'context_chars', 'max_read_rounds', 'max_files', 'max_file_bytes', 'max_context_bytes'):
            self.assertIsNone(opts[k])
        self.assertEqual(planner.options({'max_read_rounds': 20})['max_read_rounds'], 20)

    def test_no_progress_stops_read_loop(self):
        with patch.object(planner.model_call, 'call', return_value=({'action': 'read', 'requested_files': ['main.py']}, {})) as model:
            with self.assertRaisesRegex(planner.PlanningError, 'No progress'):
                planner.plan(self.source, {}, self.root / 'audit', planner.options({}), None)
        self.assertEqual(model.call_count, 1)

    def test_changed_build_inputs_rejected_before_docker(self):
        request = self.prepared()
        (Path(request.frozen_directory) / 'runtime/context/Dockerfile').write_text('FROM scratch\n')
        with patch('creation_pipeline.runtime.local.process', side_effect=AssertionError('Docker called')):
            with self.assertRaisesRegex(ValueError, 'changed'):
                LocalExecutor().build(request)

    def test_explicit_binding_needs_real_file_and_source_quote(self):
        with self.assertRaises(RuntimeBlocked):
            bind(self.package, self.sources, {'entry': 'absent.py', 'source_id': 'tool', 'source_path': 'main.py', 'association': 'identical'})
        with self.assertRaises(RuntimeBlocked):
            bind(self.package, self.sources, {'entry': 'main.py', 'source_id': 'tool', 'source_path': 'main.py', 'association': 'explicit', 'reason': 'user mapping', 'quote': 'invented'})

    def test_credential_values_not_valid_resource_configuration(self):
        from creation_pipeline.runtime.preparation import validate_spec
        with self.assertRaisesRegex(ValueError, 'credential values'):
            validate_spec({'resource_refs': {'license': {'password': 'not-a-reference'}}})
        with self.assertRaisesRegex(ValueError, 'Credential values'):
            validate_spec({'plan': {'environment': [{'name': 'API_TOKEN', 'value': 'opaque-value'}]}})

    def test_runtime_reprepare_keeps_content_and_history(self):
        self.prepared()
        unavailable = {'status': 'unavailable', 'gaps': [{'code': 'docker_unavailable', 'detail': 'missing'}]}
        with patch.object(LocalExecutor, 'host', return_value=unavailable):
            execute_prepared(self.root / 'output', self.record, LocalExecutor())
        library = self.root / 'library'
        store.adopt(self.root / 'output', [self.record], {'revision_parents': {}, 'batch': {'label': 'test', 'tags': []}}, library)
        old = store.get(library, 'probe', include_candidates=True)
        p = plan(); p['base_image'] = 'python:3.12-slim'
        with patch.object(LocalExecutor, 'host', return_value=unavailable), patch.object(planner, 'plan', side_effect=AssertionError('No model needed')):
            result = prepare_revision(library, 'probe', {'plan': p})
        self.assertEqual(result['status'], 'runtime_blocked')
        entry = store.get(library, 'probe', include_candidates=True)
        self.assertNotEqual(old['revision_id'], entry['revision_id'])
        self.assertEqual(entry['delivery']['inputs']['files'], old['delivery']['inputs']['files'])
        self.assertEqual(entry['delivery']['inputs']['acceptance'], old['delivery']['inputs']['acceptance'])
        self.assertEqual(entry['history'][-1]['runtime'], old['runtime'])

    def test_explicit_model_budget_prevents_call(self):
        from creation_pipeline.runtime.preparation import propose
        from creation_pipeline.runtime.preparation import handoff
        handoff(self.package, self.sources, self.root / 'handoff')
        def guard():
            raise RuntimeBlocked('explicit_budget', 'No model calls remaining')
        with patch.object(planner.model_call, 'call', side_effect=AssertionError('Model called')):
            with self.assertRaisesRegex(RuntimeBlocked, 'No model calls'):
                propose(self.root / 'handoff', bind(self.package, self.sources), self.root / 'audit', planner.options({}), call_guard=guard)

    def test_direct_executor_cannot_bypass_unknown_requirement_or_draft(self):
        from creation_pipeline.runtime.preparation import rebind
        original = self.prepared()
        for mode, requirement, code in [('draft', 'required', 'draft_only'), ('normal', 'unknown', 'requirements_unknown')]:
            record = copy.deepcopy(self.record)
            record.pop('durable_evidence')
            d = record['delivery']; d['mode'] = mode; d['inputs']['requirement']['status'] = requirement
            rebind(record, d['inputs']['bindings']['payload'], d['inputs']['environment']['payload'], d['inputs']['acceptance']['payload'])
            frozen = self.root / ('guard-' + mode)
            freeze = seal(frozen, self.package, record, self.sources, Path(original.frozen_directory) / 'runtime')
            request = runtime_request(d, frozen, freeze, self.root / ('attempt-' + mode))
            with patch.object(LocalExecutor, 'host', return_value=HOST), patch('creation_pipeline.runtime.local.process', side_effect=AssertionError('Unexpected build')):
                result = LocalExecutor().build(request)
            self.assertEqual(result['status'], 'runtime_blocked')
            self.assertIn(code, [g['code'] for g in result['gaps']])

    def test_image_loss_changes_current_availability_not_history(self):
        from creation_pipeline.runtime.local import binding_identity
        request = self.prepared()
        historical = {'status': 'built', 'request': binding_identity(request), 'image_id': 'sha256:' + 'a' * 64}
        with patch.object(LocalExecutor, 'host', return_value=HOST), patch('creation_pipeline.runtime.local.process', return_value={'exit_code': 1, 'stdout': '', 'stderr': 'missing image'}):
            current = LocalExecutor().verify_current(request, historical)
        self.assertEqual(current['status'], 'unavailable')
        self.assertEqual(historical['status'], 'built')
