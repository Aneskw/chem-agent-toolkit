"""Interface/policy regressions; doubles here are NOT real Docker acceptance."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.runtime.checks import mapped_checks
from creation_pipeline.runtime.execution import observations_pass, classification, locked_inputs, expected_image_files, image_files_match
from creation_pipeline.runtime.local import LocalExecutor, binding_identity
from creation_pipeline.runtime.preparation import prepare
from creation_pipeline.runtime import runner
from creation_pipeline.records import write_json
from creation_pipeline.artifacts import store
from creation_pipeline.contracts import qualify
from tests.pipeline import test_runtime_build as fixtures
from tests.pipeline.test_runtime_build import HOST, plan


class ExecutionTests(unittest.TestCase):
    setUp = fixtures.RuntimeBuildTests.setUp
    tearDown = fixtures.RuntimeBuildTests.tearDown
    prepared = fixtures.RuntimeBuildTests.prepared

    def test_native_checks_map_actual_delivery_sources_and_output(self):
        checks = {'configured': [{'name': 'actual', 'argv': ['{python}', '{package}/main.py', '{source:tool}/main.py', '{run}/result'],
                                  'cwd': '{package}', 'stdout_contains': ['ok'], 'artifacts': ['result']}]}
        c = mapped_checks(checks, plan(), ['tool'])[0]
        self.assertEqual(c['entrypoint'], 'python')
        self.assertEqual(c['args'], ['/opt/skill/package/main.py', '/sources/tool/main.py', '/output/result'])
        self.assertEqual(c['workdir'], '/opt/skill/package')
        self.assertEqual(c['stdout_contains'], ['ok'])
        self.assertEqual(c['artifacts'], ['result'])
        reviewed = mapped_checks({'reviewed':checks['configured']},plan(),['tool'])
        self.assertEqual(reviewed[0]['name'],'check-reviewed-actual')
        self.assertEqual(reviewed[0]['args'],c['args'])

    def test_host_paths_unresolved_macros_and_escaping_artifacts_are_rejected(self):
        for argv in (['python', 'C:/host/tool.py'], ['python', '/home/host.py'], ['{python}', '{source:missing}/tool.py']):
            with self.assertRaises(ValueError):
                mapped_checks({'configured': [{'name': 'bad', 'argv': argv}]}, plan(), ['tool'])
        with self.assertRaises(ValueError):
            mapped_checks({'configured': [{'name': 'bad', 'argv': ['python'], 'artifacts': ['../secret']}]}, plan(), [])

    def test_frozen_case_source_and_support_bytes_are_rechecked(self):
        request = self.prepared()
        cases = locked_inputs(self.record, request)
        self.assertEqual(len(cases), 2)
        hashes = expected_image_files(self.record, request)
        self.assertIn('package/main.py', hashes)
        good = {'exit_code': 0, 'stdout': ''.join(v + '  ' + k + '\n' for k, v in hashes.items())}
        self.assertTrue(image_files_match(good, hashes))
        self.assertFalse(image_files_match(dict(good, stdout=''), hashes))
        locked = Path(request.frozen_directory) / 'runtime/locked-tests.json'
        write_json(locked, {'cases': [], 'policy': {}})
        with self.assertRaises(ValueError):
            locked_inputs(self.record, request)

    def test_wrong_output_cannot_pass_by_editing_status_flags(self):
        c = {'name': 'business', 'oracle_status': 'supported', 'args': [], 'stdout_equals': 'ok'}
        o = {'name': 'business', 'status': 'passed', 'exit_code': 0, 'command': ['docker','run','image'], 'stdout':'wrong'}
        self.assertFalse(observations_pass([c], [o], 'image', self.root))
        o['stdout'] = 'ok'
        self.assertTrue(observations_pass([c], [o], 'image', self.root))
        o['command'][-1] = 'other-image'
        self.assertFalse(observations_pass([c], [o], 'image', self.root))

    def test_business_error_words_are_not_resource_success(self):
        cases = [{'name':'deps'}, {'name':'business','expected_exit':0}]
        observed = [{'name':'deps','layer':'environment','status':'failed','oracle_status':'supported','exit_code':1},
                    {'name':'business','layer':'behavior','status':'failed','oracle_status':'supported','exit_code':0,'stdout':'CUDA unavailable'}]
        self.assertEqual(classification(cases, observed), 'unknown')
        observed[1]['exit_code'] = 1
        self.assertEqual(classification(cases, observed), 'environment')
        observed[0]['exit_code'] = 0
        self.assertEqual(classification(cases, observed), 'unknown')

    def test_tag_retarget_and_image_loss_invalidate_current_evidence(self):
        request = self.prepared()
        receipt = {'status':'built','request':binding_identity(request),'image_id':'sha256:bound','tag':'owned'}
        good = {'exit_code':0,'stdout':'sha256:bound','stderr':''}
        with patch.object(LocalExecutor, 'host', return_value=HOST):
            for bad in ({'exit_code':1,'stdout':'','stderr':'missing'}, dict(good, stdout='sha256:other')):
                with patch('creation_pipeline.runtime.local.process', side_effect=[good,bad]):
                    self.assertEqual(LocalExecutor().verify_current(request,receipt)['status'], 'unavailable')
            with patch('creation_pipeline.runtime.local.process', side_effect=[good,good]):
                self.assertEqual(LocalExecutor().verify_current(request,receipt)['status'], 'available')

    def test_no_execution_evidence_never_qualifies(self):
        self.prepared()
        self.record['delivery']['execution']['status'] = 'passed'
        self.assertFalse(qualify(self.record['delivery'])[0])

    def test_typed_contract_changes_increment_version_and_cannot_bypass_locks(self):
        from creation_pipeline.runtime.preparation import rebind
        from creation_pipeline.records import read_json
        request = self.prepared()
        d = self.record['delivery']
        binding = copy.deepcopy(d['inputs']['bindings']['payload'])
        env = copy.deepcopy(d['inputs']['environment']['payload'])
        rebind(self.record, binding, env, {'typed_value': 10})
        old = copy.deepcopy(d['inputs']['acceptance'])
        rebind(self.record, binding, env, {'typed_value': 10.0})
        self.assertEqual(d['inputs']['acceptance']['version'], old['version'] + 1)
        self.assertNotEqual(d['inputs']['acceptance']['sha256'], old['sha256'])
        # Restore the actual frozen record for locking checks.
        self.record = read_json(Path(request.frozen_directory) / 'record.json')
        locked = copy.deepcopy(self.record['delivery']['inputs']['acceptance']['payload']['cases'])
        p = plan(); p['tests'][1]['tolerance'] = 0.0
        with patch.object(LocalExecutor, 'host', return_value=HOST):
            prepare(self.record, self.package, self.sources, self.root/'typed-repair',
                    {'plan': p, 'locked_cases': locked}, LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['status'], 'runtime_blocked')
        self.assertTrue(any('locked test' in g['detail'] for g in self.record['runtime_preparation']['gaps']))
        frozen_record = read_json(Path(request.frozen_directory) / 'record.json')
        lock_path = Path(request.frozen_directory) / 'runtime/locked-tests.json'
        lock = read_json(lock_path); lock['cases'][1]['tolerance'] = 0.0
        write_json(lock_path, lock)
        with self.assertRaisesRegex(ValueError, 'Locked tests differ'):
            locked_inputs(frozen_record, request)

    def test_environment_repair_cannot_weaken_locked_assertions(self):
        self.prepared()
        old = copy.deepcopy(self.record['delivery']['inputs']['acceptance']['payload']['cases'])
        p = plan(); import json
        c = json.loads(p['tests'][1]['case_json']); c['stdout_equals'] = 'wrong'
        p['tests'][1]['case_json'] = json.dumps(c)
        with patch.object(LocalExecutor,'host',return_value=HOST):
            prepare(self.record,self.package,self.sources,self.root/'repair',{'plan':p,'locked_cases':old},LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['status'],'runtime_blocked')
        self.assertEqual((self.package/'main.py').read_text(), (self.source/'main.py').read_text())

    def test_revoked_content_cannot_resume_as_environment_only(self):
        self.prepared()
        store.adopt(self.root/'output',[self.record],{'revision_parents':{},'batch':{'label':'unit','tags':[]}},self.root/'library')
        catalog=store.catalog(self.root/'library'); catalog['skills'][0]['current_content']={'status':'failed'}
        write_json(self.root/'library/catalog.json',catalog)
        from creation_pipeline.runtime.service import resume_build
        with patch('creation_pipeline.runtime.diagnosis.model_call.call', side_effect=ValueError('Source diagnosis unresolved')):
            result = resume_build(self.root/'library','probe',reuse_image=True)
        self.assertEqual(result['status'], 'review_required')
        self.assertFalse(store.get(self.root/'library', 'probe', include_candidates=True)['current_qualification']['accepted'])
        from creation_pipeline.runtime.recovery import inspect_candidate
        inspected = inspect_candidate(self.root/'library', 'probe')
        self.assertEqual(inspected['action'], 'review_required')
        self.assertIn('not proof of defective source', inspected['reason'])

    def test_oracle_correction_requires_verified_source_and_independent_approval(self):
        self.prepared()
        library=self.root/'library'
        store.adopt(self.root/'output',[self.record],{'revision_parents':{},'batch':{'label':'unit','tags':[]}},library)
        before=(library/'catalog.json').read_bytes()
        from creation_pipeline.runtime.service import prepare_revision
        correction={'reason':'Review a claimed source-supported expectation error',
                    'citations':[{'source_id':'tool','path':'main.py','quote':'not in the source'}]}
        with patch('creation_pipeline.runtime.review.review_snapshot',side_effect=AssertionError('must not call model for false citation')):
            with self.assertRaisesRegex(ValueError,'mismatched source'):
                prepare_revision(library,'probe',{'plan':plan()},correction=correction)
        correction['citations'][0]['quote']='print("ok")'
        with patch('creation_pipeline.runtime.review.review_snapshot',return_value={'review':{'status':'pass','oracle_changes_verified':False,'requirement_assessment':'confirmed'}}) as review:
            with self.assertRaisesRegex(ValueError,'did not confirm'):
                prepare_revision(library,'probe',{'plan':plan()},correction=correction)
            self.assertEqual(review.call_count,1)
        self.assertEqual((library/'catalog.json').read_bytes(),before)

    def test_timeout_retains_partial_logs_and_cleanup_handle(self):
        case={'name':'slow','origin':'test','basis':'unit','args':[]}
        exc=runner.subprocess.TimeoutExpired(['docker'],1,output='partial',stderr='diagnostic')
        exc.cleanup=[{'scope':'owned','phase':'removed'}]; exc.scope='owned'
        with patch.object(runner,'run',side_effect=exc):
            result=runner.run_case(self.root,{'behavior':{'file_io':False}},'image',case,artifact_dir=self.root/'retained')
        self.assertTrue(result['timed_out'])
        self.assertEqual(result['stdout'],'partial')
        self.assertEqual(result['scope'],'owned')
        self.assertEqual(result['cleanup'],exc.cleanup)

    def test_native_production_checks_never_execute_on_host(self):
        from creation_pipeline.validation.checks import run_checks
        from types import SimpleNamespace
        config={'_docker_checks':True,'checks':[{'name':'check','argv':['{python}','-c','raise Exception()'],'stdout_contains':['locked']}]}
        result=run_checks(config,{'tests':[]},self.package,SimpleNamespace(evidence=[]),self.root/'checks',True)
        self.assertEqual(result[0]['status'],'not_run')
        self.assertEqual(result[0]['executor'],'docker')

    def test_native_artifacts_remain_nonempty_in_execution_and_recheck(self):
        from creation_pipeline.runtime.execution import observations_pass
        from creation_pipeline.contracts import fingerprint
        case = {'name': 'artifact', 'origin': 'authored_check', 'basis': 'unit contract',
                'mapped_check': True, 'oracle_status': 'supported', 'args': [], 'artifacts': ['result.json']}
        for content, passed in (('', False), ('{}', True)):
            with self.subTest(content=content):
                def run(tool, image, args, input_dir, output_dir, entrypoint, timeout):
                    (output_dir / 'result.json').write_text(content)
                    return {'exit_code': 0, 'stdout': '', 'stderr': '', 'command': ['docker', 'run', 'sha256:test']}
                target = self.root / ('case-' + fingerprint(case['name'])[:16])
                with patch.object(runner, 'run', side_effect=run):
                    observed = runner.run_case(self.root, {'behavior': {'file_io': False}},
                        'sha256:test', case, artifact_dir=target)
                self.assertEqual(observed['status'] == 'passed', passed)
                # Rechecking must independently reject even a forged pass flag.
                observed['status'] = 'passed'
                self.assertEqual(observations_pass([case], [observed], 'sha256:test', self.root), passed)

    def test_native_json_equals_preserves_original_exact_equality(self):
        import json
        for expected, actual, passed in ((10, 10.0, True), (0, 0.0, True),
                ({'a': 1}, {'a': 1, 'extra': 2}, False),
                ([1, 2], [1.0, 2.0], True), (10, 11.0, False), (10, '10', False)):
            with self.subTest(expected=expected, actual=actual):
                case = {'json_equals': {'value': expected}}
                result = {'stdout': json.dumps({'value': actual})}
                self.assertEqual(runner.output_matches(case, result, result['stdout']), passed)
        # Migrated legacy typed business assertions keep their original semantics.
        self.assertFalse(runner.subset(10, 10.0))

    def test_generated_evidence_array_is_reported_without_type_error(self):
        from creation_pipeline.validation.checks import run_checks
        from types import SimpleNamespace
        sources = SimpleNamespace(evidence=[{'id': 'e1', 'excerpt': 'fixed source contract'}])
        test = {'name': 'business', 'argv': ['{python}', '{package}/main.py'],
                'stdout_contains': ['ok'], 'evidence': ['e1'], 'purpose': 'source-backed result'}
        config = {'_docker_checks': True, 'checks': []}
        reports = run_checks(config, {'tests': [test]}, self.package, sources, self.root/'checks')
        self.assertEqual(reports[0]['status'], 'fail')
        self.assertIn('source evidence', reports[0]['findings'][0])
        test['evidence'] = 'e1'
        reports = run_checks(config, {'tests': [test]}, self.package, sources, self.root/'checks')
        self.assertEqual(reports[0]['executor'], 'docker')

    def test_runtime_failure_routes_to_existing_repair_modules(self):
        # Fault-injected receipts exercise scheduling only, not Docker/model success.
        from tests.pipeline.test_discovery import DiscoveryTests, discovery, candidate
        from tests.pipeline.test_delivery_protocol import text_artifact, configure_text
        from creation_pipeline.runtime.preparation import prepare as real_prepare
        for lane in ('environment', 'content'):
            with self.subTest(lane=lane):
                fixture = DiscoveryTests(); fixture.setUp()
                try:
                    configure_text(fixture)
                    artifact = text_artifact()
                    artifact['runtime_requirement']['status'] = 'required'
                    specs = []
                    def prepare(*args, **kwargs):
                        specs.append(copy.deepcopy(args[4]))
                        return real_prepare(*args, **kwargs)
                    def fail(output, record, executor, **kwargs):
                        record['runtime'] = {'fault_injection': True}
                        record['status'] = 'failed'
                        if lane == 'content':
                            record['content_status'] = 'failed'
                        return {'status': 'execution_failed', 'execution': {
                            'repair_lane': lane, 'cases': [{'name': 'locked-business', 'status': 'failed'}]}}
                    with patch('creation_pipeline.runtime.preparation.prepare', side_effect=prepare), patch(
                            'creation_pipeline.runtime.service.execute_prepared', side_effect=fail) as execution:
                        result, summary = fixture.run_case(discovery(candidate()), artifact, artifact)
                    self.assertFalse(result['errors'], summary)
                    self.assertEqual(execution.call_count, 2)
                    self.assertIn('locked_cases', specs[1])
                    prompts = fixture.last_backend.prompts
                    author_turns = sum('"_phase": "author"' in p for p in prompts)
                    review_turns = sum('"_phase": "review"' in p for p in prompts)
                    self.assertEqual(author_turns, 1 if lane == 'environment' else 2)
                    self.assertEqual(review_turns, author_turns)
                    if lane == 'environment':
                        self.assertEqual(specs[1]['feedback']['policy'], 'Fix environment only; source and tests are immutable')
                    else:
                        self.assertTrue(any('locked_acceptance' in p for p in prompts))
                finally:
                    fixture.tearDown()

    def test_execution_failure_does_not_stop_next_native_candidate(self):
        # A scheduling double only; actual failure evidence is validated by the
        # separate real wrong-result probe, never manufactured by this test.
        from tests.pipeline.test_discovery import DiscoveryTests, discovery, candidate
        from tests.pipeline.test_delivery_protocol import text_artifact, configure_text
        fixture=DiscoveryTests();fixture.setUp();self.addCleanup(fixture.tearDown)
        configure_text(fixture)
        fixture.options['checks']=[];fixture.options['limits']['repair_rounds']=0
        write_json(fixture.config,fixture.options)
        first=text_artifact();first['runtime_requirement']['status']='required'
        second=text_artifact();second['files'][0]['content']=second['files'][0]['content'].replace('name: add-numbers','name: second')
        def failed(output, record, executor, **kwargs):
            record.update(status='failed',content_status='failed')
            return {'status':'execution_failed','execution':{'repair_lane':'content','cases':[{'name':'business','status':'failed'}]}}
        with patch('creation_pipeline.runtime.service.execute_prepared',side_effect=failed) as execution:
            result,summary=fixture.run_case(discovery(candidate(),candidate('second')),first,second)
        self.assertEqual(execution.call_count,1)
        self.assertEqual(result['status'],'partial',summary)
        self.assertEqual([(e['name'],e['status']) for e in summary['entities']],[('add-numbers','failed'),('second','ready')])


if __name__ == '__main__': unittest.main()
